---
name: daggerheart-md-converter
description: Convert Daggerheart PDF/DOCX sources to raw Markdown. Supports marker (local, Gemini API) and PaddleOCR-VL (free, manual). Outputs source/_raw.md.
---

# Daggerheart Markdown Converter

PDF/DOCX → `source/_raw.md`。第一步，只负责把源文件转成可编辑的原始 Markdown。

标题层级、表格、粗斜体、列表等结构修复不在本 skill 内处理，交给 `daggerheart-md-format-fixer`。

## 路径约定

`source/` 均相对于用户翻译项目的根目录（如 `project/example/`）。`scripts/` 相对于本 skill 根目录。下文命令中两者混用时，AI 需分别解析到对应绝对路径。

## 方案对比

| | 方案 A：marker | 方案 B：PaddleOCR-VL |
|---|---|---|
| 方式 | 本地自动化 | 网页手动上传 |
| 费用 | 需 Gemini API key | 免费 |
| 粗体/斜体 | 保留 | 丢失 |
| 图片漏字 | 偶尔发生 | 较少，但仍可能 |
| 表格 | MD 格式 | HTML（脚本转 MD） |
| 图片引用 | 本地文件 | 远程临时 URL（脚本清除） |

## 方案 A：marker（自动化）

需要 Gemini API key。使用项目 `.venv` 环境：

```bash
.venv/Scripts/marker_single "输入.pdf" --output_dir "输出目录" --use_llm --gemini_api_key %GEMINI_API_KEY%
```

将生成的 Markdown 整理为 `项目目录/source/_raw.md`。

转换完成后，手动检查输出中的图片引用，确认是否有文字被整块识别为图片而丢失（常见于图文交错的卡片区域）。如有漏字，先在 `_raw.md` 中补回缺失文本。

## 方案 B：PaddleOCR-VL（手动，免费）

1. 打开 https://aistudio.baidu.com/paddleocr
2. 上传 PDF，等待转换完成
3. 下载 Markdown，审查质量（标题层级、粗体/斜体、列表、URL 完整性）
4. 另存为 `项目目录/source/_raw.md`

PaddleOCR 输出含远程临时图片 URL 和 HTML 表格，需后处理：

```bash
python scripts/paddle_postprocess.py "source/_raw.md"
```

清除 `<div>` 图片标签，HTML `<table>` 转为 Markdown 表格。

## 其他格式

自行寻找办法转为 MD（pandoc、直接改后缀等）。

## 输出约定

本 skill 的终点是 `项目目录/source/_raw.md`。

后续若需把 `_raw.md` 修成可进入术语提取和分块流程的标准原文，调用 `daggerheart-md-format-fixer`。
