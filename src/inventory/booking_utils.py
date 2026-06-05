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
    rooms_list = format_room_list(rooms_or_instance)
    
    # Check if instance is a model with parsed_alternative_slots
    alt_slots = []
    if hasattr(rooms_or_instance, 'parsed_alternative_slots'):
        alt_slots = rooms_or_instance.parsed_alternative_slots
    
    sl = timezone.localtime(start_dt)
    el = timezone.localtime(end_dt)
    
    date_time_str = f"{sl.strftime('%A, %d %B %Y')}, {sl.strftime('%I:%M %p')} – {el.strftime('%I:%M %p')}"
    if alt_slots:
        slots_str_list = []
        for i, slot in enumerate(alt_slots, 1):
            ssl = timezone.localtime(slot['start'])
            sel = timezone.localtime(slot['end'])
            slots_str_list.append(f"\n               Slot {i}: {ssl.strftime('%d %b %Y, %I:%M %p')} – {sel.strftime('%I:%M %p')}")
        date_time_str += "".join(slots_str_list)
        
    details = (
        f"\n  Room(s)    : {rooms_list}"
        f"\n  Faculty    : {faculty_name}"
        f"\n  Schedule   : {date_time_str}"
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
            # Detect tables on this page to exclude their bounding boxes from text extraction
            tables = page.find_tables()
            bboxes = [table.bbox for table in tables]

            def not_within_bboxes(obj):
                """Check if the object is NOT in any of the table's bbox."""
                if "top" not in obj or "bottom" not in obj or "x0" not in obj or "x1" not in obj:
                    return True
                v_mid = (obj["top"] + obj["bottom"]) / 2
                h_mid = (obj["x0"] + obj["x1"]) / 2
                for bbox in bboxes:
                    x0, top, x1, bottom = bbox
                    if (h_mid >= x0) and (h_mid < x1) and (v_mid >= top) and (v_mid < bottom):
                        return False
                return True

            if bboxes:
                # Filter out elements inside the table boundary
                filtered_page = page.filter(not_within_bboxes)
                page_text = (filtered_page.extract_text() or "").strip()
            else:
                page_text = (page.extract_text() or "").strip()

            if page_text:
                for paragraph in [part.strip() for part in re.split(r"\n\s*\n", page_text) if part.strip()]:
                    blocks.append({"type": "paragraph", "text": paragraph})

            raw_tables = page.extract_tables() or []
            for table in raw_tables:
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


def check_slots_conflict(selected_rooms, slots, exclude_booking_pk=None, exclude_request_pk=None):
    from django.db.models import Q
    from inventory.models import RoomBooking, RoomBookingRequest
    from django.utils import timezone
    from django.utils.dateparse import parse_datetime
    import json

    def overlaps(s1_start, s1_end, s2_start, s2_end):
        return s1_start < s2_end and s2_start < s1_end

    # Check self-overlap in slots
    for i in range(len(slots)):
        for j in range(i + 1, len(slots)):
            if overlaps(slots[i][0], slots[i][1], slots[j][0], slots[j][1]):
                return f"Duplicate or overlapping slots detected in your request: {slots[i][0].strftime('%d %b %Y, %I:%M %p')} overlaps with {slots[j][0].strftime('%d %b %Y, %I:%M %p')}."

    # Fetch active bookings for these rooms
    bookings = RoomBooking.objects.filter(
        Q(room__in=selected_rooms) | Q(rooms__in=selected_rooms)
    ).exclude(status='cancelled')
    if exclude_booking_pk:
        bookings = bookings.exclude(pk=exclude_booking_pk)

    # Fetch pending requests for these rooms
    requests = RoomBookingRequest.objects.filter(
        Q(room__in=selected_rooms) | Q(rooms__in=selected_rooms),
        status='pending'
    )
    if exclude_request_pk:
        requests = requests.exclude(pk=exclude_request_pk)

    for b in bookings:
        b_slots = [(b.start_datetime, b.end_datetime)]
        if b.alternative_slots:
            try:
                extra = json.loads(b.alternative_slots)
                for slot in extra:
                    s_dt = parse_datetime(slot['start'])
                    e_dt = parse_datetime(slot['end'])
                    if s_dt and e_dt:
                        if timezone.is_naive(s_dt):
                            s_dt = timezone.make_aware(s_dt)
                        if timezone.is_naive(e_dt):
                            e_dt = timezone.make_aware(e_dt)
                        b_slots.append((s_dt, e_dt))
            except Exception:
                pass
        
        for s_start, s_end in slots:
            for b_start, b_end in b_slots:
                if overlaps(s_start, s_end, b_start, b_end):
                    return f"Room is already booked for slot {s_start.strftime('%d %b %Y, %I:%M %p')} to {s_end.strftime('%I:%M %p')}."

    for r in requests:
        r_slots = [(r.start_datetime, r.end_datetime)]
        if r.alternative_slots:
            try:
                extra = json.loads(r.alternative_slots)
                for slot in extra:
                    s_dt = parse_datetime(slot['start'])
                    e_dt = parse_datetime(slot['end'])
                    if s_dt and e_dt:
                        if timezone.is_naive(s_dt):
                            s_dt = timezone.make_aware(s_dt)
                        if timezone.is_naive(e_dt):
                            e_dt = timezone.make_aware(e_dt)
                        r_slots.append((s_dt, e_dt))
            except Exception:
                pass
        
        for s_start, s_end in slots:
            for r_start, r_end in r_slots:
                if overlaps(s_start, s_end, r_start, r_end):
                    return f"Room has a pending request for slot {s_start.strftime('%d %b %Y, %I:%M %p')} to {s_end.strftime('%I:%M %p')}."

    return None
