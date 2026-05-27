---
name: daggerheart-md-format-fixer
description: Repair converted Daggerheart raw Markdown into clean source Markdown. Reads source/_raw.md, writes source/_original.md, and only fixes formatting without changing content.
---

# Daggerheart Markdown Format Fixer

`source/_raw.md` -> `source/_original.md`。第二步，专门修转换阶段留下的格式问题。

## 路径约定

`source/` 路径均相对于用户翻译项目根目录（如 `project/example/`）。

## 工作方式

启动 subagent，读取 `source/_raw.md`，复制为 `source/_original.md` 后在 `_original.md` 上修复。

硬约束：
- 只改格式、修饰符号、结构和位置
- 不改动具体文本内容
- 不要原地修改 `source/_raw.md`

## 总体原则

- 同一文档内，同类型内容的格式应尽量统一；统一优先于局部自以为“更正确”
- AI 必须真正阅读全文判断格式问题，不能只靠 `grep`、正则或局部片段匹配
- 优先参考文档中已经正确的同类段落、标题、表格或列表
- 若当前上游流程是手动模式，修复完成后应提示用户审阅 `_raw.md` 与 `_original.md` 的 diff

## 重点修复项

- 标题层级统一，同类型标题使用一致的 `#` 层级
- 被错误并入标题的正文或副标题，合理拆开
- 表格整理为标准 GFM：`|` 分列，`---|---` 分隔表头，单元格内不换行
- 粗体/斜体语法统一，同类术语的修饰形式保持一致
- 列表统一用 `-`，缩进一致，修正 OCR 识别出的 `•`等表头
- 正文段落之间用空行分隔
- 清理残留的 LaTeX、HTML 标签（如 `<br>`、`<div>`、`<table>`）和转义符号，只保留核心文本

## 输入输出

- 输入：`source/_raw.md`
- 输出：`source/_original.md`

## 使用位置

- 在 `daggerheart-translation-pipeline` 中，位于 `daggerheart-md-converter` 之后、术语提取之前
- 也可单独用于“修复 OCR / marker 导出的 Markdown 格式”场景
