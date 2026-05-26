---
name: daggerheart-md-converter
description: Convert Daggerheart PDF/DOCX sources to Markdown. Supports marker (local, Gemini API) and PaddleOCR-VL (free, manual). Outputs source/_original.md.
---

# Daggerheart Markdown Converter

PDF/DOCX → `source/_original.md`。第一步，格式最易出错，注意检查输出质量。

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

转换完成后，手动检查输出中的图片引用，确认是否有文字被整块识别为图片而丢失（常见于图文交错的卡片区域）。如有漏字，手动补回 MD。

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

原始 MD 保存为 `项目目录/source/_raw.md`。

---

## AI 修复原文格式

转换后的 MD 总会有格式错误——转义字符残留、表格断行、标题层级混乱、附录噪声混入正文、OCR 错误等。这些错误零散、语义性强，正则脚本难以穷举，用 AI 处理。

启动 subagent，读 `_raw.md`，按以下三部分指引逐项修复，直接写入。**只改格式/修饰符号/位置，不改动具体文本内容。** 

### 总体原则
- 同一文档内，同类型内容的格式应该一致。AI 应主动在文中寻找已正确格式化的同类内容作为参照. 保证格式"统一"比"正确"重要.
- 下面的例子无法涵盖所有格式错误, AI需要自己判断内容是否有错误, 故AI必须真正读取文章内容, 而不是用grep之类的匹配.
- 不要原地修改, 复制一份`_raw.md`为`_original.md`, 在上面修改. 修改后diff一下. 如果在非自动模式, 则告知用户进行diff审阅

### 具体例子

- **标题层级**：同类型的标题的`#`层级应相同
- **标题合并**: 有时正文/副标题会被错误与真正的标题合并, 合理切开.
- **表格**：标准 GFM 格式，`|` 分隔列，`---|---` 分隔表头与数据行，单元格内不换行
- **粗体/斜体**：转换的粗体(**xx**)斜体(*x*) 语法嵌套应当一致, 同类术语应该有统一的粗体斜体修饰.
- **列表**：列表统一用 `-`，缩进一致. 有时列表头会被识别为圆点`•`
- **段落**：正文段落之间空行分隔
- **残留**: latex, html标签（<br>/<div>/<table>等）, 转义符号残留. 全部去除, 只保留核心文本
