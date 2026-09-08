"""Offline course workbooks and creator product pages. No synthetic AI output."""
import base64
import hmac
import json
import re
import textwrap
from datetime import date

from utils import integrations_hub


TEMPLATES = {
    "course": "Course workbook",
    "budget": "Personal budget planner",
    "habits": "Habit tracker",
    "content": "Content calendar",
    "product": "Digital product launch workbook",
}


def text_value(value, limit, default=""):
    if not isinstance(value, str):
        raise ValueError("Expected text fields")
    return value.strip()[:limit] or default


def pdf_text(value):
    return str(value).encode("ascii", "replace").decode("ascii").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_document(body):
    template = body.get("template", "course")
    if template not in TEMPLATES:
        raise ValueError("Choose a supported workbook template")
    title = text_value(body.get("title", ""), 80, TEMPLATES[template])
    audience = text_value(body.get("audience", ""), 160, "Define your audience")
    outline = text_value(body.get("outline", ""), 6000)
    sections = [line.strip(" -\t")[:160] for line in outline.splitlines() if line.strip()][:10]
    if not sections:
        sections = {
            "course": ["Define the learner outcome", "Core concepts", "Guided practice", "Independent activity", "Reflection and next steps"],
            "budget": ["Income and fixed costs", "Flexible spending", "Savings goals", "Monthly review"],
            "habits": ["Habits and intentions", "Weekly habit check-in", "What helped and what changed"],
            "content": ["Audience and content pillars", "Weekly publishing plan", "Production checklist", "Actual performance review"],
            "product": ["Audience problem", "Offer and deliverables", "Production plan", "Pricing assumptions", "Quality and rights review", "Launch checklist"],
        }[template]
    pages = []
    commands = []

    def begin_page(continued=False):
        nonlocal commands
        title_lines = textwrap.wrap(title, width=31)
        bottom = 798-len(title_lines)*22
        commands = [f"0.08 0.17 0.24 rg 0 {bottom} 595 {842-bottom} re f", "1 1 1 rg"]
        for row, value in enumerate(title_lines):
            commands.append(f"BT /F1 16 Tf 42 {810-row*22} Td ({pdf_text(value)}) Tj ET")
        commands.append(f"BT /F1 9 Tf 42 {bottom+13} Td ({pdf_text(TEMPLATES[template])}) Tj ET")
        commands.append("0.08 0.17 0.24 rg")
        if continued:
            commands.append(f"BT /F1 9 Tf 42 {bottom-28} Td (Continued) Tj ET")
        return bottom-52 if continued else bottom-30

    def finish_page():
        commands.append("0.3 0.4 0.47 rg")
        footer = "U1 OS | Created locally | " + date.today().isoformat() + " | " + str(len(pages)+1)
        commands.append(f"BT /F1 8 Tf 42 30 Td ({pdf_text(footer)}) Tj ET")
        pages.append("\n".join(commands).encode("ascii"))

    def room(y, height):
        if y-height < 64:
            finish_page()
            return begin_page(True)
        return y

    def words(content, x, y, size=11, width=75):
        # Helvetica's widest ASCII glyph is below 1.02 em. This conservative
        # limit keeps long unbroken titles on the page without extra packages.
        width = min(width, max(1, int((553-x)/(size*1.02))))
        lines = textwrap.wrap(content, width=width, break_long_words=True) or [""]
        for line in lines:
            y = room(y, size+6)
            commands.append(f"BT /F1 {size} Tf {x} {y} Td ({pdf_text(line)}) Tj ET")
            y -= size + 6
        return y

    def line(x, y, end):
        commands.append(f"0.76 0.82 0.87 RG 0.5 w {x} {y} m {end} {y} l S")

    for index, section in enumerate(["Your workbook"] + sections):
        y = words(section, 42, begin_page(), 21, 42) - 14
        if index == 0:
            y = words("Audience: " + audience, 42, y, 11) - 12
            y = words("An editable planning structure for your own original content. This is a template, not an AI-written course or a financial forecast.", 42, y, 11) - 24
            words("CONTENTS", 42, y, 10)
            y -= 28
            for number, item in enumerate(sections, 1):
                y = room(y, len(textwrap.wrap(f"{number:02d}   {item}", width=41))*18+12)
                y = words(f"{number:02d}   {item}", 42, y, 12, 65) - 12
        else:
            prompts = {
                "course": ["Learning outcome", "Key ideas and examples", "Practice activity", "Reflection / assessment"],
                "budget": ["Record actual amounts and dates", "Planned / actual / difference", "Decisions and next steps"],
                "habits": ["Habit / cue / achievable action", "Mon     Tue     Wed     Thu     Fri     Sat     Sun", "Reflection, without judgement"],
                "content": ["Platform / audience / objective", "Topic / hook / format / publish date", "Rights, accessibility and review"],
                "product": ["Assumptions to validate", "Evidence and decisions", "Owner / next action / due date"],
            }[template]
            for prompt in prompts:
                y = room(y, 155)
                y = words(prompt, 42, y, 11)-7
                for _ in range(4):
                    line(42, y, 553)
                    y -= 21
                y -= 18
        finish_page()

    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for stream in pages:
        page_id = len(objects) + 1
        kids.append(f"{page_id} 0 R")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {page_id + 1} 0 R >>".encode("ascii"))
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream")
    objects[1] = ("<< /Type /Pages /Kids [" + " ".join(kids) + f"] /Count {len(pages)} >>").encode("ascii")
    result = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(f"{number} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    start = len(result)
    result.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        result.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    result.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode("ascii"))
    name = re.sub(r"[^a-zA-Z0-9_-]+", "-", title).strip("-")[:70] or "u1-workbook"
    return {"success": True, "filename": name + ".pdf", "mime": "application/pdf", "pages": len(pages),
            "content": base64.b64encode(result).decode("ascii"), "source": "Local vector PDF template", "ai_generated": False}


def handle_request(handler):
    if handler.path.split("?", 1)[0] != "/api/workspace/life-studio":
        return False
    from utils.u1_safety import _reply
    if not handler.integration_request_allowed():
        _reply(handler, {"success": False, "error": "Local same-origin request required"}, 403)
        return True
    if handler.command == "GET":
        _reply(handler, {"success": True, "templates": TEMPLATES, "image_provider": "not_connected", "notice": "Local templates are not AI-generated lessons or images."})
        return True
    if not hmac.compare_digest(handler.headers.get("X-U1-CSRF", ""), integrations_hub.CSRF_TOKEN):
        _reply(handler, {"success": False, "error": "Reload the workspace before creating a document"}, 403)
        return True
    try:
        length = int(handler.headers.get("Content-Length", "0"))
        if not 0 < length <= 16384:
            raise ValueError("Invalid request size")
        body = json.loads(handler.rfile.read(length))
        if not isinstance(body, dict):
            raise ValueError("Expected a JSON object")
        _reply(handler, make_document(body))
    except (ValueError, TypeError) as exc:
        _reply(handler, {"success": False, "error": str(exc)}, 400)
    return True
