// Executed by Adobe Illustrator. Input coordinates are points from the top left.
(function (scene) {
    var ai = new File(scene.ai);
    var png = new File(scene.png);
    if (ai.exists || png.exists) {
        throw new Error("Choose a fresh output filename.");
    }

    function rgb(hex) {
        var result = new RGBColor();
        result.red = parseInt(hex.substr(1, 2), 16);
        result.green = parseInt(hex.substr(3, 2), 16);
        result.blue = parseInt(hex.substr(5, 2), 16);
        return result;
    }

    var doc;
    var connectors;
    var objects;
    if (scene.sourceSVG) {
        var temporary = new File(Folder.temp.fsName + "/" + scene.importName);
        if (temporary.exists || !new File(scene.sourceSVG).copy(temporary)) {
            throw new Error("Could not stage SVG for native import.");
        }
        try {
            doc = app.open(temporary);
        } finally {
            temporary.remove();
        }
    } else {
        doc = app.documents.add(DocumentColorSpace.RGB, scene.width, scene.height);
        connectors = doc.layers[0];
        connectors.name = "Connectors";
        objects = doc.layers.add();
        objects.name = "Nodes";
    }
    var board = doc.artboards[0].artboardRect;
    var canvasWidth = board[2] - board[0];
    var canvasHeight = board[1] - board[3];

    function point(x, y) {
        return [board[0] + x, board[1] - y];
    }

    function path(group, points, closed) {
        var coordinates = [];
        for (var i = 0; i < points.length; i++) {
            coordinates.push(point(points[i][0], points[i][1]));
        }
        var item = group.pathItems.add();
        item.setEntirePath(coordinates);
        item.closed = closed;
        return item;
    }

    function drawEdge(edge) {
        var group = connectors.groupItems.add();
        group.name = edge.name;
        var pts = edge.points;
        var tip = pts[pts.length - 1];
        var previous = pts[pts.length - 2];
        var dx = tip[0] - previous[0];
        var dy = tip[1] - previous[1];
        var length = Math.sqrt(dx * dx + dy * dy);
        var depth = Math.min(length * 0.65, 9);
        var ux = dx / length;
        var uy = dy / length;
        var base = [tip[0] - depth * ux, tip[1] - depth * uy];
        var shaft = path(group, pts.slice(0, -1).concat([base]), false);
        shaft.filled = false;
        shaft.stroked = true;
        shaft.strokeWidth = 1.35;
        shaft.strokeColor = rgb(edge.stroke);
        if (edge.dashed) {
            shaft.strokeDashes = [5, 4];
        }
        var half = depth * 0.49;
        var head = path(group, [tip, [base[0] - uy * half, base[1] + ux * half],
                                    [base[0] + uy * half, base[1] - ux * half]], true);
        head.stroked = false;
        head.filled = true;
        head.fillColor = rgb(edge.stroke);
        return group;
    }

    function drawNode(node) {
        var group = objects.groupItems.add();
        group.name = node.id;
        var origin = point(node.x, node.y);
        var left = origin[0];
        var top = origin[1];
        var shape;
        if (node.shape === "rounded") {
            var radius = Math.min(9, node.w / 2, node.h / 2);
            shape = group.pathItems.roundedRectangle(top, left, node.w, node.h, radius, radius);
        } else if (node.shape === "rectangle") {
            shape = group.pathItems.rectangle(top, left, node.w, node.h);
        } else if (node.shape === "ellipse") {
            shape = group.pathItems.ellipse(top, left, node.w, node.h);
        }
        if (shape) {
            shape.filled = true;
            shape.fillColor = rgb(node.fill);
            shape.stroked = true;
            shape.strokeColor = rgb(node.stroke);
            shape.strokeWidth = 1;
        }
        if (node.label) {
            var frame = doc.textFrames.pointText(origin);
            frame.name = node.id + " label";
            frame.move(group, ElementPlacement.PLACEATBEGINNING);
            var label = node.label.replace(/\r\n|\n/g, "\r");
            frame.contents = label;
            var attributes = frame.textRange.characterAttributes;
            attributes.size = node.size;
            attributes.fillColor = rgb("#193A33");
            frame.textRange.paragraphAttributes.justification = Justification.CENTER;
            var bounds = frame.geometricBounds;
            frame.translate(left + node.w / 2 - (bounds[0] + bounds[2]) / 2,
                            top - node.h / 2 - (bounds[1] + bounds[3]) / 2);
            if (frame.contents !== label) {
                throw new Error("Text verification failed: " + node.id);
            }
        }
        return group;
    }

    function horizontalAnchor(bounds, alignment) {
        if (alignment === "left") { return bounds[0]; }
        if (alignment === "right") { return bounds[2]; }
        return (bounds[0] + bounds[2]) / 2;
    }

    function drawArtwork(item) {
        var group = objects.groupItems.add();
        group.name = item.name;
        var origin;
        var shape;
        if (item.kind === "label") {
            origin = point(item.x, item.y);
            var frame = doc.textFrames.pointText(origin);
            frame.move(group, ElementPlacement.PLACEATBEGINNING);
            frame.name = item.name + " text";
            var expected = item.text.replace(/\r\n|\n/g, "\r");
            frame.contents = expected;
            var attr = frame.textRange.characterAttributes;
            attr.textFont = app.textFonts.getByName(item.font);
            attr.size = item.size;
            attr.fillColor = rgb(item.fill);
            var choices = {left: Justification.LEFT, center: Justification.CENTER,
                           right: Justification.RIGHT};
            frame.textRange.paragraphAttributes.justification = choices[item.align];
            var b = frame.geometricBounds;
            frame.translate(origin[0] - horizontalAnchor(b, item.align),
                            origin[1] - (b[1] + b[3]) / 2);
            var placed = frame.geometricBounds;
            if (Math.abs(horizontalAnchor(placed, item.align) - origin[0]) > 0.15 ||
                Math.abs((placed[1] + placed[3]) / 2 - origin[1]) > 0.15) {
                throw new Error("Text placement verification failed: " + item.name);
            }
            if (frame.contents !== expected) {
                throw new Error("Text verification failed: " + item.name);
            }
            return group;
        }
        if (item.kind === "path") {
            shape = path(group, item.knots, item.closed);
            for (var k = 0; k < item.knots.length; k++) {
                var knot = item.knots[k];
                if (knot.length === 6) {
                    shape.pathPoints[k].leftDirection = point(knot[2], knot[3]);
                    shape.pathPoints[k].rightDirection = point(knot[4], knot[5]);
                }
            }
        } else {
            origin = point(item.x, item.y);
            if (item.kind === "ellipse") {
                shape = group.pathItems.ellipse(origin[1], origin[0], item.w, item.h);
            } else if (item.radius > 0) {
                shape = group.pathItems.roundedRectangle(origin[1], origin[0], item.w, item.h,
                                                         item.radius, item.radius);
            } else {
                shape = group.pathItems.rectangle(origin[1], origin[0], item.w, item.h);
            }
        }
        shape.filled = item.fill !== null;
        shape.stroked = item.stroke !== null;
        if (shape.filled) { shape.fillColor = rgb(item.fill); }
        if (shape.stroked) {
            shape.strokeColor = rgb(item.stroke);
            shape.strokeWidth = item.weight;
            shape.strokeCap = StrokeCap.ROUNDENDCAP;
            shape.strokeJoin = StrokeJoin.ROUNDENDJOIN;
        }
        return group;
    }

    var options = new ExportOptionsPNG24();
    options.artBoardClipping = true;
    options.antiAliasing = true;
    options.transparency = false;
    options.horizontalScale = 150;
    options.verticalScale = 150;

    function collectSvgItems(layers, result) {
        for (var layerIndex = layers.length - 1; layerIndex >= 0; layerIndex--) {
            var layer = layers[layerIndex];
            if (!layer.visible || layer.locked) { continue; }
            for (var itemIndex = layer.pageItems.length - 1; itemIndex >= 0; itemIndex--) {
                var pageItem = layer.pageItems[itemIndex];
                if (pageItem.parent.typename !== "Layer" || pageItem.hidden || pageItem.locked) {
                    continue;
                }
                result.push({type: "import", value: pageItem, stage: 0});
            }
            collectSvgItems(layer.layers, result);
        }
    }

    var sequence = [];
    if (scene.sourceSVG) {
        if (doc.rasterItems.length || doc.placedItems.length) {
            throw new Error("Illustrator imported raster or linked content from the SVG.");
        }
        collectSvgItems(doc.layers, sequence);
        if (!sequence.length || sequence.length > 9999) {
            throw new Error("Expected 1 to 9999 visible, editable SVG drawing units.");
        }
        if (scene.progressive) {
            for (var u = 0; u < sequence.length; u++) {
                sequence[u].value.hidden = true;
            }
        }
    } else if (scene.artwork) {
        for (var a = 0; a < scene.artwork.length; a++) {
            sequence.push({type: "artwork", value: scene.artwork[a], stage: scene.artwork[a].stage});
        }
    } else {
        for (var e = 0; e < scene.edges.length; e++) {
            sequence.push({type: "edge", value: scene.edges[e], stage: 0});
        }
        for (var n = 0; n < scene.nodes.length; n++) {
            sequence.push({type: "node", value: scene.nodes[n], stage: 0});
        }
    }

    var cursorLayer = scene.cursors ? doc.layers.add() : null;
    var palette = ["#774DE6", "#E75348", "#087DC1", "#D46E0C", "#00846F", "#AC387D"];
    if (cursorLayer) { cursorLayer.name = "Temporary replay pointers"; }

    function addPointer(bounds, index) {
        var x = Math.max(6, Math.min(canvasWidth - 25, bounds[2] - board[0]));
        var y = Math.max(6, Math.min(canvasHeight - 25, board[1] - bounds[1]));
        var group = cursorLayer.groupItems.add();
        var cursor = path(group, [[x,y],[x+2,y+17],[x+6,y+13],[x+10,y+21],
                                  [x+14,y+19],[x+10,y+11],[x+17,y+11]], true);
        cursor.fillColor = rgb(palette[index % palette.length]);
        cursor.filled = true;
        cursor.strokeColor = rgb("#FFFFFF");
        cursor.strokeWidth = 1.4;
        cursor.stroked = true;
    }

    var step = 0;
    var batchGroups = [];
    try {
        for (var i = 0; i < sequence.length; i++) {
            var entry = sequence[i];
            var groupItem;
            if (entry.type === "import") {
                groupItem = entry.value;
                if (scene.progressive) { groupItem.hidden = false; }
            } else if (entry.type === "artwork") {
                groupItem = drawArtwork(entry.value);
            } else if (entry.type === "edge") {
                groupItem = drawEdge(entry.value);
            } else {
                groupItem = drawNode(entry.value);
            }
            if (!scene.progressive) { continue; }
            batchGroups.push(groupItem);
            var last = i === sequence.length - 1;
            if (!last && batchGroups.length < scene.batch &&
                         sequence[i + 1].stage === entry.stage) {
                continue;
            }
            if (cursorLayer) {
                var count = Math.min(scene.cursors, batchGroups.length);
                for (var c = 0; c < count; c++) {
                    addPointer(batchGroups[Math.floor(c * batchGroups.length / count)].visibleBounds, c);
                }
            }
            app.redraw();
            if (scene.frames) {
                step++;
                var frameName = ("0000" + step).slice(-4);
                doc.exportFile(new File(scene.frames + "/" + frameName + ".png"), ExportType.PNG24, options);
            }
            $.sleep(Math.round(scene.interval * 1000));
            if (cursorLayer) {
                while (cursorLayer.groupItems.length) { cursorLayer.groupItems[0].remove(); }
            }
            batchGroups.length = 0;
        }
    } catch (error) {
        if (cursorLayer) {
            try { cursorLayer.remove(); } catch (cleanupError) {}
        }
        throw new Error("Drawing object " + (i + 1) + " / " + sequence.length +
                        ": " + error.message + " (line " + error.line + ")");
    }
    if (cursorLayer) { cursorLayer.remove(); }

    if (!scene.sourceSVG && sequence.length !== objects.groupItems.length + connectors.groupItems.length) {
        throw new Error("Object group count verification failed.");
    }
    doc.saveAs(ai, new IllustratorSaveOptions());
    doc.exportFile(png, ExportType.PNG24, options);
} (diagram));
