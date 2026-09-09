"""Bounded local publishing: operator text, vector artwork, interactive PDFs and ZIPs.

No account access, uploads, user-selected paths or network calls. Approved handoffs
persist personal records and Studio provenance in the managed workspace database.
The parent server must run its safety gate before dispatching this handler.
"""
import base64
from contextlib import contextmanager
import fcntl
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import textwrap
import threading
import zipfile
from datetime import datetime, timezone
from html import escape

from utils import integrations_hub

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas
except ImportError:
    canvas = None

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    PdfReader = PdfWriter = None

try:
    import pypdfium2 as pdfium
except ImportError:
    pdfium = None

ROUTE = "/api/workspace/studio-pro"
MAX_REQUEST = 262144
MAX_TEXT = 100000
MAX_PAGES = 240
MAX_PREVIEW_PDF = 8 * 1024 * 1024
MAX_PREVIEW_REQUEST = 12 * 1024 * 1024
_PREVIEW_KEY = secrets.token_bytes(32)
_PREVIEW_LOCK = threading.Lock()
SOURCE = "Local original layout; operator-supplied content"
STRUCTURES = {
    "course": ("Course workbook", ["Learning outcome", "Core concepts", "Guided practice", "Assessment", "Reflection"]),
    "daily": ("Daily planner", ["Priorities", "Schedule", "Tasks", "Reflection"]),
    "weekly": ("Weekly planner", ["Weekly intention", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Weekend"]),
    "workout": ("Workout planner", ["Session goal", "Exercises", "Recovery"]),
    "meals": ("Meal planner", ["Meals for the week", "Shopping list", "Preparation"]),
    "calendar": ("Monthly calendar", ["Monthly intention", "Key dates", "Weekly plans"]),
    "colouring": ("Colouring pages", ["Palette", "Creative practice", "Reflection"]),
    "budget": ("Personal budget planner", ["Income and fixed costs", "Flexible spending", "Savings goals", "Review"]),
    "habits": ("Habit tracker", ["Intentions", "Weekly check-in", "Reflection"]),
    "content": ("Content calendar", ["Audience", "Content pillars", "Publishing plan", "Review"]),
    "product": ("Product launch workbook", ["Audience problem", "Offer", "Production", "Rights review", "Launch checklist"]),
}


def _object(value, allowed, label):
    if not isinstance(value, dict):
        raise ValueError(label + " must be an object")
    if set(value) - set(allowed):
        raise ValueError(label + " contains unsupported fields")
    return value


def _text(value, maximum, label, required=False, single=False, preserve=False):
    if not isinstance(value, str):
        raise ValueError(label + " must be text")
    if len(value) > maximum:
        raise ValueError(f"{label} must be at most {maximum} characters")
    if any(ord(char) < 32 and char not in "\n\r\t" for char in value) or "\x7f" in value:
        raise ValueError(label + " contains control characters")
    if single and any(char in value for char in "\n\r\t"):
        raise ValueError(label + " must be a single line")
    value = value if preserve else value.strip()
    if required and not value.strip():
        raise ValueError(label + " is required")
    # Built-in PDF and AcroForm fonts support Western Latin text. Reject rather
    # than silently substituting missing glyphs in a product for publication.
    try:
        value.encode("cp1252")
    except UnicodeEncodeError:
        raise ValueError(label + " currently supports Western Latin characters only") from None
    return value if preserve else value.replace("\r\n", "\n").replace("\r", "\n")


def validate_document(value):
    data = _object(value, {"title", "subtitle", "audience", "template", "version", "source", "brand", "sections", "fillable", "include_answer_notes", "instructions", "licence"}, "Document")
    result = {}
    for key, limit in {"title": 120, "subtitle": 280, "audience": 240, "version": 24, "source": 300, "instructions": 12000, "licence": 12000}.items():
        result[key] = _text(data.get(key, "1.0" if key == "version" else ""), limit, key, required=key in {"title", "version"}, single=key in {"title", "version"}, preserve=key in {"instructions", "licence"})
    template = data.get("template", "course")
    if not isinstance(template, str) or template not in STRUCTURES:
        raise ValueError("Choose a supported template")
    result["template"] = template
    for key, default in (("fillable", True), ("include_answer_notes", False)):
        value = data.get(key, default)
        if type(value) is not bool:
            raise ValueError(key + " must be true or false")
        result[key] = value
    brand = _object(data.get("brand", {}), {"name", "accent", "font"}, "Brand")
    accent = brand.get("accent", "#176B64")
    if not isinstance(accent, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
        raise ValueError("Accent must be a six-digit hex colour")
    font = brand.get("font", "serif")
    if not isinstance(font, str) or font not in {"serif", "sans"}:
        raise ValueError("Choose serif or sans typography")
    result["brand"] = {"name": _text(brand.get("name", ""), 80, "Brand name", single=True), "accent": accent.upper(), "font": font}
    sections = data.get("sections")
    if not isinstance(sections, list) or not 1 <= len(sections) <= 24:
        raise ValueError("Add between 1 and 24 sections")
    result["sections"] = []
    for index, section in enumerate(sections, 1):
        _object(section, {"title", "content", "activity", "quizzes", "answer_notes"}, f"Section {index}")
        item = {key: _text(section.get(key, ""), limit, f"Section {index} {key}", required=key == "title", single=key == "title")
                for key, limit in {"title": 160, "content": 6000, "activity": 2000, "answer_notes": 3000}.items()}
        quizzes = section.get("quizzes", [])
        if not isinstance(quizzes, list) or len(quizzes) > 8:
            raise ValueError("Use at most 8 quiz questions per section")
        item["quizzes"] = []
        for quiz in quizzes:
            _object(quiz, {"question", "answer_notes"}, "Quiz")
            item["quizzes"].append({"question": _text(quiz.get("question", ""), 600, "Quiz question", True),
                                    "answer_notes": _text(quiz.get("answer_notes", ""), 1500, "Quiz answer notes")})
        result["sections"].append(item)
    if len(json.dumps(result, ensure_ascii=False)) > MAX_TEXT:
        raise ValueError("Document exceeds the 100,000-character combined content limit")
    return result


def capabilities():
    return {"success": True, "templates": [{"id": key, "title": value[0], "sections": value[1]} for key, value in STRUCTURES.items()],
            "capabilities": {"pdf": canvas is not None, "fillable": canvas is not None, "hyperlinks": canvas is not None,
                             "pypdf_metadata": PdfWriter is not None, "preview_images": pdfium is not None, "svg": True, "bundle": canvas is not None},
            "limits": {"request_bytes": MAX_REQUEST, "preview_request_bytes": MAX_PREVIEW_REQUEST, "sections": 24, "quizzes_per_section": 8, "combined_characters": MAX_TEXT, "pages": MAX_PAGES},
            "providers": {"ai_images": "not_connected", "canva_sync": "not_connected"},
            "notice": "Original local vector layouts. Add your own lessons and licence. Western Latin PDF text is supported."}


def _stem(doc):
    def slug(value, limit):
        return re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-_")[:limit] or "document"
    return "u1-" + slug(doc["title"], 64) + "-v" + slug(doc["version"], 24)


def _metadata(doc):
    return {"title": doc["title"], "version": doc["version"], "source": SOURCE,
            "content_source": doc["source"], "template": doc["template"], "brand": doc["brand"],
            "created_at": datetime.now(timezone.utc).isoformat(), "ai_generated": False,
            "answer_notes_included": doc["include_answer_notes"], "section_titles": [s["title"] for s in doc["sections"]]}


def artwork(doc):
    accent = doc["brand"]["accent"]
    # Geometry is local and original; values are text nodes, never SVG markup.
    def lines(value, count, size, spacing):
        return "".join(f'<tspan x="82" dy="{0 if index == 0 else spacing}" textLength="{min(736, len(line)*size*.58):.1f}" lengthAdjust="spacingAndGlyphs">{escape(line)}</tspan>'
                       for index, line in enumerate(textwrap.wrap(value, count)))
    title = lines(doc["title"], 27, 51, 64)
    subtitle = lines(doc["subtitle"], 48, 23, 29)
    brand = lines(doc["brand"]["name"] or "INDEPENDENT STUDIO", 48, 22, 26)
    inner = f'''<rect width="900" height="1200" fill="#f8f4eb"/>
<rect x="0" y="0" width="22" height="1200" fill="{accent}"/>
<circle cx="710" cy="290" r="210" fill="{accent}" opacity="0.18"/>
<circle cx="710" cy="290" r="136" fill="none" stroke="{accent}" stroke-width="2"/>
<path d="M82 365H800M82 382H670" stroke="{accent}" stroke-width="6"/>
<text x="82" y="115" font-family="sans-serif" font-size="22" fill="#172923">{brand}</text>
<text x="82" y="315" font-family="sans-serif" font-size="19" fill="#172923">{escape(STRUCTURES[doc['template']][0].upper())}</text>
<text x="82" y="455" font-family="sans-serif" font-size="23" fill="#172923">{subtitle}</text>
<text x="82" y="710" font-family="{'serif' if doc['brand']['font'] == 'serif' else 'sans-serif'}" font-size="51" fill="#172923">{title}</text>
<text x="82" y="1120" font-family="sans-serif" font-size="18" fill="#172923" textLength="680" lengthAdjust="spacingAndGlyphs">VERSION {escape(doc['version'])} / ORIGINAL LOCAL DESIGN</text>'''
    cover = f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1200" viewBox="0 0 900 1200" role="img"><title>{escape(doc["title"])}</title>{inner}</svg>'
    mockup = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="1100" viewBox="0 0 1400 1100" role="img"><title>{escape(doc['title'])} product mockup</title>
<rect width="1400" height="1100" fill="#e7e4db"/><ellipse cx="720" cy="976" rx="480" ry="40" fill="#182e28" opacity="0.14"/>
<path d="M357 92L1014 132L1060 952L391 946Z" fill="#c3c2b8"/><path d="M341 84L369 103L399 934L369 910Z" fill="{accent}"/>
<g transform="translate(365 96) rotate(2 310 420)"><svg width="625" height="834" viewBox="0 0 900 1200">{inner}</svg></g></svg>'''
    return {"cover": cover.encode("utf-8"), "mockup": mockup.encode("utf-8")}


def _wrap(value, font, size, width):
    """Measured wrapping, including long tokens and explicit paragraph breaks."""
    result = []
    for paragraph in value.expandtabs(4).split("\n"):
        line = ""
        for word in paragraph.split():
            if line and stringWidth(line + " " + word, font, size) > width:
                result.append(line)
                line = ""
            while stringWidth(word, font, size) > width:
                low, high = 1, len(word)
                while low < high:
                    middle = (low + high + 1) // 2
                    if stringWidth(word[:middle], font, size) <= width:
                        low = middle
                    else:
                        high = middle - 1
                result.append(word[:low])
                word = word[low:]
            if word:
                line = (line + " " + word).strip()
        result.append(line)
    return result


class _Layout:
    def __init__(self, doc):
        self.doc = doc
        self.stream = io.BytesIO()
        self.pdf = canvas.Canvas(self.stream, pagesize=A4, pageCompression=1)
        self.pdf.setTitle(doc["title"])
        self.pdf.setAuthor(doc["brand"]["name"])
        self.pdf.setSubject(f"Version {doc['version']} | {SOURCE} | {doc['source']}")
        self.pdf.setCreator("U1 OS Digital Studio / reportlab")
        self.accent = colors.HexColor(doc["brand"]["accent"])
        self.ink = colors.HexColor("#172923")
        self.heading_font = "Times-Roman" if doc["brand"]["font"] == "serif" else "Helvetica-Bold"
        self.width, self.height = A4
        self.page = 0
        self.y = 0
        self.fields = []
        self.section_pages = []

    def finish_page(self):
        self.pdf.setFillColor(self.ink)
        self.pdf.setFont("Helvetica", 8)
        self.pdf.drawString(48, 46, f"Created locally / Version {self.doc['version']}")
        self.pdf.drawRightString(self.width-48, 32, str(self.page))
        if self.page > 1:
            self.pdf.drawCentredString(self.width/2, 32, "Back to contents")
            self.pdf.linkRect("Contents", "contents", (self.width/2-45, 24, self.width/2+45, 44), relative=0, thickness=0)
        self.pdf.showPage()

    def new_page(self):
        if self.page:
            self.finish_page()
        self.page += 1
        if self.page > MAX_PAGES:
            raise ValueError("Document exceeds the 240-page limit; shorten the content")
        self.pdf.setFillColor(colors.HexColor("#FAF8F2"))
        self.pdf.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        self.pdf.setFillColor(self.accent)
        self.pdf.rect(0, self.height-12, self.width, 12, fill=1, stroke=0)
        self.pdf.setFillColor(self.ink)
        self.pdf.setFont("Helvetica", 9)
        for index, line in enumerate(_wrap(self.doc["title"], "Helvetica", 9, self.width-96)):
            self.pdf.drawString(48, self.height-39-index*12, line)
        self.y = self.height-95

    def ensure(self, height):
        if self.y-height < 70:
            self.new_page()

    def block(self, value, size=11, font="Helvetica", gap=12):
        for line in _wrap(value, font, size, self.width-96):
            self.ensure(size*1.45)
            self.pdf.setFillColor(self.ink)
            self.pdf.setFont(font, size)
            self.pdf.drawString(48, self.y, line)
            self.y -= size*1.45
        self.y -= gap

    def heading(self, value):
        self.ensure(75)
        self.block(value, 17, self.heading_font, 10)

    def field(self, name, label):
        self.ensure(151)
        self.block(label, 10, "Helvetica-Bold", 6)
        height = 96
        if self.doc["fillable"]:
            self.pdf.acroForm.textfield(name=name, tooltip=label, x=48, y=self.y-height,
                width=self.width-96, height=height, borderWidth=1, borderColor=self.accent,
                fillColor=colors.white, textColor=self.ink, fontName="Helvetica", fontSize=11,
                forceBorder=True, fieldFlags="multiline", maxlen=3000, value="")
            self.fields.append(name)
        else:
            self.pdf.setStrokeColor(self.accent)
            self.pdf.rect(48, self.y-height, self.width-96, height, fill=0, stroke=1)
            for row in range(1, 4):
                self.pdf.line(60, self.y-row*23, self.width-60, self.y-row*23)
        self.y -= height+23

    def build(self):
        doc = self.doc
        self.new_page()
        self.block(doc["brand"]["name"] or "INDEPENDENT STUDIO", 12, "Helvetica-Bold", 36)
        self.block(STRUCTURES[doc["template"]][0].upper(), 10, "Helvetica", 26)
        self.block(doc["title"], 32, self.heading_font, 30)
        if doc["subtitle"]:
            self.block(doc["subtitle"], 15, gap=24)
        if doc["audience"]:
            self.block("For: " + doc["audience"], 11)
        self.block(f"Version {doc['version']} / {len(doc['sections'])} sections", 11, gap=24)
        self.ensure(30)
        self.pdf.setFont("Helvetica-Bold", 11)
        self.pdf.drawString(48, self.y, "Open contents")
        self.pdf.linkRect("Open contents", "contents", (48, self.y-5, 180, self.y+15), relative=0, thickness=0)
        self.new_page()
        self.pdf.bookmarkPage("contents")
        self.pdf.addOutlineEntry("Contents", "contents", level=0)
        self.heading("Contents")
        for index, section in enumerate(doc["sections"], 1):
            title = f"{index:02d} / {section['title']}"
            lines = _wrap(title, "Helvetica", 12, self.width-96)
            self.ensure(len(lines)*17.4+18)
            top = self.y+13
            self.block(title, 12, gap=14)
            self.pdf.linkRect(section["title"], f"section-{index}", (48, self.y+8, self.width-48, top), relative=0, thickness=0)
        for index, section in enumerate(doc["sections"], 1):
            self.new_page()
            self.pdf.bookmarkPage(f"section-{index}")
            self.pdf.addOutlineEntry(section["title"], f"section-{index}", level=0)
            self.section_pages.append({"index": index-1, "title": section["title"], "page": self.page})
            self.block(f"SECTION {index:02d}", 10)
            self.block(section["title"], 25, self.heading_font, 22)
            if section["content"]:
                self.block(section["content"])
            if section["activity"]:
                self.heading("Activity")
                self.block(section["activity"])
            self.field(f"s{index:02d}_response", f"Section {index} / Your response")
            for qindex, quiz in enumerate(section["quizzes"], 1):
                self.heading(f"Question {qindex}")
                self.block(quiz["question"])
                self.field(f"s{index:02d}_q{qindex:02d}", f"Section {index} / Question {qindex} response")
        notes = [(i, section) for i, section in enumerate(doc["sections"], 1)
                 if section["answer_notes"] or any(q["answer_notes"] for q in section["quizzes"])]
        if doc["include_answer_notes"] and notes:
            self.new_page()
            self.pdf.bookmarkPage("answer-notes")
            self.pdf.addOutlineEntry("Operator answer notes", "answer-notes", level=0)
            self.heading("Operator answer notes")
            for index, section in notes:
                self.heading(f"{index:02d} / {section['title']}")
                if section["answer_notes"]:
                    self.block(section["answer_notes"])
                for qindex, quiz in enumerate(section["quizzes"], 1):
                    if quiz["answer_notes"]:
                        self.block(f"Question {qindex}: " + quiz["answer_notes"])
        self.finish_page()
        self.pdf.save()
        raw = self.stream.getvalue()
        if PdfWriter is not None:
            reader = PdfReader(io.BytesIO(raw))
            writer = PdfWriter()
            writer.clone_document_from_reader(reader)
            writer.add_metadata({"/U1Version": doc["version"], "/U1Source": SOURCE, "/U1ContentSource": doc["source"], "/U1Template": doc["template"]})
            target = io.BytesIO()
            writer.write(target)
            raw = target.getvalue()
        return raw


def _artifact(raw, name, mime):
    return {"filename": name, "mime": mime, "content": base64.b64encode(raw).decode("ascii"),
            "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _receipt_signature(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hmac.new(_PREVIEW_KEY, b"studio-product-v1:"+encoded, hashlib.sha256).hexdigest()


def _handoff_receipt(doc, artifact):
    document_key = hashlib.sha256(json.dumps(doc,sort_keys=True,separators=(",", ":"),ensure_ascii=True).encode("ascii")).hexdigest()
    value = {"document_key": document_key, "title": doc["title"], "version": doc["version"],
             "audience": doc["audience"], "description": doc["subtitle"], "content_source": doc["source"],
             "filename": artifact["filename"], "mime": artifact["mime"], "size": artifact["size"], "sha256": artifact["sha256"]}
    return {"artifact": value, "signature": _receipt_signature(value)}


def _handoff_file(body):
    from utils import prism_workspace as workspace
    receipt = _object(body.get("receipt"), {"artifact", "signature"}, "Artifact receipt")
    value = receipt.get("artifact")
    _object(value, {"document_key","title","version","audience","description","content_source","filename","mime","size","sha256"}, "Signed artifact")
    signature = receipt.get("signature")
    if not isinstance(signature,str) or not re.fullmatch(r"[a-f0-9]{64}",signature) or not hmac.compare_digest(signature,_receipt_signature(value)):
        raise ValueError("The artifact receipt is invalid or expired. Generate and save the current document again.")
    file_id = workspace.identifier(body.get("file_id"))
    verify = getattr(workspace, "read_verified_file", None)
    if not callable(verify):
        raise RuntimeError("Managed Files integrity verification is unavailable. Complete the Files update before handing off a product.")
    row, raw = verify(file_id)
    if not row or row["deleted"] is not None or row["status"] != "ready" or row["received"] != row["size"]:
        raise ValueError("Choose the successfully saved, ready file. Missing, uploading and trashed files cannot be handed off.")
    if any(row[key] != value[other] for key,other in (("name","filename"),("mime","mime"),("size","size"),("checksum","sha256"))):
        raise ValueError("The saved file does not match this generated artifact receipt.")
    if len(raw) != value["size"] or hashlib.sha256(raw).hexdigest() != value["sha256"]:
        raise ValueError("The verified file bytes do not match this generated artifact receipt.")
    if value["mime"] not in {"application/pdf","application/zip"}:
        raise ValueError("Only generated PDF or ZIP files can become catalogue products.")
    return value, dict(row)


@contextmanager
def _provenance_lock(workspace):
    """Serialize Studio processes while retaining personal.action for all records."""
    with workspace.database() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS studio_product_origins (
                document_key TEXT PRIMARY KEY, product_id TEXT,
                seed_file_id TEXT NOT NULL, artifact_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS studio_launch_origins (
                product_id TEXT NOT NULL, task_key TEXT NOT NULL, launch_id TEXT NOT NULL,
                PRIMARY KEY(product_id,task_key)
            );
        """)
    fd = os.open(workspace.DATA / ".studio-handoff.lock",
                 os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            from utils.u1_personal_core import PersonalError
            raise PersonalError("Another Studio handoff is running. Review again after it finishes.", 409, "handoff_busy") from None
        yield
    finally:
        os.close(fd)


def _origin(artifact):
    from utils import prism_workspace as workspace
    with workspace.database() as conn:
        row = conn.execute("SELECT * FROM studio_product_origins WHERE document_key=?", (artifact["document_key"],)).fetchone()
    return dict(row) if row else None


def _bind_origin(artifact, file_id, product_id=None):
    from utils import prism_workspace as workspace
    with workspace.database() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT OR IGNORE INTO studio_product_origins VALUES(?,NULL,?,?)",
                     (artifact["document_key"], file_id, json.dumps(artifact, sort_keys=True)))
        row = conn.execute("SELECT product_id FROM studio_product_origins WHERE document_key=?", (artifact["document_key"],)).fetchone()
        if product_id:
            if row[0] and row[0] != product_id:
                raise ValueError("This Studio origin already belongs to a different product. Review the catalogue.")
            conn.execute("UPDATE studio_product_origins SET product_id=? WHERE document_key=?", (product_id, artifact["document_key"]))


def _launch_key(product_id, title):
    return hashlib.sha256((product_id+"\n"+title).encode("utf-8")).hexdigest()


def _existing_launches(personal, product_id, titles):
    from utils import prism_workspace as workspace
    rows = _personal_rows(personal, "launch") if titles else []
    with workspace.database() as conn:
        origins = dict(conn.execute("SELECT task_key,launch_id FROM studio_launch_origins WHERE product_id=?", (product_id,)).fetchall())
    result = {}
    for title in titles:
        key = _launch_key(product_id, title)
        if key in origins:
            found = next((row for row in rows if row["id"] == origins[key] and row["payload"]["product_id"] == product_id), None)
            if not found:
                raise personal.PersonalError("An earlier Studio launch task was removed or relinked. Review it in Income instead of silently recreating it.", 409, "launch_origin_conflict")
        else:
            marker = "[u1-studio-launch:"+key+"]"
            matches = [row for row in rows if row["payload"]["product_id"] == product_id and
                       (row["title"] == title or marker in row["payload"].get("notes", ""))]
            if len(matches) > 1:
                raise ValueError("Multiple launch tasks match this review. Resolve them in Income first.")
            found = matches[0] if matches else None
        result[title] = found
    return result


def _bind_launch(product_id, title, launch_id):
    from utils import prism_workspace as workspace
    with workspace.database() as conn:
        conn.execute("INSERT OR IGNORE INTO studio_launch_origins VALUES(?,?,?)",
                     (product_id, _launch_key(product_id, title), launch_id))


def _personal_rows(personal, kind):
    rows, offset = [], 0
    while True:
        result = personal.snapshot({"kind":kind,"archived":"all","limit":"200","offset":str(offset)})
        rows.extend(result["records"])
        if not result["has_more"]:
            return rows
        offset += len(result["records"])
        if offset >= personal.MAX_RECORDS:
            raise ValueError("Catalogue duplicate checks exceeded the record limit")


def _handoff_existing(personal, artifact, file_id):
    marker = "[u1-studio-product:"+artifact["document_key"]+"]"
    origin = _origin(artifact)
    matches = []
    for row in _personal_rows(personal,"product"):
        payload = row["payload"]
        if origin and origin["product_id"]:
            matched = row["id"] == origin["product_id"]
        else:
            candidates = {file_id, origin["seed_file_id"] if origin else file_id}
            matched = marker in payload.get("notes", "") or any(v["file_id"] in candidates and v["version"] == artifact["version"] for v in payload.get("versions", []))
        if matched:
            matches.append(row)
    if origin and origin["product_id"] and not matches:
        raise ValueError("The product for this Studio origin was removed. Review the catalogue before creating a replacement.")
    if len(matches) > 1:
        raise ValueError("More than one catalogue record already matches this artifact. Resolve those records in Income before handing off.")
    existing = matches[0] if matches else None
    if existing and existing["archived"]:
        raise ValueError("This product is archived. Restore it in Income instead of creating a duplicate.")
    if existing and existing["payload"]["current_version"] != artifact["version"]:
        raise ValueError("The existing product now has a different current version. Review its versions in Income; Studio will not overwrite them.")
    return marker, existing


def _handoff(body):
    from utils import prism_workspace as workspace
    from utils import u1_personal_core as personal
    review = body.get("action") == "handoff-review"
    allowed = {"action","file_id","receipt"}
    if not review:
        allowed |= {"reviewed","product","checklist","expected_product_version"}
    _object(body, allowed, "Catalogue handoff")
    if not review and body.get("reviewed") is not True:
        raise ValueError("Review the saved artifact and explicitly approve the catalogue handoff first.")
    # The application's shared reentrant lock serializes Studio retries and
    # concurrent requests with PRISM/personal actions. Records themselves remain
    # in the existing personal store and are created through its public action.
    with workspace.LOCK, _provenance_lock(workspace):
        artifact, saved = _handoff_file(body)
        marker, existing = _handoff_existing(personal, artifact, saved["id"])
        proposed = {"title":existing["title"] if existing else artifact["title"],
                    "audience":existing["payload"]["audience"] if existing else artifact["audience"],
                    "description":existing["payload"]["description"] if existing else artifact["description"]}
        if review:
            return {"success":True,"file":saved,"artifact":artifact,"product":proposed,"existing":existing,
                    "expected_product_version":existing["version"] if existing else 0,"publishes":False}
        product = _object(body.get("product"), {"title","audience","description"}, "Product")
        product = {key:_text(product.get(key,""),limit,"Product "+key,required=key == "title",single=key == "title")
                   for key,limit in (("title",160),("audience",300),("description",4000))}
        checklist = body.get("checklist",[])
        if not isinstance(checklist,list) or len(checklist) > 6:
            raise ValueError("Approve at most six launch checklist tasks")
        checklist = [_text(value,160,"Launch task",True,True) for value in checklist]
        if len(set(checklist)) != len(checklist):
            raise ValueError("Launch checklist tasks must be distinct")
        expected = body.get("expected_product_version")
        if type(expected) is not int or expected < 0:
            raise ValueError("Use the catalogue version returned by the handoff review")
        reused = existing is not None
        existing_tasks = _existing_launches(personal, existing["id"], checklist) if existing else {}
        version_link = {"version":artifact["version"],"file_id":saved["id"],
                        "notes":f"Studio artifact SHA-256: {artifact['sha256']}\nSource: {SOURCE}\n{artifact['content_source']}"}
        if existing:
            payload = existing["payload"]
            linked = any(v["file_id"] == saved["id"] and v["version"] == artifact["version"] for v in payload["versions"])
            retry = linked and product == proposed and all(existing_tasks.get(title) for title in checklist)
            if expected != existing["version"] and not (expected <= existing["version"] and retry):
                raise personal.PersonalError("The product changed after review. Review the latest catalogue record before continuing.",409,"version_conflict")
            if product != proposed:
                raise ValueError("Edit existing product details in Income. This handoff preserves the reviewed catalogue record.")
            changes = {}
            if not linked:
                changes["versions"] = payload["versions"]+[version_link]
            record = personal.action({"action":"update","id":existing["id"],"expected_version":existing["version"],"payload":changes})["record"] if changes else existing
        else:
            if expected != 0:
                raise personal.PersonalError("The reviewed product is no longer available. Review the handoff again.",409,"version_conflict")
            _bind_origin(artifact, saved["id"])
            record = personal.action({"action":"create","kind":"product","title":product["title"],"payload":{
                "status":"review","audience":product["audience"],"description":product["description"],
                "current_version":artifact["version"],"versions":[version_link],
                "notes":"Created from an operator-reviewed Studio file. Private catalogue record; no publication performed."}})["record"]
        _bind_origin(artifact, saved["id"], record["id"])
        launches, pending, warnings = [], [], []
        for title in checklist:
            found = existing_tasks.get(title)
            if found:
                _bind_launch(record["id"], title, found["id"])
                if found["archived"]:
                    warnings.append("An approved launch task is archived; restore it in Income: "+title)
                launches.append(found)
                continue
            try:
                launch = personal.action({"action":"create","kind":"launch","title":title,"payload":{
                    "product_id":record["id"],"status":"backlog","notes":"Operator-approved planning task. No publication or account action is scheduled."}})["record"]
                _bind_launch(record["id"], title, launch["id"])
                launches.append(launch)
            except personal.PersonalError as error:
                pending.append(title)
                warnings.append(str(error))
        return {"success":True,"product":record,"reused":reused,"file_id":saved["id"],"launches":launches,
                "pending_checklist":pending,"warnings":warnings,"partial":bool(pending),"publishes":False}


def _preview(raw, page):
    if pdfium is None:
        raise RuntimeError("PDF page-image preview needs pypdfium2 in the application runtime; open the generated PDF in a compatible reader")
    if type(page) is not int or not 1 <= page <= MAX_PAGES:
        raise ValueError("Choose a valid one-based PDF page")
    # PDFium is not thread-safe. Only PDFs signed by this process reach it.
    with _PREVIEW_LOCK:
        with pdfium.PdfDocument(raw) as document:
            if page > len(document):
                raise ValueError("That PDF page does not exist")
            pdf_page = document[page-1]
            try:
                bitmap = pdf_page.render(scale=1.5)
                try:
                    image = bitmap.to_pil()
                    output = io.BytesIO()
                    image.save(output, format="PNG")
                finally:
                    bitmap.close()
            finally:
                pdf_page.close()
    result = _artifact(output.getvalue(), f"page-{page}.png", "image/png")
    result["page"] = page
    return result


def _signed_preview(body):
    _object(body, {"action", "content", "signature", "page"}, "Preview request")
    content, signature = body.get("content"), body.get("signature")
    if not isinstance(content, str) or len(content) > (MAX_PREVIEW_PDF+2)//3*4:
        raise ValueError("Preview PDF exceeds the 8 MB limit")
    if not isinstance(signature, str) or not re.fullmatch(r"[a-f0-9]{64}", signature):
        raise ValueError("Generate a new PDF before requesting a preview")
    raw = base64.b64decode(content, validate=True)
    if len(raw) > MAX_PREVIEW_PDF or not hmac.compare_digest(signature, hmac.new(_PREVIEW_KEY, raw, hashlib.sha256).hexdigest()):
        raise ValueError("Preview signature is invalid; generate a new PDF")
    return {"success": True, **_preview(raw, body.get("page"))}


def create(body):
    if isinstance(body,dict) and body.get("action") in ("handoff-review","handoff"):
        return _handoff(body)
    if isinstance(body, dict) and body.get("action") == "preview":
        return _signed_preview(body)
    _object(body, {"action", "document"}, "Request")
    action = body.get("action", "render")
    if not isinstance(action, str) or action not in {"render", "artwork", "bundle"}:
        raise ValueError("Choose render, artwork or bundle")
    doc = validate_document(body.get("document"))
    if action == "bundle" and (not doc["instructions"].strip() or not doc["licence"].strip()):
        raise ValueError("Supply your own instructions and licence before creating a bundle")
    stem = _stem(doc)
    metadata = _metadata(doc)
    art = artwork(doc)
    artifacts = {key: _artifact(raw, stem + "-" + key + ".svg", "image/svg+xml") for key, raw in art.items()}
    if action == "artwork":
        return {"success": True, "artifacts": artifacts, "metadata": metadata, "document": doc}
    if canvas is None:
        raise RuntimeError("PDF creation needs reportlab in the U1 OS runtime. Existing basic printables remain available; no dependency was installed.")
    layout = _Layout(doc)
    pdf = layout.build()
    if len(pdf) > MAX_PREVIEW_PDF:
        raise ValueError("Generated PDF exceeds the 8 MB limit")
    result = {"success": True, "metadata": metadata, "pages": layout.page, "section_pages": layout.section_pages,
              "fields": layout.fields, "fillable": doc["fillable"], "hyperlinks": True, "artifacts": artifacts}
    if action == "render":
        result.update(_artifact(pdf, stem + ".pdf", "application/pdf"))
        result["handoff_receipt"] = _handoff_receipt(doc,result)
        result["preview_signature"] = hmac.new(_PREVIEW_KEY, pdf, hashlib.sha256).hexdigest()
        result["preview"] = _preview(pdf, 1) if pdfium is not None else None
        return result
    members = {stem + ".pdf": pdf, stem + "-cover.svg": art["cover"], stem + "-mockup.svg": art["mockup"],
               "INSTRUCTIONS.txt": doc["instructions"].encode("utf-8"), "LICENCE.txt": doc["licence"].encode("utf-8"),
               "metadata.json": json.dumps(metadata, indent=2, ensure_ascii=False).encode("utf-8"),
               "README.txt": ("Created locally in U1 OS Digital Studio.\nOpen the PDF in a form-capable reader to complete and save responses.\nContents links and PDF bookmarks navigate between sections.\nSVG cover and mockup are original local vector layouts, not AI images.\nRead INSTRUCTIONS.txt and LICENCE.txt supplied by the operator.\nNo account sync, sale, AI content generation or external upload was performed.\n").encode("utf-8")}
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in members.items():
            archive.writestr(name, raw)
    result.update(_artifact(output.getvalue(), stem + ".zip", "application/zip"))
    result["handoff_receipt"] = _handoff_receipt(doc,result)
    result["members"] = list(members)
    return result


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def handle_request(handler):
    if handler.path.split("?", 1)[0] != ROUTE:
        return False
    from utils.u1_safety import _reply
    if not handler.integration_request_allowed():
        _reply(handler, {"success": False, "error": "Local same-origin request required"}, 403)
        return True
    if handler.command == "GET":
        _reply(handler, capabilities())
        return True
    if handler.command != "POST":
        _reply(handler, {"success": False, "error": "Use GET or POST"}, 405)
        return True
    supplied = handler.headers.get("X-U1-CSRF", "")
    if not isinstance(supplied, str) or not hmac.compare_digest(supplied.encode("utf-8"), integrations_hub.CSRF_TOKEN.encode("utf-8")):
        _reply(handler, {"success": False, "error": "Reload the workspace for local authorisation"}, 403)
        return True
    if handler.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
        _reply(handler, {"success": False, "error": "Use application/json"}, 415)
        return True
    try:
        if handler.headers.get("Transfer-Encoding"):
            raise ValueError("Use a bounded Content-Length")
        length = int(handler.headers.get("Content-Length", "0"))
        if not 0 < length <= MAX_PREVIEW_REQUEST:
            raise ValueError("Request exceeds the bounded request size")
        raw = handler.rfile.read(length)
        if len(raw) != length:
            raise ValueError("Incomplete request body")
        body = json.loads(raw, object_pairs_hook=_unique_pairs)
        if length > MAX_REQUEST and (not isinstance(body, dict) or body.get("action") != "preview"):
            raise ValueError("Document requests must be at most 262144 bytes")
        _reply(handler, create(body))
    except (ValueError, TypeError, RecursionError) as exc:
        message = "Request nesting is too deep" if isinstance(exc, RecursionError) else str(exc)
        _reply(handler, {"success": False, "error": message}, getattr(exc,"status",400))
    except RuntimeError as exc:
        _reply(handler, {"success": False, "error": str(exc)}, 503)
    except (OSError, sqlite3.Error):
        _reply(handler, {"success": False, "error": "Studio storage verification did not complete. Refresh before retrying; an earlier approved record may already be saved."}, 503)
    return True
