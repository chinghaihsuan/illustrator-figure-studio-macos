"""Check local SVG inputs before passing them to Illustrator's native importer."""
import re
import xml.etree.ElementTree as ET


def read_svg(filename):
    data = filename.read_bytes()
    if len(data) > 20_000_000:
        raise ValueError("SVG exceeds 20 MB")
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("Save the SVG without a document type or XML entities")
    root = ET.fromstring(data)
    if root.tag != "{http://www.w3.org/2000/svg}svg":
        raise ValueError("Expected an SVG root in the SVG namespace")
    for item in root.iter():
        kind = item.tag.split("}")[-1]
        if kind in {"script", "foreignObject", "image", "feImage", "iframe", "a"}:
            raise ValueError(f"Unsupported SVG element: {kind}")
        values = list(item.attrib.values()) + ([item.text or ""] if kind == "style" else [])
        for name, value in item.attrib.items():
            attr = name.split("}")[-1].lower()
            if attr.startswith("on") or (attr == "href" and not value.strip().startswith("#")):
                raise ValueError(f"Unsupported SVG attribute: {attr}")
        for value in values:
            if re.search(r"@import", value, re.I):
                raise ValueError("SVG styles must be local")
            for match in re.findall(r"url\s*\(([^)]*)\)", value, re.I):
                if not match.strip(" \"'\t\n").startswith("#"):
                    raise ValueError("SVG references must be internal")
    return data
