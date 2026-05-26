# Daggerheart Translation Pipeline

TTRPG 翻译流水线：PDF → 中文 Markdown → 结构化 JSON。默认搭载 Daggerheart 术语表和模板。

## 安装

```bash
git clone https://github.com/ZZZZzzzzac/Daggerheart-translator.git
```

作为 DaggerHeart_CN 项目的 skill 子模块：

```bash
git submodule add https://github.com/ZZZZzzzzac/Daggerheart-translator.git .claude/skills/
```

## 依赖

- Python 3.x
- Gemini API key（方案A marker OCR）或 PaddleOCR（方案B，免费）
- 详见各 skill 文档

## 包含的 Skills

| Skill | 说明 |
|-------|------|
| `daggerheart-translation-pipeline` | 9 步翻译流水线（PDF→MD→翻译→JSON） |
| `daggerheart-chinese-writing` | 中文行文规范与术语统一 |
| `daggerheart-md-converter` | PDF/DOCX → Markdown |
| `daggerheart-glossary-extractor` | 从原文提取文档术语表 |
| `daggerheart-json-formatter` | 译文 → 结构化 JSON |

## 适配其他 TTRPG

替换以下 4 个文件即可适配其他规则书：

- `daggerheart-translation-pipeline/resources/terms-*.json` — 术语表
- `daggerheart-chinese-writing/REFERENCE.md` — 术语规范
- `daggerheart-chinese-writing/匕语/` — 行文规范
- `daggerheart-json-formatter/examples/template.md` — 输出模板

其余脚本通用，无需修改。

## 使用方式

加载 `daggerheart-translation-pipeline` skill，按 9 步流水线执行（详见该 skill 文档）。

## License

MIT
