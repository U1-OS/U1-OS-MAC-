"""Bounded, offline printable templates. No AI, remote assets or file writes."""
import base64
import calendar
import math
from datetime import date

TEMPLATES = {"daily", "weekly", "workout", "meals", "calendar", "colouring"}


def text(value, maximum=100):
    value = str(value or "")[:maximum].encode("ascii", "replace").decode("ascii")
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").replace("\n", " ").replace("\r", " ")


class Page:
    def __init__(self, title, subtitle):
        self.ops = ["0.08 0.14 0.21 RG", "0.8 w"]
        self.label(40, 794, title, 23, True)
        self.label(40, 772, subtitle, 9)
        self.line(40, 756, 555, 756)
        self.label(40, 26, "U1 OS / Personal printable / Created locally", 8)

    def label(self, x, y, value, size=10, bold=False):
        self.ops.append(f"BT /{'F2' if bold else 'F1'} {size} Tf {x:.2f} {y:.2f} Td ({text(value)}) Tj ET")

    def line(self, x, y, end_x, end_y):
        self.ops.append(f"{x:.2f} {y:.2f} m {end_x:.2f} {end_y:.2f} l S")

    def box(self, x, y, w, h, title="", rows=0):
        self.ops.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re S")
        if title:
            self.label(x+10, y+h-20, title, 10, True)
        for i in range(rows):
            yy = y+h-43-i*20
            if yy > y+8:
                self.line(x+10, yy, x+w-10, yy)


def _pdf(pages):
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>"]
    children = []
    for page in pages:
        page_id = len(objects)+1
        stream_id = page_id+1
        children.append(f"{page_id} 0 R")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {stream_id} 0 R >>".encode())
        content = "\n".join(page.ops).encode("ascii")
        objects.append(f"<< /Length {len(content)} >>\nstream\n".encode()+content+b"\nendstream")
    objects[1] = f"<< /Type /Pages /Count {len(pages)} /Kids [{' '.join(children)}] >>".encode()
    result = bytearray(b"%PDF-1.4\n%U1OS\n")
    offsets = [0]
    for number, item in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(f"{number} 0 obj\n".encode()+item+b"\nendobj\n")
    xref = len(result)
    result.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        result.extend(f"{offset:010d} 00000 n \n".encode())
    result.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(result)


def create(body):
    kind = body.get("template", "weekly")
    if kind not in TEMPLATES:
        raise ValueError("Choose one of the six printable templates.")
    count = body.get("pages", 1)
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 12:
        raise ValueError("Create between 1 and 12 pages at a time.")
    today = date.today()
    year, month = body.get("year", today.year), body.get("month", today.month)
    if type(year) is not int or type(month) is not int or not 2020 <= year <= 2100 or not 1 <= month <= 12:
        raise ValueError("Choose a valid month and a year from 2020 to 2100.")
    title = str(body.get("title") or kind.replace("colouring", "Colouring studio").title())[:58]
    pages = []
    for index in range(count):
        p = Page(title, f"{kind.upper()} / A4 / Page {index+1} of {count}")
        if kind == "daily":
            p.box(40, 570, 515, 168, "TOP THREE PRIORITIES", 5)
            p.box(40, 225, 245, 325, "SCHEDULE", 13)
            p.box(305, 225, 250, 325, "TASKS", 13)
            p.box(40, 55, 515, 150, "NOTES AND REFLECTION", 5)
        elif kind in {"weekly", "meals"}:
            for i, day in enumerate(calendar.day_name):
                p.box(40, 738-(i+1)*82, 515, 74, day.upper() + (" / BREAKFAST - LUNCH - DINNER" if kind == "meals" else ""), 2)
            p.box(40, 55, 515, 95, "SHOPPING LIST" if kind == "meals" else "NEXT WEEK", 2)
        elif kind == "workout":
            p.box(40, 625, 515, 113, "SESSION / DATE / GOAL", 3)
            for i, heading in enumerate(["EXERCISE", "SETS / REPS", "LOAD / NOTES"]):
                p.box(40+i*172, 220, 171, 385, heading, 16)
            p.box(40, 55, 515, 145, "RECOVERY / HOW THE SESSION FELT", 5)
        elif kind == "calendar":
            p.label(40, 720, f"{calendar.month_name[month]} {year}", 18, True)
            weeks = calendar.monthcalendar(year, month)
            cell_w, cell_h = 515/7, 550/len(weeks)
            for day in range(7):
                p.label(44+day*cell_w, 693, list(calendar.day_abbr)[day], 9, True)
            for week, days in enumerate(weeks):
                for day, value in enumerate(days):
                    p.box(40+day*cell_w, 670-(week+1)*cell_h, cell_w, cell_h, str(value) if value else "")
            p.box(40, 55, 515, 52, "MONTHLY INTENTION")
        else:
            # Original geometric line art, not downloaded or AI-generated.
            for ring in range(1, 8):
                radius = ring*29
                for petal in range(16):
                    angle = (petal/16)*math.tau+index*0.09
                    points = []
                    for step in range(25):
                        a = step/24*math.tau
                        rr = radius+11*math.cos(a)
                        aa = angle+0.12*math.sin(a)
                        points.append((297+rr*math.cos(aa), 425+rr*math.sin(aa)))
                    p.ops.append(" ".join(f"{x:.2f} {y:.2f} {'m' if i == 0 else 'l'}" for i,(x,y) in enumerate(points))+" h S")
            p.label(40, 90, "Make space for colour. Choose your own palette.", 10)
        pages.append(p)
    content = _pdf(pages)
    return {"success": True, "filename": f"u1-{kind}.pdf", "mime": "application/pdf", "content": base64.b64encode(content).decode(), "pages": count,
            "notice": "Static A4 printable. Not an interactive form; no AI or paid provider was used."}
