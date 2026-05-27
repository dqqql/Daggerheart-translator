# Daggerheart 翻译工具集

Daggerheart TTRPG 内容的翻译技能合集。英文 PDF/DOCX 输入，中文 Markdown + 结构化 JSON 输出。

## 目录

```
skills/                           # 技能源码
  daggerheart-translation-pipeline/  # 9 步翻译管线（主入口）
  daggerheart-chinese-writing/      # 中文行文规范
  daggerheart-glossary-extractor/   # 文档术语提取
  daggerheart-json-formatter/      # 译文 → 结构化 JSON
  daggerheart-md-converter/        # PDF/DOCX → Markdown
project/
  example/                        # 翻译项目模板（复制以新建项目）
```

## 安装

直接 clone，让你的 AI 助手完成安装（详见 `AGENTS.md`）：

```bash
git clone https://github.com/ZZZZzzzzac/Daggerheart-translator.git
```

然后告诉 AI："安装 Daggerheart-translator skills"。

## 使用

1. 复制 `project/example/` 为 `project/<你的项目名>/`
2. 将待翻译的 PDF/MD 文件放入项目的 `source/` 子目录
3. 在项目目录下告诉 AI："加载 daggerheart-translation-pipeline skill，翻译这个文件"

## 适配其他 TTRPG

替换以下文件即可适配其他规则书：

- `skills/daggerheart-translation-pipeline/resources/terms-*.json` — 术语表
- `skills/daggerheart-chinese-writing/REFERENCE.md` — 术语规范
- `skills/daggerheart-chinese-writing/匕语/` — 行文规范
- `skills/daggerheart-json-formatter/examples/template.md` — 输出模板

其余脚本通用，无需修改。

## License

MIT
