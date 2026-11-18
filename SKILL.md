---
name: illustrator-figure-studio
description: Create editable scientific diagrams in Adobe Illustrator on macOS from a description or a reference figure. Use for native AI and SVG output, reference-guided vector reconstruction, or a step-by-step Illustrator drawing replay.
---

# Illustrator Figure Studio

Resolve tool paths relative to this skill folder. Read [USAGE.md](USAGE.md) for commands and the diagram format.

- For a simple flowchart, adapt [example.json](example.json).
- For a reference image, inspect it at native resolution and author an `artwork` JSON with editable text and geometry. Use the optional macOS OCR helper to locate labels. Check the OCR against the picture, preserve label blocks, and flag unreadable or approximated content.
- Recover quantitative plots from source data when values matter. Preserve reference attribution and disclose graphic substitutions.
- Generate to an unused target path. Use `--run` to render via the local Illustrator application, and `--gif` if the user requests replay. Check the final PNG for overlaps and the GIF for sequence and a clean last frame.
- If Apple Events are unavailable, the generated JSX can be run through Illustrator’s **File → Scripts → Other Script**. The SVG can also be opened directly.
