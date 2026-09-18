from __future__ import annotations

import io
from copy import deepcopy
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn

from weekly_deck import from_legacy, section_lines, week_labels

MASTER_PATH = Path(__file__).resolve().parent / "templates" / "weekly_member_master.pptx"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
LINES_WITH_EVENTS = 16
LINES_WITHOUT_EVENTS = 28


def _walk_shapes(shapes):
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _walk_shapes(shape.shapes)
        else:
            yield shape


def _write_paragraphs(cell, lines):
    tx_body = cell.text_frame._txBody
    existing = tx_body.findall(qn("a:p"))
    if not existing:
        cell.text_frame.text = "\n".join(lines or [""])
        return
    template = deepcopy(existing[0])
    for node in existing:
        tx_body.remove(node)
    rows = lines or [""]
    for line in rows:
        paragraph = deepcopy(template)
        runs = paragraph.findall(qn("a:r"))
        if runs:
            first = runs[0]
            text_node = first.find(qn("a:t"))
            if text_node is None:
                text_node = first.makeelement(qn("a:t"), {})
                first.append(text_node)
            text_node.text = line
            text_node.set(XML_SPACE, "preserve")
            for extra in runs[1:]:
                paragraph.remove(extra)
        tx_body.append(paragraph)


def _delete_shape(shape):
    shape._element.getparent().remove(shape._element)


def _set_textbox(shape, value):
    paragraph = shape.text_frame.paragraphs[0]
    if paragraph.runs:
        paragraph.runs[0].text = value
        for extra in paragraph.runs[1:]:
            extra.text = ""
    else:
        paragraph.add_run().text = value


def _fill_cover(slide, deck):
    for shape in _walk_shapes(slide.shapes):
        if shape.has_text_frame and shape.text_frame.text.strip().startswith("Center"):
            _set_textbox(
                shape, f"Center : {deck.get('center') or deck.get('author') or ''}".rstrip()
            )
        if not shape.has_table:
            continue
        table = shape.table
        if len(table.rows) < 2 or len(table.columns) < 2:
            continue
        if "보고일자" not in table.cell(0, 0).text_frame.text:
            continue
        _write_paragraphs(table.cell(0, 1), [deck.get("report_date") or ""])
        if "센터장" in table.cell(1, 0).text_frame.text:
            _write_paragraphs(table.cell(1, 0), ["작성자"])
        _write_paragraphs(table.cell(1, 1), [deck.get("author") or ""])


def _fill_notices(slide, notices):
    blocks = []
    for index, notice in enumerate(notices or [], start=1):
        title = str(notice.get("title") or "").strip()
        body = [str(line).strip() for line in notice.get("body") or [] if str(line).strip()]
        if not title and not body:
            continue
        blocks.append(f"{index}. {title}" if title else f"{index}.")
        blocks.extend(f"   - {line}" for line in body)
    if not blocks:
        blocks = ["없음"]
    for shape in _walk_shapes(slide.shapes):
        if not shape.has_table:
            continue
        table = shape.table
        if "공지" not in table.cell(0, 0).text_frame.text:
            continue
        body_row = 1 if len(table.rows) > 1 else 0
        _write_paragraphs(table.cell(body_row, 0), blocks)
        if len(table.columns) > 1:
            _write_paragraphs(table.cell(body_row, 1), [""])
        return True
    return True


def _fill_events(table, month_events, next_events):
    data_rows = list(range(1, len(table.rows)))
    for offset, row in enumerate(data_rows):
        month = (month_events or [])[offset] if offset < len(month_events or []) else {}
        nxt = (next_events or [])[offset] if offset < len(next_events or []) else {}
        _write_paragraphs(table.cell(row, 0), [str(month.get("when") or "")])
        _write_paragraphs(table.cell(row, 1), [str(month.get("title") or "")])
        if len(table.columns) > 3:
            _write_paragraphs(table.cell(row, 2), [str(nxt.get("when") or "")])
            _write_paragraphs(table.cell(row, 3), [str(nxt.get("title") or "")])


def _expand_status_table(slide, event_shape):
    status = None
    for shape in slide.shapes:
        if not shape.has_table:
            continue
        header = shape.table.cell(0, 0).text_frame.text
        if "진행" in header or "향후" in header:
            status = shape
            break
    if status is None:
        return
    top = event_shape.top
    extra = event_shape.height
    _delete_shape(event_shape)
    status.top = top
    status.height = status.height + extra


def paginate_sections(sections, max_lines):
    pages = []
    current = []
    used = 0
    for section in sections or []:
        title = str(section.get("title") or "").strip()
        items = [str(item).strip() for item in section.get("items") or [] if str(item).strip()]
        if not title and not items:
            continue
        remaining = items
        first = True
        while remaining or first:
            first = False
            room = max_lines - used - 1
            if room < 1:
                if current:
                    pages.append(current)
                current = []
                used = 0
                continue
            take = remaining[:room]
            remaining = remaining[room:]
            current.append({"title": title, "items": take})
            used += 1 + len(take)
            if remaining:
                pages.append(current)
                current = []
                used = 0
    if current:
        pages.append(current)
    return pages or [[]]


def duplicate_slide(prs, index):
    source = prs.slides[index]
    dest = prs.slides.add_slide(source.slide_layout)
    for shape in list(dest.shapes):
        shape._element.getparent().remove(shape._element)
    tree = dest.shapes._spTree
    for shape in source.shapes:
        tree.insert_element_before(deepcopy(shape._element), "p:extLst")
    return dest


def _fill_status_pair(slide, *, done_label, next_label, done_sections, next_sections, events):
    event_shape = None
    status_shape = None
    for shape in _walk_shapes(slide.shapes):
        if not shape.has_table:
            continue
        header = shape.table.cell(0, 0).text_frame.text
        if "금월" in header:
            event_shape = shape
        elif "진행" in header or "향후" in header:
            status_shape = shape
    month_events = [e for e in (events[0] or []) if str(e.get("when") or e.get("title") or "").strip()]
    next_events = [e for e in (events[1] or []) if str(e.get("when") or e.get("title") or "").strip()]
    has_events = bool(month_events or next_events)
    if event_shape is not None and has_events:
        _fill_events(event_shape.table, month_events, next_events)
    elif event_shape is not None:
        _expand_status_table(slide, event_shape)
        status_shape = None
        for shape in _walk_shapes(slide.shapes):
            if shape.has_table and (
                "진행" in shape.table.cell(0, 0).text_frame.text
                or "향후" in shape.table.cell(0, 0).text_frame.text
            ):
                status_shape = shape
    if status_shape is None:
        return
    table = status_shape.table
    _write_paragraphs(table.cell(0, 0), [f"진행 현황 ({done_label})"])
    _write_paragraphs(table.cell(0, 1), [f"향후일정 ({next_label})"])
    _write_paragraphs(table.cell(1, 0), section_lines(done_sections))
    _write_paragraphs(table.cell(1, 1), section_lines(next_sections))


def _notice_slide_index(prs):
    for index, slide in enumerate(prs.slides):
        for shape in slide.shapes:
            if shape.has_text_frame and "공지" in shape.text_frame.text:
                return index
            if shape.has_table and "공지" in shape.table.cell(0, 0).text_frame.text:
                return index
    return None


def _status_slide_index(prs):
    for index, slide in enumerate(prs.slides):
        for shape in slide.shapes:
            if shape.has_table and "진행" in shape.table.cell(0, 0).text_frame.text:
                return index
    return None


def _delete_slide(prs, index):
    sld_id_lst = prs.slides._sldIdLst
    children = list(sld_id_lst)
    sld_id_lst.remove(children[index])
    rId = children[index].get(qn("r:id"))
    if rId:
        try:
            prs.part.drop_rel(rId)
        except Exception:
            pass


def fill_weekly_pptx(report: dict) -> bytes:
    if not MASTER_PATH.is_file():
        raise FileNotFoundError(f"PPT 마스터가 없습니다: {MASTER_PATH}")
    selected = report.get("selectedDate") or []
    deck = from_legacy(
        report.get("report") or report,
        selected_dates=selected,
        member_name=str(report.get("memberName") or ""),
        team_name=str(report.get("teamName") or ""),
    )
    if selected:
        done_label, next_label = week_labels(selected)
        if not deck.get("week_label_done"):
            deck["week_label_done"] = done_label
        deck["week_label_next"] = next_label
    prs = Presentation(str(MASTER_PATH))
    if prs.slides:
        _fill_cover(prs.slides[0], deck)

    notices = [
        n
        for n in (deck.get("notices") or [])
        if str(n.get("title") or "").strip()
        or any(str(x).strip() for x in n.get("body") or [])
    ]
    notice_index = _notice_slide_index(prs)
    if notice_index is not None:
        _fill_notices(prs.slides[notice_index], notices)

    status_index = _status_slide_index(prs)
    if status_index is None:
        buf = io.BytesIO()
        prs.save(buf)
        return buf.getvalue()

    month_events = deck.get("month_events") or []
    next_events = deck.get("next_month_events") or []
    has_events = any(
        str(item.get("when") or item.get("title") or "").strip()
        for item in month_events + next_events
    )
    max_lines = LINES_WITH_EVENTS if has_events else LINES_WITHOUT_EVENTS
    done_pages = paginate_sections(deck.get("done") or [], max_lines)
    next_pages = paginate_sections(deck.get("next") or [], max_lines)
    page_count = max(len(done_pages), len(next_pages))
    while len(done_pages) < page_count:
        done_pages.append([])
    while len(next_pages) < page_count:
        next_pages.append([])

    status_slides = [prs.slides[status_index]]
    for _ in range(1, page_count):
        status_slides.append(duplicate_slide(prs, status_index))
    for page, slide in enumerate(status_slides):
        _fill_status_pair(
            slide,
            done_label=deck.get("week_label_done") or "",
            next_label=deck.get("week_label_next") or "",
            done_sections=done_pages[page],
            next_sections=next_pages[page],
            events=(month_events, next_events) if page == 0 else ([], []),
        )

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()
