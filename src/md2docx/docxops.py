from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
import re
import zipfile

from lxml import etree as ET
import yaml

from md2docx.bibliography import build_sources_customxml, load_sources_yaml


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

NS = {"w": W_NS, "r": R_NS}


@dataclass(frozen=True)
class _RelItem:
    old_id: str
    new_id: str
    rel_type: str
    target: str
    target_mode: str | None


def assemble_final_docx(
    *,
    template_docx: Path,
    body_docx: Path,
    output_docx: Path,
    meta_path: Path,
    sources_path: Path,
) -> None:
    meta = _load_yaml(meta_path) if meta_path.exists() else {}
    sources = load_sources_yaml(sources_path)

    with zipfile.ZipFile(template_docx, "r") as zt, zipfile.ZipFile(body_docx, "r") as zb:
        # Load XML parts
        tmpl_doc = _xml_from_bytes(zt.read("word/document.xml"))
        tmpl_rels = _xml_from_bytes(zt.read("word/_rels/document.xml.rels"))

        body_doc = _xml_from_bytes(zb.read("word/document.xml"))
        body_rels = _xml_from_bytes(zb.read("word/_rels/document.xml.rels"))

        # Merge relationships + media
        rel_map, added_media = _merge_rels_and_media(tmpl_rels, body_rels, zt=zt, zb=zb)

        # Merge footnotes/endnotes and patch body doc
        footnote_map, endnote_map, new_footnotes_xml, new_endnotes_xml = _merge_notes(
            zt=zt, zb=zb
        )
        _patch_note_refs(body_doc, footnote_map=footnote_map, endnote_map=endnote_map)

        # Patch relationship ids in body doc
        _patch_relationship_ids(body_doc, rel_id_map=rel_map)

        # Apply cover metadata and ensure list of tables exists
        _apply_cover_meta(tmpl_doc, meta)
        _ensure_list_of_tables(tmpl_doc)

        # Replace the sample content with body content
        _replace_content_region(tmpl_doc, body_doc)

        # Replace markers with Word fields
        _replace_markers(tmpl_doc)

        # Align figure images consistently (caption above, centered image).
        _center_captioned_figure_images(tmpl_doc)

        # Bibliography sources customXml
        item1_xml = zt.read("customXml/item1.xml") if "customXml/item1.xml" in zt.namelist() else None
        new_item1_xml = (
            build_sources_customxml(template_item1_xml=item1_xml, sources=sources)
            if item1_xml is not None
            else None
        )

        # Build output package
        output_docx.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_docx, "w", compression=zipfile.ZIP_DEFLATED) as zo:
            for info in zt.infolist():
                name = info.filename
                if name in (
                    "word/document.xml",
                    "word/_rels/document.xml.rels",
                    "word/styles.xml",
                    "word/numbering.xml",
                    "word/footnotes.xml",
                    "word/endnotes.xml",
                    "customXml/item1.xml",
                ):
                    continue
                zo.writestr(info, zt.read(name))

            # Write replaced parts
            zo.writestr("word/document.xml", _xml_to_bytes(tmpl_doc))
            zo.writestr("word/_rels/document.xml.rels", _xml_to_bytes(tmpl_rels))

            # Use pandoc-generated styles/numbering for list fidelity
            zo.writestr("word/styles.xml", zb.read("word/styles.xml"))
            zo.writestr("word/numbering.xml", zb.read("word/numbering.xml"))

            # Notes
            zo.writestr("word/footnotes.xml", new_footnotes_xml)
            zo.writestr("word/endnotes.xml", new_endnotes_xml)

            if new_item1_xml is not None:
                zo.writestr("customXml/item1.xml", new_item1_xml)

            # Added media
            for target_path, blob in added_media.items():
                zo.writestr(target_path, blob)


def _xml_from_bytes(data: bytes) -> ET._Element:
    parser = ET.XMLParser(remove_blank_text=False)
    return ET.fromstring(data, parser=parser)


def _xml_to_bytes(root: ET._Element) -> bytes:
    return ET.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _merge_rels_and_media(
    tmpl_rels: ET._Element,
    body_rels: ET._Element,
    *,
    zt: zipfile.ZipFile,
    zb: zipfile.ZipFile,
) -> tuple[dict[str, str], dict[str, bytes]]:
    """Copy image/hyperlink relationships from body -> template.

    Returns:
      - rel_id_map: old rId -> new rId
      - added_media: zip path -> bytes
    """
    rel_id_map: dict[str, str] = {}
    added_media: dict[str, bytes] = {}

    tmpl_ids = [_rel.get("Id") for _rel in tmpl_rels.findall(f"{{{PKG_REL_NS}}}Relationship")]
    max_n = 0
    for rid in tmpl_ids:
        if not rid:
            continue
        m = re.match(r"rId(\d+)$", rid)
        if m:
            max_n = max(max_n, int(m.group(1)))

    def next_rid() -> str:
        nonlocal max_n
        max_n += 1
        return f"rId{max_n}"

    # Track used media filenames in template
    used_media = set(n.split("/")[-1] for n in zt.namelist() if n.startswith("word/media/"))
    media_counter = 1

    def new_media_name(ext: str) -> str:
        nonlocal media_counter
        while True:
            name = f"image_md2docx_{media_counter:04d}.{ext}"
            media_counter += 1
            if name not in used_media:
                used_media.add(name)
                return name

    for rel in body_rels.findall(f"{{{PKG_REL_NS}}}Relationship"):
        old_id = rel.get("Id")
        rel_type = rel.get("Type") or ""
        target = rel.get("Target") or ""
        target_mode = rel.get("TargetMode")

        if not old_id:
            continue
        if rel_type.endswith("/image"):
            # Copy media file
            src_path = f"word/{target}"
            blob = zb.read(src_path)
            ext = target.split(".")[-1].lower()
            name = new_media_name(ext)
            dst_target = f"media/{name}"
            dst_path = f"word/{dst_target}"

            new_id = next_rid()
            rel_id_map[old_id] = new_id
            added_media[dst_path] = blob

            new_rel = ET.Element(ET.QName(PKG_REL_NS, "Relationship"))
            new_rel.set("Id", new_id)
            new_rel.set("Type", rel_type)
            new_rel.set("Target", dst_target)
            tmpl_rels.append(new_rel)
            continue

        if rel_type.endswith("/hyperlink"):
            new_id = next_rid()
            rel_id_map[old_id] = new_id
            new_rel = ET.Element(ET.QName(PKG_REL_NS, "Relationship"))
            new_rel.set("Id", new_id)
            new_rel.set("Type", rel_type)
            new_rel.set("Target", target)
            if target_mode:
                new_rel.set("TargetMode", target_mode)
            tmpl_rels.append(new_rel)
            continue

    return rel_id_map, added_media


def _merge_notes(*, zt: zipfile.ZipFile, zb: zipfile.ZipFile) -> tuple[dict[int, int], dict[int, int], bytes, bytes]:
    tmpl_foot = _xml_from_bytes(zt.read("word/footnotes.xml"))
    tmpl_end = _xml_from_bytes(zt.read("word/endnotes.xml"))
    body_foot = _xml_from_bytes(zb.read("word/footnotes.xml"))
    body_end = _xml_from_bytes(zb.read("word/endnotes.xml")) if "word/endnotes.xml" in zb.namelist() else None

    foot_map = _append_notes(tmpl_foot, body_foot, note_tag="footnote")
    end_map: dict[int, int] = {}
    if body_end is not None:
        end_map = _append_notes(tmpl_end, body_end, note_tag="endnote")

    return foot_map, end_map, _xml_to_bytes(tmpl_foot), _xml_to_bytes(tmpl_end)


def _append_notes(tmpl_root: ET._Element, body_root: ET._Element, *, note_tag: str) -> dict[int, int]:
    # Determine max existing positive id
    max_id = 0
    for n in tmpl_root.findall(f".//w:{note_tag}", namespaces=NS):
        raw = n.get(ET.QName(W_NS, "id"))
        if raw is None:
            continue
        try:
            i = int(raw)
        except ValueError:
            continue
        if i > 0:
            max_id = max(max_id, i)

    id_map: dict[int, int] = {}
    for n in body_root.findall(f".//w:{note_tag}", namespaces=NS):
        raw = n.get(ET.QName(W_NS, "id"))
        if raw is None:
            continue
        try:
            old = int(raw)
        except ValueError:
            continue
        if old <= 0:
            continue
        max_id += 1
        new = max_id
        id_map[old] = new
        n.set(ET.QName(W_NS, "id"), str(new))
        tmpl_root.append(copy.deepcopy(n))

    return id_map


def _patch_note_refs(doc: ET._Element, *, footnote_map: dict[int, int], endnote_map: dict[int, int]) -> None:
    for ref in doc.findall(".//w:footnoteReference", namespaces=NS):
        raw = ref.get(ET.QName(W_NS, "id"))
        if raw is None:
            continue
        try:
            i = int(raw)
        except ValueError:
            continue
        if i in footnote_map:
            ref.set(ET.QName(W_NS, "id"), str(footnote_map[i]))

    for ref in doc.findall(".//w:endnoteReference", namespaces=NS):
        raw = ref.get(ET.QName(W_NS, "id"))
        if raw is None:
            continue
        try:
            i = int(raw)
        except ValueError:
            continue
        if i in endnote_map:
            ref.set(ET.QName(W_NS, "id"), str(endnote_map[i]))


def _patch_relationship_ids(doc: ET._Element, *, rel_id_map: dict[str, str]) -> None:
    # Images: a:blip @r:embed
    for el in doc.xpath("//*[@r:embed]", namespaces=NS):
        old = el.get(ET.QName(R_NS, "embed"))
        if old in rel_id_map:
            el.set(ET.QName(R_NS, "embed"), rel_id_map[old])

    # Hyperlinks: w:hyperlink @r:id
    for el in doc.xpath("//w:hyperlink[@r:id]", namespaces=NS):
        old = el.get(ET.QName(R_NS, "id"))
        if old in rel_id_map:
            el.set(ET.QName(R_NS, "id"), rel_id_map[old])


def _apply_cover_meta(doc: ET._Element, meta: dict) -> None:
    title = str(meta.get("title", "")).strip()
    subtitle = str(meta.get("subtitle", "")).strip()
    author = str(meta.get("author", "")).strip()
    date = str(meta.get("date", "")).strip()

    repl = {
        "T\ufffdTULO DEL DOCUMENTO": title or "T\ufffdTULO DEL DOCUMENTO",
        "Subt\ufffdtulo del documento": subtitle or "Subt\ufffdtulo del documento",
    }

    # Replace title/subtitle placeholders
    for t in doc.findall(".//w:t", namespaces=NS):
        if t.text in repl:
            t.text = repl[t.text]

    # Replace author/date lines
    for t in doc.findall(".//w:t", namespaces=NS):
        if t.text == "Elaborado por:" and author:
            t.text = f"Elaborado por: {author}"
        if t.text == "Fecha:" and date:
            t.text = f"Fecha: {date}"


def _ensure_list_of_tables(doc: ET._Element) -> None:
    body = doc.find(".//w:body", namespaces=NS)
    if body is None:
        return

    # If there is already a TOC \c "Tabla" field, do nothing.
    if doc.xpath(
        "//w:instrText[contains(., 'TOC') and contains(., '\\c') and contains(., 'Tabla')]",
        namespaces=NS,
    ):
        return

    # Find list-of-figures field paragraph to insert after
    fig_instr = doc.xpath(
        "//w:instrText[contains(., 'TOC') and contains(., '\\c') and contains(., 'Figura')]",
        namespaces=NS,
    )
    if not fig_instr:
        return
    fig_p = fig_instr[0].getparent()
    while fig_p is not None and fig_p.tag != ET.QName(W_NS, "p"):
        fig_p = fig_p.getparent()
    if fig_p is None:
        return

    # Insert after the figure list paragraph
    children = list(body)
    try:
        idx = children.index(fig_p)
    except ValueError:
        return

    heading_p = _make_styled_paragraph(style_id="TOCHeading", text="Lista de tablas")
    toc_p = _make_toc_field_paragraph(style_id="TableofFigures", caption_label="Tabla")

    body.insert(idx + 1, heading_p)
    body.insert(idx + 2, toc_p)


def _make_styled_paragraph(*, style_id: str, text: str) -> ET._Element:
    p = ET.Element(ET.QName(W_NS, "p"))
    ppr = ET.SubElement(p, ET.QName(W_NS, "pPr"))
    pstyle = ET.SubElement(ppr, ET.QName(W_NS, "pStyle"))
    pstyle.set(ET.QName(W_NS, "val"), style_id)
    r = ET.SubElement(p, ET.QName(W_NS, "r"))
    t = ET.SubElement(r, ET.QName(W_NS, "t"))
    t.text = text
    return p


def _make_toc_field_paragraph(*, style_id: str, caption_label: str) -> ET._Element:
    p = ET.Element(ET.QName(W_NS, "p"))
    ppr = ET.SubElement(p, ET.QName(W_NS, "pPr"))
    pstyle = ET.SubElement(ppr, ET.QName(W_NS, "pStyle"))
    pstyle.set(ET.QName(W_NS, "val"), style_id)

    def run() -> ET._Element:
        return ET.SubElement(p, ET.QName(W_NS, "r"))

    r1 = run()
    ET.SubElement(r1, ET.QName(W_NS, "fldChar"), attrib={ET.QName(W_NS, "fldCharType"): "begin"})
    r2 = run()
    it = ET.SubElement(r2, ET.QName(W_NS, "instrText"))
    it.set(ET.QName("http://www.w3.org/XML/1998/namespace", "space"), "preserve")
    it.text = f" TOC \\h \\z \\c \"{caption_label}\" "
    r3 = run()
    ET.SubElement(r3, ET.QName(W_NS, "fldChar"), attrib={ET.QName(W_NS, "fldCharType"): "separate"})
    r4 = run()
    t = ET.SubElement(r4, ET.QName(W_NS, "t"))
    t.text = ""
    r5 = run()
    ET.SubElement(r5, ET.QName(W_NS, "fldChar"), attrib={ET.QName(W_NS, "fldCharType"): "end"})
    return p


def _replace_content_region(tmpl_doc: ET._Element, body_doc: ET._Element) -> None:
    tmpl_body = tmpl_doc.find(".//w:body", namespaces=NS)
    body_body = body_doc.find(".//w:body", namespaces=NS)
    if tmpl_body is None or body_body is None:
        raise RuntimeError("Invalid docx: missing w:body")

    tmpl_children = list(tmpl_body)
    body_children = [c for c in list(body_body) if c.tag != ET.QName(W_NS, "sectPr")]

    # Find insertion start: first Heading1 after the figure list field.
    fig_instr = tmpl_doc.xpath(
        "//w:instrText[contains(., 'TOC') and contains(., '\\c') and contains(., 'Figura')]",
        namespaces=NS,
    )
    if not fig_instr:
        raise RuntimeError("Template missing Table of Figures field")
    fig_p = fig_instr[0].getparent()
    while fig_p is not None and fig_p.tag != ET.QName(W_NS, "p"):
        fig_p = fig_p.getparent()
    if fig_p is None:
        raise RuntimeError("Unable to locate Table of Figures paragraph")

    start_idx = None
    for idx, el in enumerate(tmpl_children):
        if el is fig_p:
            # scan forward
            for j in range(idx + 1, len(tmpl_children)):
                if _is_paragraph_style(tmpl_children[j], "Heading1"):
                    start_idx = j
                    break
            break
    if start_idx is None:
        raise RuntimeError("Unable to find content start in template")

    # Find end: the SDT that contains the 'Referencias' Heading1 paragraph.
    end_idx = None
    for idx, el in enumerate(tmpl_children):
        if el.tag == ET.QName(W_NS, "sdt"):
            if el.xpath(".//w:p[w:pPr/w:pStyle[@w:val='Heading1']]//w:t[contains(., 'Referencias')]", namespaces=NS):
                end_idx = idx
                break
    if end_idx is None:
        raise RuntimeError("Unable to find references section (Referencias) in template")

    # Remove old sample content
    for _ in range(end_idx - start_idx):
        del tmpl_children[start_idx]
    # Rebuild body children in-place
    tmpl_body[:] = tmpl_children[:start_idx] + [copy.deepcopy(c) for c in body_children] + tmpl_children[start_idx:]


def _is_paragraph_style(p: ET._Element, style_id: str) -> bool:
    if p.tag != ET.QName(W_NS, "p"):
        return False
    pstyle = p.find("./w:pPr/w:pStyle", namespaces=NS)
    if pstyle is None:
        return False
    return pstyle.get(ET.QName(W_NS, "val")) == style_id


def _replace_markers(doc: ET._Element) -> None:
    max_bm = _max_bookmark_id(doc)
    next_bm = max_bm + 1

    fig_numbers: dict[str, int] = {}
    tab_numbers: dict[str, int] = {}
    fig_counter = 0
    tab_counter = 0

    # Captions are expected to be the entire paragraph text
    for p in doc.findall(".//w:p", namespaces=NS):
        text = "".join([t.text or "" for t in p.findall(".//w:t", namespaces=NS)]).strip()
        m = re.match(r"^\[\[MD2DOCX_CAPTION_FIG:([A-Za-z0-9_-]+)\|(.*)\]\]$", text)
        if m:
            fig_id = m.group(1)
            title = m.group(2)
            fig_counter += 1
            fig_numbers[fig_id] = fig_counter
            bm_name = _bookmark_name("fig", fig_id)
            _replace_paragraph_with_caption(
                p,
                label="Figura",
                seq_name="Figura",
                title=title,
                bookmark=bm_name,
                bm_id=next_bm,
                number=fig_counter,
            )
            next_bm += 1
            continue

        m = re.match(r"^\[\[MD2DOCX_CAPTION_TAB:([A-Za-z0-9_-]+)\|(.*)\]\]$", text)
        if m:
            tab_id = m.group(1)
            title = m.group(2)
            tab_counter += 1
            tab_numbers[tab_id] = tab_counter
            bm_name = _bookmark_name("tab", tab_id)
            _replace_paragraph_with_caption(
                p,
                label="Tabla",
                seq_name="Tabla",
                title=title,
                bookmark=bm_name,
                bm_id=next_bm,
                number=tab_counter,
            )
            next_bm += 1
            continue

    # Inline replacements for REF and CITATION markers
    for p in doc.findall(".//w:p", namespaces=NS):
        for t in list(p.findall(".//w:t", namespaces=NS)):
            if not t.text:
                continue
            _replace_inline_markers_in_textnode(
                t,
                fig_numbers=fig_numbers,
                tab_numbers=tab_numbers,
            )


def _replace_inline_markers_in_textnode(
    t: ET._Element,
    *,
    fig_numbers: dict[str, int],
    tab_numbers: dict[str, int],
) -> None:
    txt = t.text or ""

    # REF markers
    ref_pat = re.compile(r"\[\[MD2DOCX_REF:(fig|tab):([A-Za-z0-9_-]+)\]\]")
    m = ref_pat.search(txt)
    if m:
        kind, ref_id = m.group(1), m.group(2)
        before = txt[: m.start()]
        after = txt[m.end() :]
        t.text = before
        bm = _bookmark_name(kind, ref_id)
        if kind == "fig":
            n = fig_numbers.get(ref_id)
            placeholder = f"Figura {n}" if n is not None else "Figura"
        else:
            n = tab_numbers.get(ref_id)
            placeholder = f"Tabla {n}" if n is not None else "Tabla"

        nodes = _make_ref_field_runs(bookmark=bm, result_text=placeholder)
        if after:
            nodes.append(_make_run_with_text(after))
        _insert_after_textnode(t, nodes)
        return

    cit_pat = re.compile(r"\[\[MD2DOCX_CITATION:([A-Za-z0-9_-]+)\]\]")
    m = cit_pat.search(txt)
    if m:
        tag = m.group(1)
        before = txt[: m.start()]
        after = txt[m.end() :]
        t.text = before
        nodes: list[ET._Element] = [_make_citation_sdt(tag=tag)]
        if after:
            nodes.append(_make_run_with_text(after))
        _insert_after_textnode(t, nodes)
        return

    return


def _center_captioned_figure_images(doc: ET._Element) -> None:
    body = doc.find(".//w:body", namespaces=NS)
    if body is None:
        return

    paras = body.findall("./w:p", namespaces=NS)
    for i in range(len(paras) - 1):
        cap = paras[i]
        nxt = paras[i + 1]

        if not _is_paragraph_style(cap, "Caption"):
            continue
        # Only for figure captions (not table captions)
        if not cap.xpath(".//w:instrText[contains(., 'SEQ Figura')]", namespaces=NS):
            continue
        if not (nxt.xpath(".//w:drawing", namespaces=NS) or nxt.xpath(".//w:pict", namespaces=NS)):
            continue

        ppr = nxt.find("w:pPr", namespaces=NS)
        if ppr is None:
            ppr = ET.SubElement(nxt, ET.QName(W_NS, "pPr"))
        jc = ppr.find("w:jc", namespaces=NS)
        if jc is None:
            jc = ET.SubElement(ppr, ET.QName(W_NS, "jc"))
        jc.set(ET.QName(W_NS, "val"), "center")


def _insert_after_textnode(t: ET._Element, new_nodes: list[ET._Element]) -> None:
    # Insert after the parent run of this text node.
    r = t.getparent()
    if r is None:
        return
    p = r.getparent()
    if p is None:
        return
    idx = list(p).index(r)
    for n in new_nodes:
        idx += 1
        p.insert(idx, n)


def _replace_paragraph_with_caption(
    p: ET._Element,
    *,
    label: str,
    seq_name: str,
    title: str,
    bookmark: str,
    bm_id: int,
    number: int,
) -> None:
    # Remove all children except pPr
    ppr = p.find("w:pPr", namespaces=NS)
    for child in list(p):
        if child is ppr:
            continue
        p.remove(child)

    # Ensure style is Caption
    if ppr is None:
        ppr = ET.SubElement(p, ET.QName(W_NS, "pPr"))
    pstyle = ppr.find("w:pStyle", namespaces=NS)
    if pstyle is None:
        pstyle = ET.SubElement(ppr, ET.QName(W_NS, "pStyle"))
    pstyle.set(ET.QName(W_NS, "val"), "Caption")

    # Bookmark around label + SEQ number
    bm_start = ET.Element(ET.QName(W_NS, "bookmarkStart"))
    bm_start.set(ET.QName(W_NS, "name"), bookmark)
    bm_start.set(ET.QName(W_NS, "id"), str(bm_id))
    p.append(bm_start)

    p.append(_make_run_with_text(f"{label} "))
    p.extend(_make_seq_field_runs(seq_name=seq_name, result_text=str(number)))

    bm_end = ET.Element(ET.QName(W_NS, "bookmarkEnd"))
    bm_end.set(ET.QName(W_NS, "id"), str(bm_id))
    p.append(bm_end)

    p.append(_make_run_with_text(f". {title}"))


def _make_seq_field_runs(*, seq_name: str, result_text: str) -> list[ET._Element]:
    runs: list[ET._Element] = []

    r_begin = ET.Element(ET.QName(W_NS, "r"))
    ET.SubElement(r_begin, ET.QName(W_NS, "fldChar"), attrib={ET.QName(W_NS, "fldCharType"): "begin"})
    runs.append(r_begin)

    r_instr = ET.Element(ET.QName(W_NS, "r"))
    it = ET.SubElement(r_instr, ET.QName(W_NS, "instrText"))
    it.set(ET.QName("http://www.w3.org/XML/1998/namespace", "space"), "preserve")
    it.text = f" SEQ {seq_name} \\* ARABIC "
    runs.append(r_instr)

    r_sep = ET.Element(ET.QName(W_NS, "r"))
    ET.SubElement(r_sep, ET.QName(W_NS, "fldChar"), attrib={ET.QName(W_NS, "fldCharType"): "separate"})
    runs.append(r_sep)

    r_txt = ET.Element(ET.QName(W_NS, "r"))
    rpr = ET.SubElement(r_txt, ET.QName(W_NS, "rPr"))
    ET.SubElement(rpr, ET.QName(W_NS, "noProof"))
    ET.SubElement(r_txt, ET.QName(W_NS, "t")).text = result_text
    runs.append(r_txt)

    r_end = ET.Element(ET.QName(W_NS, "r"))
    ET.SubElement(r_end, ET.QName(W_NS, "fldChar"), attrib={ET.QName(W_NS, "fldCharType"): "end"})
    runs.append(r_end)

    return runs


def _make_ref_field_runs(*, bookmark: str, result_text: str) -> list[ET._Element]:
    runs: list[ET._Element] = []

    r_begin = ET.Element(ET.QName(W_NS, "r"))
    ET.SubElement(r_begin, ET.QName(W_NS, "fldChar"), attrib={ET.QName(W_NS, "fldCharType"): "begin"})
    runs.append(r_begin)

    r_instr = ET.Element(ET.QName(W_NS, "r"))
    it = ET.SubElement(r_instr, ET.QName(W_NS, "instrText"))
    it.set(ET.QName("http://www.w3.org/XML/1998/namespace", "space"), "preserve")
    it.text = f" REF {bookmark} \\h "
    runs.append(r_instr)

    r_sep = ET.Element(ET.QName(W_NS, "r"))
    ET.SubElement(r_sep, ET.QName(W_NS, "fldChar"), attrib={ET.QName(W_NS, "fldCharType"): "separate"})
    runs.append(r_sep)

    r_txt = ET.Element(ET.QName(W_NS, "r"))
    rpr = ET.SubElement(r_txt, ET.QName(W_NS, "rPr"))
    ET.SubElement(rpr, ET.QName(W_NS, "noProof"))
    t_el = ET.SubElement(r_txt, ET.QName(W_NS, "t"))
    if result_text.startswith(" ") or result_text.endswith(" "):
        t_el.set(ET.QName("http://www.w3.org/XML/1998/namespace", "space"), "preserve")
    t_el.text = result_text
    runs.append(r_txt)

    r_end = ET.Element(ET.QName(W_NS, "r"))
    ET.SubElement(r_end, ET.QName(W_NS, "fldChar"), attrib={ET.QName(W_NS, "fldCharType"): "end"})
    runs.append(r_end)

    return runs


def _make_citation_sdt(*, tag: str) -> ET._Element:
    # Minimal citation SDT modeled after the template.
    sdt = ET.Element(ET.QName(W_NS, "sdt"))
    sdtPr = ET.SubElement(sdt, ET.QName(W_NS, "sdtPr"))
    ET.SubElement(sdtPr, ET.QName(W_NS, "id"), attrib={ET.QName(W_NS, "val"): str(_stable_int(tag))})
    ET.SubElement(sdtPr, ET.QName(W_NS, "citation"))
    ET.SubElement(sdt, ET.QName(W_NS, "sdtEndPr"))
    sdtContent = ET.SubElement(sdt, ET.QName(W_NS, "sdtContent"))

    def r() -> ET._Element:
        return ET.SubElement(sdtContent, ET.QName(W_NS, "r"))

    rb = r()
    ET.SubElement(rb, ET.QName(W_NS, "fldChar"), attrib={ET.QName(W_NS, "fldCharType"): "begin"})
    ri = r()
    it = ET.SubElement(ri, ET.QName(W_NS, "instrText"))
    it.set(ET.QName("http://www.w3.org/XML/1998/namespace", "space"), "preserve")
    it.text = f" CITATION {tag} \\l 12298 "
    rs = r()
    ET.SubElement(rs, ET.QName(W_NS, "fldChar"), attrib={ET.QName(W_NS, "fldCharType"): "separate"})
    rt = r()
    rpr = ET.SubElement(rt, ET.QName(W_NS, "rPr"))
    ET.SubElement(rpr, ET.QName(W_NS, "noProof"))
    ET.SubElement(rt, ET.QName(W_NS, "t")).text = "(Cita)"
    re = r()
    ET.SubElement(re, ET.QName(W_NS, "fldChar"), attrib={ET.QName(W_NS, "fldCharType"): "end"})
    return sdt


def _make_run_with_text(text: str) -> ET._Element:
    r = ET.Element(ET.QName(W_NS, "r"))
    t = ET.SubElement(r, ET.QName(W_NS, "t"))
    if text.startswith(" ") or text.endswith(" "):
        t.set(ET.QName("http://www.w3.org/XML/1998/namespace", "space"), "preserve")
    t.text = text
    return r


def _bookmark_name(kind: str, raw_id: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_]+", "_", raw_id.strip())
    if not re.match(r"^[A-Za-z]", base):
        base = "x_" + base
    return f"{kind}_{base}"


def _max_bookmark_id(doc: ET._Element) -> int:
    max_id = 0
    for bm in doc.findall(".//w:bookmarkStart", namespaces=NS):
        raw = bm.get(ET.QName(W_NS, "id"))
        if raw is None:
            continue
        try:
            i = int(raw)
        except ValueError:
            continue
        max_id = max(max_id, i)
    return max_id


def _stable_int(s: str) -> int:
    # Deterministic pseudo-id
    h = 0
    for ch in s:
        h = (h * 131 + ord(ch)) & 0x7FFFFFFF
    if h == 0:
        h = 1
    return h
