#!/usr/bin/env python3
"""Compile a diagram JSON file into an Adobe Illustrator JSX script."""
import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as ET

from artwork import compile_artwork, write_artwork_svg
from svg_input import read_svg


def number(value, name, minimum=0, maximum=16000):
    if type(value) not in (float, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be a number in [{minimum}, {maximum}]")
    return value


def color(value):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError(f"Expected #RRGGBB, got {value!r}")
    return value


def compile_scene(spec):
    width = number(spec.get("width", 760), "width", 80)
    height = number(spec.get("height", 360), "height", 80)
    direction = spec.get("layout", "horizontal")
    if direction not in ("horizontal", "vertical", "manual"):
        raise ValueError("layout must be horizontal, vertical, or manual")
    entries = spec["nodes"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("nodes must be a nonempty list")
    nodes = {}
    for index, item in enumerate(entries):
        key = item["id"]
        if not isinstance(key, str) or not key.strip() or key in nodes:
            raise ValueError(f"Missing or duplicate node id: {key!r}")
        if direction == "horizontal":
            spacing = (width - 64) / len(entries)
        elif direction == "vertical":
            spacing = (height - 64) / len(entries)
        else:
            spacing = 160
        w = number(item.get("width", min(180, spacing - 24) if direction == "horizontal" else 180), "node width", 12)
        h = number(item.get("height", min(58, spacing - 20) if direction == "vertical" else 58), "node height", 12)
        if direction == "horizontal":
            x, y = 32 + spacing * (index + 0.5) - w / 2, (height - h) / 2
        elif direction == "vertical":
            x, y = (width - w) / 2, 32 + spacing * (index + 0.5) - h / 2
        else:
            x, y = number(item["x"], "x"), number(item["y"], "y")
        if x < 0 or y < 0 or x + w > width or y + h > height:
            raise ValueError(f"Node {key!r} exceeds the artboard")
        label = item.get("label", "")
        shape = item.get("shape", "rounded")
        if not isinstance(label, str) or shape not in ("rounded", "rectangle", "ellipse", "text"):
            raise ValueError(f"Invalid label or shape for {key!r}")
        nodes[key] = dict(id=key, x=x, y=y, w=w, h=h, label=label, shape=shape,
                          fill=color(item.get("fill", "#E5F2ED")),
                          stroke=color(item.get("stroke", "#378073")),
                          size=number(item.get("size", 13), "font size", 5, 100))
    default_edges = [{"from": a, "to": b} for a, b in zip(nodes, list(nodes)[1:])]
    edges = []
    for index, edge in enumerate(spec.get("edges", default_edges)):
        a, b = nodes[edge["from"]], nodes[edge["to"]]
        if "via" in edge:
            waypoints = [[number(x, "via x", 0, width), number(y, "via y", 0, height)]
                         for x, y in edge["via"]]
        else:
            waypoints = []
        start, end = center(a), center(b)
        points = [boundary(a, waypoints[0] if waypoints else end), *waypoints,
                  boundary(b, waypoints[-1] if waypoints else start)]
        if any(math.dist(p, q) < 0.01 for p, q in zip(points, points[1:])):
            raise ValueError(f"Edge {index + 1} contains a zero-length segment")
        dashed = edge.get("dashed", False)
        if type(dashed) is not bool:
            raise ValueError("dashed must be true or false")
        edges.append(dict(name=f'{a["id"]} to {b["id"]}', points=points, dashed=dashed,
                          stroke=color(edge.get("stroke", "#41645C"))))
    return dict(width=width, height=height, nodes=list(nodes.values()), edges=edges)


def center(node):
    return [node["x"] + node["w"] / 2, node["y"] + node["h"] / 2]


def boundary(node, target):
    x, y = center(node)
    dx, dy = target[0] - x, target[1] - y
    rx, ry = node["w"] / 2, node["h"] / 2
    if node["shape"] == "ellipse":
        length = math.hypot(dx / rx, dy / ry)
    else:
        length = max(abs(dx) / rx, abs(dy) / ry)
    if length == 0:
        raise ValueError(f'Edge at {node["id"]!r} needs a distinct waypoint or endpoint')
    return [x + dx / length, y + dy / length]


def write_svg(scene, filename):
    root = ET.Element("svg", xmlns="http://www.w3.org/2000/svg",
                      width=f'{scene["width"]}pt', height=f'{scene["height"]}pt',
                      viewBox=f'0 0 {scene["width"]} {scene["height"]}')
    connectors = ET.SubElement(root, "g", id="connectors")
    shapes = ET.SubElement(root, "g", id="nodes")
    for index, edge in enumerate(scene["edges"]):
        group = ET.SubElement(connectors, "g", id=f"edge-{index + 1}")
        points = edge["points"]
        tip, previous = points[-1], points[-2]
        dx, dy = tip[0] - previous[0], tip[1] - previous[1]
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length
        depth = min(length * 0.65, 9)
        bx, by = tip[0] - depth * ux, tip[1] - depth * uy
        half = depth * 0.49
        shaft = ET.SubElement(group, "polyline", points=svg_points([*points[:-1], [bx, by]]),
                              fill="none", stroke=edge["stroke"], **{"stroke-width": "1.35"})
        if edge["dashed"]:
            shaft.set("stroke-dasharray", "5 4")
        head = [tip, [bx - uy * half, by + ux * half], [bx + uy * half, by - ux * half]]
        ET.SubElement(group, "polygon", points=svg_points(head), fill=edge["stroke"])
    for index, node in enumerate(scene["nodes"]):
        group = ET.SubElement(shapes, "g", id=f"node-{index + 1}")
        x, y = center(node)
        style = dict(fill=node["fill"], stroke=node["stroke"])
        if node["shape"] == "ellipse":
            ET.SubElement(group, "ellipse", cx=str(x), cy=str(y),
                          rx=str(node["w"] / 2), ry=str(node["h"] / 2), **style)
        elif node["shape"] != "text":
            radius = min(9, node["w"] / 2, node["h"] / 2) if node["shape"] == "rounded" else 0
            ET.SubElement(group, "rect", x=str(node["x"]), y=str(node["y"]), rx=str(radius),
                          width=str(node["w"]), height=str(node["h"]), **style)
        if node["label"]:
            size = node["size"]
            lines = node["label"].splitlines() or [node["label"]]
            text = ET.SubElement(group, "text", x=str(x), fill="#193A33",
                                 **{"font-family": "sans-serif", "font-size": str(size),
                                    "text-anchor": "middle"})
            baseline = y + size * 0.34 - (len(lines) - 1) * size * 0.6
            for line_index, line in enumerate(lines):
                ET.SubElement(text, "tspan", x=str(x),
                              y=str(baseline + line_index * size * 1.2)).text = line
    with filename.open("xb") as handle:
        ET.ElementTree(root).write(handle, encoding="utf-8", xml_declaration=True)


def svg_points(points):
    return " ".join(f"{x:.5f},{y:.5f}" for x, y in points)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="diagram JSON or a local vector SVG")
    parser.add_argument("output", type=Path, help="new .ai file to create")
    parser.add_argument("--run", action="store_true", help="send JSX to Illustrator via Apple Events")
    parser.add_argument("--progressive", action="store_true", help="reveal artwork in drawing order")
    parser.add_argument("--batch", type=int, default=1, help="objects per frame within a stage")
    parser.add_argument("--interval", type=float, default=0.25, help="seconds between drawing batches")
    parser.add_argument("--cursors", type=int, default=0, help="number of temporary canvas pointers")
    parser.add_argument("--gif", action="store_true", help="export Illustrator frames and assemble a GIF")
    parser.add_argument("--app", type=Path, help="Illustrator .app path for --run")
    args = parser.parse_args()
    if not 1 <= args.batch <= 100 or not 0 <= args.cursors <= 12 or not 0.05 <= args.interval <= 10:
        parser.error("batch must be 1–100, cursors 0–12, and interval 0.05–10")
    if args.gif and not args.run:
        parser.error("--gif requires --run")
    app = None
    if args.run:
        choices = sorted(Path("/Applications").glob("Adobe Illustrator */Adobe Illustrator.app"))
        app = args.app or (choices[-1] if choices else None)
        if app is None or not app.is_dir():
            parser.error("provide Illustrator’s .app path via --app")
    output = args.output.resolve()
    if output.suffix.lower() != ".ai":
        parser.error("output must end in .ai")
    script = output.with_suffix(".jsx")
    preview = output.with_suffix(".png")
    svg = output.with_suffix(".svg")
    gif = output.with_suffix(".gif")
    frames = output.with_name(output.stem + "-frames")
    if any(p.exists() for p in (script, output, preview, svg, gif, frames)):
        parser.error("choose a new filename for the JSX, SVG, AI and PNG")
    try:
        source = None
        if args.spec.suffix.lower() == ".svg":
            source = read_svg(args.spec)
            scene = dict(sourceSVG=str(svg), importName=uuid.uuid4().hex + ".svg")
        else:
            spec = json.loads(args.spec.read_text(encoding="utf-8"))
            if "artwork" in spec:
                scene = compile_artwork(spec, number, color)
            else:
                scene = compile_scene(spec)
        if args.gif:
            frames.mkdir()
        scene.update(progressive=args.progressive or args.gif or bool(args.cursors),
                     interval=args.interval, batch=args.batch, cursors=args.cursors,
                     frames=str(frames) if args.gif else None)
        scene.update(ai=str(output), png=str(preview))
        renderer = Path(__file__).with_name("render.jsx").read_text(encoding="utf-8")
        literal = json.dumps(scene, ensure_ascii=True, allow_nan=False)
        with script.open("x", encoding="utf-8") as handle:
            handle.write("var diagram = " + literal + ";\n" + renderer)
        if source is not None:
            with svg.open("xb") as handle:
                handle.write(source)
        elif "artwork" in scene:
            write_artwork_svg(scene, svg)
        else:
            write_svg(scene, svg)
    except (ValueError, KeyError, TypeError, OSError, ET.ParseError) as exc:
        parser.error(str(exc))
    print(script, svg, sep="\n", flush=True)
    if args.run:
        app_path = str(app.resolve()).replace(chr(92), chr(92) * 2).replace('"', chr(92) + '"')
        apple = ("on run argv\n"
                 f'tell application "{app_path}"\n'
                 'with timeout of 1800 seconds\n'
                 '«event miscDjxM» ((POSIX file (item 1 of argv)) as alias)\n'
                 'end timeout\nend tell\nend run')
        result = subprocess.run(["osascript", "-e", apple, str(script)], check=False)
        if result.returncode:
            parser.exit(result.returncode, f"Open {script} via Illustrator’s File > Scripts > Other Script.\n")
        if not output.is_file() or not preview.is_file():
            parser.error("Illustrator did not produce both expected files")
        print(output, preview, sep="\n")
        if args.gif:
            frame_files = sorted(frames.glob("*.png"))
            swift = Path(__file__).with_name("replay.swift")
            with tempfile.TemporaryDirectory(prefix="scientific-illustrator-swift-") as cache:
                subprocess.run(["swift", "-module-cache-path", cache, str(swift), str(gif),
                                str(args.interval), *map(str, frame_files), str(preview)], check=True)
            print(gif)


if __name__ == "__main__":
    main()
