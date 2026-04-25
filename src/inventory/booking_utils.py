import io
import os
import re

import pdfplumber
from django.utils import timezone


def room_label_sort_key(label):
    raw = (label or "").strip().lower()
    parts = re.findall(r"\d+|[a-z]+", raw)
    if not parts:
        return ((2, raw),)
    key = []
    for part in parts:
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part))
    return tuple(key)


def sort_rooms_iterable(rooms):
    return sorted(
        rooms,
        key=lambda room: (
            room_label_sort_key(getattr(room, "label", "")),
            (getattr(room, "room_name", "") or "").lower(),
            getattr(room, "pk", 0) or 0,
        ),
    )


def get_booking_rooms(instance):
    rooms = []

    if hasattr(instance, "rooms"):
        try:
            rooms = list(instance.rooms.all())
        except Exception:
            rooms = []

    primary_room = getattr(instance, "room", None)
    if primary_room and all(getattr(room, "pk", None) != primary_room.pk for room in rooms):
        rooms.append(primary_room)

    deduped = []
    seen = set()
    for room in rooms:
        room_id = getattr(room, "pk", None)
        if room_id in seen:
            continue
        seen.add(room_id)
        deduped.append(room)

    return sort_rooms_iterable(deduped)


def get_primary_room(instance):
    rooms = get_booking_rooms(instance)
    return rooms[0] if rooms else getattr(instance, "room", None)


def format_room_display(room):
    if not room:
        return "—"
    label = (getattr(room, "label", "") or "").strip()
    room_name = (getattr(room, "room_name", "") or "").strip()
    if label and room_name:
        return f"{label} - {room_name}"
    return label or room_name or "—"


def format_room_list(rooms_or_instance):
    if isinstance(rooms_or_instance, (list, tuple)):
        rooms = sort_rooms_iterable(list(rooms_or_instance))
    else:
        rooms = get_booking_rooms(rooms_or_instance)
    if not rooms:
        return "—"
    return ", ".join(format_room_display(room) for room in rooms)


def format_booking_details(rooms_or_instance, faculty_name, start_dt, end_dt, purpose, department=None):
    sl = timezone.localtime(start_dt)
    el = timezone.localtime(end_dt)
    details = (
        f"\n  Room(s)    : {format_room_list(rooms_or_instance)}"
        f"\n  Faculty    : {faculty_name}"
        f"\n  Date       : {sl.strftime('%A, %d %B %Y')}"
        f"\n  Time       : {sl.strftime('%I:%M %p')} – {el.strftime('%I:%M %p')}"
        f"\n  Purpose    : {purpose or '—'}"
    )
    if department is not None:
        details += f"\n  Department : {department or '—'}"
    return details


def _extract_docx_blocks(raw_bytes):
    import docx
    from docx.oxml.ns import qn
    import docx.table

    doc = docx.Document(io.BytesIO(raw_bytes))
    blocks = []
    for block in doc.element.body:
        tag = block.tag.split("}")[-1] if "}" in block.tag else block.tag
        if tag == "p":
            text = "".join(node.text or "" for node in block.iter() if node.tag == qn("w:t")).strip()
            if text:
                blocks.append({"type": "paragraph", "text": text})
        elif tag == "tbl":
            table = docx.table.Table(block, doc)
            rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
            if any(any(cell for cell in row) for row in rows):
                blocks.append({"type": "table", "rows": rows})
    return blocks


def _extract_pdf_blocks(raw_bytes):
    blocks = []
    with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
        for page in pdf.pages:
            page_text = (page.extract_text() or "").strip()
            if page_text:
                for paragraph in [part.strip() for part in re.split(r"\n\s*\n", page_text) if part.strip()]:
                    blocks.append({"type": "paragraph", "text": paragraph})

            tables = page.extract_tables() or []
            for table in tables:
                rows = []
                for row in table or []:
                    cleaned = [("" if cell is None else str(cell).strip()) for cell in row]
                    if any(cleaned):
                        rows.append(cleaned)
                if rows:
                    blocks.append({"type": "table", "rows": rows})
    return blocks


def extract_requirement_blocks_from_field(file_field):
    if not file_field or not getattr(file_field, "name", ""):
        return []

    name = file_field.name
    extension = os.path.splitext(name)[1].lower()
    file_field.seek(0)
    raw = file_field.read()

    if extension == ".pdf":
        return _extract_pdf_blocks(raw)
    return _extract_docx_blocks(raw)


def requirement_blocks_to_plain_text(blocks):
    lines = []
    for block in blocks or []:
        if block.get("type") == "paragraph":
            text = (block.get("text") or "").strip()
            if text:
                lines.append(text)
        elif block.get("type") == "table":
            for row in block.get("rows") or []:
                row_text = " | ".join((cell or "").strip() for cell in row if (cell or "").strip())
                if row_text:
                    lines.append(row_text)
    return "\n".join(lines).strip()


def get_requirements_payload(obj):
    inline_text = (getattr(obj, "requirements_text", "") or "").strip()
    if inline_text:
        return {
            "kind": "text",
            "title": "Requirements",
            "plain_text": inline_text,
            "blocks": [{"type": "paragraph", "text": inline_text}],
            "filename": None,
        }

    file_field = getattr(obj, "requirements_doc", None)
    if not file_field or not getattr(file_field, "name", ""):
        return {
            "kind": "none",
            "title": "Requirements",
            "plain_text": "",
            "blocks": [],
            "filename": None,
        }

    try:
        blocks = extract_requirement_blocks_from_field(file_field)
        plain_text = requirement_blocks_to_plain_text(blocks)
        return {
            "kind": "document",
            "title": "Requirements Document",
            "plain_text": plain_text,
            "blocks": blocks,
            "filename": file_field.name.split("/")[-1],
        }
    except Exception:
        return {
            "kind": "document",
            "title": "Requirements Document",
            "plain_text": "",
            "blocks": [],
            "filename": file_field.name.split("/")[-1],
        }
