"""Validation and SVG output for authored vector reconstructions."""
from pathlib import Path
import xml.etree.ElementTree as ET


def compile_artwork(spec, number, color):
    width = number(spec["width"], "width", 80)
    height = number(spec["height"], "height", 80)
    objects = []
    names = set()
    for item in spec["artwork"]:
        name = item["name"]
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError(f"Missing or repeated object name: {name!r}")
        names.add(name)
        stage = item.get("stage", 0)
        if type(stage) != int:
            raise ValueError(f"{name}: stage must be an integer")
        number(stage, "stage", 0, 299)
        kind = item["kind"]
        obj = dict(name=name, kind=kind, stage=stage)
        if kind == "label":
            label = item["text"]
            if not isinstance(label, str) or not label.strip():
                raise ValueError(f"{name}: expected nonempty text")
            align = item.get("align", "center")
            if align not in ("left", "center", "right"):
                raise ValueError(f"{name}: invalid alignment")
            font = item.get("font", "Helvetica")
            if not isinstance(font, str) or not font.strip():
                raise ValueError(f"{name}: invalid font")
            obj.update(x=number(item["x"], "x", 0, width), y=number(item["y"], "y", 0, height),
                       text=label, size=number(item.get("size", 18), "font size", 4, 500),
                       fill=color(item.get("fill", "#151921")), font=font, align=align)
        else:
            obj.update(fill=color(item["fill"]) if item.get("fill") else None,
                       stroke=color(item["stroke"]) if item.get("stroke") else None,
                       weight=number(item.get("weight", 1), "stroke width", 0.1, 80))
            if not obj["fill"] and not obj["stroke"]:
                raise ValueError(f"{name}: supply a fill or stroke")
            if kind in ("rect", "ellipse"):
                for k in ("x", "y", "w", "h"):
                    obj[k] = number(item[k], k, 1 if k in ("w", "h") else 0)
                if obj["x"] + obj["w"] > width or obj["y"] + obj["h"] > height:
                    raise ValueError(f"{name}: shape outside artboard")
                obj["radius"] = number(item.get("radius", 0), "radius", 0, min(obj["w"], obj["h"]) / 2)
            elif kind == "path":
                knots = []
                for vertex in item["knots"]:
                    if not isinstance(vertex, list) or len(vertex) not in (2, 6):
                        raise ValueError(f"{name}: knot needs x,y and optional incoming/outgoing handles")
                    knots.append([number(value, "path coordinate", -16000, 32000)
                                  for value in vertex])
                if len(knots) < 2:
                    raise ValueError(f"{name}: path requires at least two knots")
                closed = item.get("closed", False)
                if type(closed) != bool:
                    raise ValueError(f"{name}: closed must be a boolean")
                obj.update(knots=knots, closed=closed)
            else:
                raise ValueError(f"{name}: unknown kind {kind!r}")
        objects.append(obj)
    if not objects:
        raise ValueError("artwork is empty")
    return dict(width=width, height=height, artwork=sorted(objects, key=lambda obj: obj["stage"]))


def path_data(obj):
    knots = obj["knots"]
    start = knots[0]
    parts = [f"M {start[0]} {start[1]}"]
    destinations = knots[1:] + ([start] if obj["closed"] else [])
    for prev, curr in zip(knots, destinations):
        outgoing = prev[4:6] or prev[:2]
        incoming = curr[2:4] or curr[:2]
        if outgoing == prev[:2] and incoming == curr[:2]:
            parts.append(f"L {curr[0]} {curr[1]}")
        else:
            parts.append("C " + " ".join(map(str, outgoing + incoming + curr[:2])))
    if obj["closed"]:
        parts.append("Z")
    return " ".join(parts)


def write_artwork_svg(scene, filename):
    w, h = scene["width"], scene["height"]
    root = ET.Element("svg", xmlns="http://www.w3.org/2000/svg", width=f"{w}pt",
                      height=f"{h}pt", viewBox=f"0 0 {w} {h}")
    for index, obj in enumerate(scene["artwork"]):
        attrs = {"id": f"item-{index + 1}", "aria-label": obj["name"]}
        kind = obj["kind"]
        if kind == "label":
            size = obj["size"]
            lines = obj["text"].splitlines()
            text = ET.SubElement(root, "text", x=str(obj["x"]), fill=obj["fill"], **attrs)
            font = obj["font"]
            text.set("font-family", font.split("-")[0])
            if "Bold" in font:
                text.set("font-weight", "bold")
            if "Oblique" in font or "Italic" in font:
                text.set("font-style", "italic")
            text.set("font-size", str(size))
            text.set("text-anchor", {"left":"start", "center":"middle", "right":"end"}[obj["align"]])
            start = obj["y"] + size * 0.34 - (len(lines) - 1) * size * 0.6
            for line_index, line in enumerate(lines):
                ET.SubElement(text, "tspan", x=str(obj["x"]),
                              y=str(start + size * 1.2 * line_index)).text = line
            continue
        attrs.update(fill=obj["fill"] or "none", stroke=obj["stroke"] or "none")
        attrs.update({"stroke-width": str(obj["weight"]), "stroke-linecap": "round",
                      "stroke-linejoin": "round"})
        if kind == "path":
            attrs["d"] = path_data(obj)
        else:
            x, y, w, h = (obj[k] for k in ("x", "y", "w", "h"))
            if kind == "ellipse":
                attrs.update(cx=str(x+w/2), cy=str(y+h/2), rx=str(w/2), ry=str(h/2))
            else:
                attrs.update(x=str(x), y=str(y), width=str(w), height=str(h), rx=str(obj["radius"]))
        ET.SubElement(root, kind, attrs)
    with Path(filename).open("xb") as handle:
        ET.ElementTree(root).write(handle, encoding="utf-8", xml_declaration=True)
