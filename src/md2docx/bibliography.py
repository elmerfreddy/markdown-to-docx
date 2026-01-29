from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import uuid

from lxml import etree as ET
import yaml


BIB_NS = "http://schemas.openxmlformats.org/officeDocument/2006/bibliography"


@dataclass(frozen=True)
class BibSource:
    tag: str
    source_type: str
    title: str | None = None
    year: str | None = None
    city: str | None = None
    publisher: str | None = None
    authors: list[dict[str, str]] | None = None


def load_sources_yaml(path: Path) -> list[BibSource]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[BibSource] = []
    for raw in data.get("sources", []) or []:
        out.append(
            BibSource(
                tag=str(raw.get("tag", "")).strip(),
                source_type=str(raw.get("type", "")).strip() or "Book",
                title=(str(raw.get("title")).strip() if raw.get("title") is not None else None),
                year=(str(raw.get("year")).strip() if raw.get("year") is not None else None),
                city=(str(raw.get("city")).strip() if raw.get("city") is not None else None),
                publisher=(
                    str(raw.get("publisher")).strip() if raw.get("publisher") is not None else None
                ),
                authors=(raw.get("authors") or None),
            )
        )
    return [s for s in out if s.tag]


def build_sources_customxml(
    *,
    template_item1_xml: bytes,
    sources: list[BibSource],
) -> bytes:
    """Builds customXml/item1.xml in Word bibliography schema.

    We keep the root attributes from the template (APA style settings) and replace
    the list of <b:Source> entries.
    """
    parser = ET.XMLParser(remove_blank_text=True)
    root_old = ET.fromstring(template_item1_xml, parser=parser)

    # Create a new root with the same attributes.
    nsmap = {"b": BIB_NS, None: BIB_NS}
    root = ET.Element(ET.QName(BIB_NS, "Sources"), nsmap=nsmap)
    for k, v in root_old.attrib.items():
        root.set(k, v)

    for idx, src in enumerate(sources, start=1):
        root.append(_source_to_xml(src, ref_order=idx))

    return ET.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")


def _source_to_xml(src: BibSource, *, ref_order: int) -> ET._Element:
    s_el = ET.Element(ET.QName(BIB_NS, "Source"))
    ET.SubElement(s_el, ET.QName(BIB_NS, "Tag")).text = src.tag
    ET.SubElement(s_el, ET.QName(BIB_NS, "SourceType")).text = src.source_type
    ET.SubElement(s_el, ET.QName(BIB_NS, "Guid")).text = "{" + str(uuid.uuid4()).upper() + "}"

    if src.title:
        ET.SubElement(s_el, ET.QName(BIB_NS, "Title")).text = src.title
    if src.year:
        ET.SubElement(s_el, ET.QName(BIB_NS, "Year")).text = src.year

    if src.authors:
        s_el.append(_authors_to_xml(src.authors))

    if src.city:
        ET.SubElement(s_el, ET.QName(BIB_NS, "City")).text = src.city
    if src.publisher:
        ET.SubElement(s_el, ET.QName(BIB_NS, "Publisher")).text = src.publisher

    ET.SubElement(s_el, ET.QName(BIB_NS, "RefOrder")).text = str(ref_order)
    return s_el


def _authors_to_xml(authors: list[dict[str, str]]) -> ET._Element:
    # Match Word's nested structure from the template:
    # <b:Author><b:Author><b:NameList>...</b:NameList></b:Author></b:Author>
    a1 = ET.Element(ET.QName(BIB_NS, "Author"))
    a2 = ET.SubElement(a1, ET.QName(BIB_NS, "Author"))
    nl = ET.SubElement(a2, ET.QName(BIB_NS, "NameList"))

    for a in authors:
        person = ET.SubElement(nl, ET.QName(BIB_NS, "Person"))
        if "corporate" in a and a["corporate"]:
            ET.SubElement(person, ET.QName(BIB_NS, "Last")).text = str(a["corporate"]).strip()
            continue
        if "last" in a and a["last"]:
            ET.SubElement(person, ET.QName(BIB_NS, "Last")).text = str(a["last"]).strip()
        if "first" in a and a["first"]:
            ET.SubElement(person, ET.QName(BIB_NS, "First")).text = str(a["first"]).strip()

    return a1
