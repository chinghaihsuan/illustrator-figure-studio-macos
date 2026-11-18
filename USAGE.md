# Illustrator Figure Studio usage

Create and reconstruct editable scientific figures in Adobe Illustrator on macOS.

Illustrator Figure Studio turns a JSON diagram or a local vector SVG into native Illustrator artwork. It supports reference-guided reconstruction with optional local OCR, editable labels and paths, progressive drawing, and GIF replay. Tested with Illustrator 2026 on macOS.

## Quick start

```sh
python3 draw.py example.json workflow.ai --run
```

Use a new output basename. Without `--run`, the command writes SVG and JSX. To run the JSX manually, choose **File → Scripts → Other Script** in Illustrator.

## 中文使用说明


给 Codex 一段图稿说明，让它按 `example.json` 的格式编写图稿，然后运行 `draw.py`。工具用 Python 3.8+ 标准库生成 SVG 和 Illustrator JSX，无需安装 Python 第三方包。

## 运行示例

在本目录的终端运行以下命令。输出文件名可自选，父目录需已存在。

```sh
python3 draw.py example.json workflow.ai
```

- `workflow.svg` 可以直接在 Illustrator 中打开，文本和路径保留为矢量对象；导入后检查字体和换行。
- `workflow.jsx` 可以经 Illustrator 的「文件 → 脚本 → 其他脚本」执行。它会在新文档里创建图形，保存为 `workflow.ai`，并导出 `workflow.png`。生成的 JSX 含本机绝对输出路径，移动项目后重新生成。
- 加 `--run` 可尝试通过 macOS Apple Events 自动执行脚本。首次运行可能需要在 macOS 中允许发起程序控制 Illustrator。如果装在非标准位置，加 `--app "/路径/Adobe Illustrator.app"`。自动调用受限时可以在 Illustrator 中手动运行已生成的 JSX。

针对 JSX 输出，每个节点和连接线都有自己的命名编组。多行节点标签放在同一个文本对象中。箭头由线和箭头形状组成。已有的同名输出会停下，重试时请选择新文件名。

## 图稿格式

- `width` 和 `height` 是画板尺寸，默认单位 pt。
- `layout` 接受 `horizontal`、`vertical` 或 `manual`。手工布局使用节点的 `x` 和 `y`，原点在画板左上角。
- 节点需要唯一 `id`。可选 `label`、`width`、`height`、`size`、`fill`、`stroke` 和 `shape`。形状支持 `rounded`、`rectangle`、`ellipse` 和 `text`。标签中的 JSON 转义 `\n` 产生换行。
- 省略 `edges` 时按顺序连线。显式指定 `edges` 可以画分支，每条边使用 `from` 和 `to` 引用节点，可加 `via` 坐标数组设置折点、`dashed` 设置虚线、`stroke` 设置线色。空数组表示无连线。
- 复杂排版可调整坐标和折点。请检查重叠和过长的标签。这个版本面向流程图和示意图，定量曲线应从原始数据单独绘制。

## 参考图重建与动画

先在 Codex 中附上参考图。Codex 根据观察编写 `artwork` 图稿，可选用本机 Vision OCR 提取文字和坐标。OCR 输出的是识别结果和左上角像素坐标，仍需结合原图检查。

```sh
swift read_reference.swift reference.png en-US zh-Hans > labels.json
```

`artwork` 图稿需要画板 `width`、`height` 和对象数组。每个对象都有唯一 `name`、`kind`，并可设置 `stage`。同组阶段按数组顺序绘制。

| 类型 | 字段 |
|---|---|
| `label` | `text`、`x`、`y`、`size`、`align`、`fill`、`font`。坐标为文字块对齐点及垂直中点，字体用本机 PostScript 名称 |
| `rect`、`ellipse` | `x`、`y`、`w`、`h`、`fill`、`stroke`、`weight`。矩形可设置 `radius` |
| `path` | `knots`、`closed`、`fill`、`stroke`、`weight`。锚点为 `[x,y]`，贝塞尔锚点为 `[x,y,inX,inY,outX,outY]` |

图形至少要有填充或描边。所有坐标均从画板左上角开始。添加 `--progressive` 可在 Illustrator 中逐步绘制，`--batch` 控制每批对象数量，`--interval` 控制批次间的停顿。加 `--cursors` 可显示多枚临时彩色指针，数量也受每批图元数限制。指针出现在画板和早期回放帧中，保存最终图稿之前会移除。

```sh
python3 draw.py example.json replay.ai --run \
  --progressive --batch 6 --interval 0.28 --cursors 5 --gif
```

GIF 使用 Illustrator 导出的 PNG 帧和 macOS ImageIO 生成，需 Swift（Xcode Command Line Tools）。逐帧 PNG 放在同名 `-frames` 目录，最后一帧停留至少 1.8 秒。批次停顿之外还有 Illustrator 导出耗时。


### 已有 SVG 的逐组绘制

也可以把本地矢量 SVG 作为输入。Illustrator 通过自身的 SVG 导入器打开副本，再按图层中对象的堆叠顺序显示图元。顶层组作为一个绘制单位。SVG 禁用脚本、位图和外部引用。导入后的文本和渐变表现取决于 Illustrator 和本机字体。

```sh
python3 draw.py demo.svg imported.ai --run --batch 1 --interval 0.2 --cursors 1 --gif
```
