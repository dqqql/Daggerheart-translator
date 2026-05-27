"""
给翻译 subagent 组装提示词。

结构严格按 pipeline 第五步的三段：
  1. 任务说明（写死在本文件）
  2. 内联标记说明（写死在本文件）
  3. 行文规范 = daggerheart-chinese-writing/SKILL.md 全文（从文件加载）

大体积内容通过文件路径引用，由 subagent 自行 Read：
  - REFERENCE.md → 给路径让 subagent 读
  - 待翻译 chunk → 给路径让 subagent 读

修改提示词 = 修改对应的源文件：
  - 任务说明 / 标记规则 → 改本文件
  - 行文规范 → 改 daggerheart-chinese-writing/SKILL.md
  - 术语参考 → 改 daggerheart-chinese-writing/REFERENCE.md
"""

import os
import re

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRITING_SKILL_DIR = os.path.join(os.path.dirname(SKILL_DIR), "daggerheart-chinese-writing")

# 预计算的绝对路径，注入提示词让 subagent 自行 Read
REFERENCE_PATH = os.path.join(WRITING_SKILL_DIR, "REFERENCE.md")


def _strip_frontmatter(text: str) -> str:
    """去掉 YAML frontmatter（--- ... ---）"""
    return re.sub(r'^---\n.*?\n---\n*', '', text, count=1, flags=re.DOTALL)


def _load_skill_md() -> str:
    """加载 daggerheart-chinese-writing/SKILL.md（行文规范本体）"""
    path = os.path.join(WRITING_SKILL_DIR, "SKILL.md")
    with open(path, "r", encoding="utf-8") as f:
        return _strip_frontmatter(f.read()).strip()


# ====================================================================
# 第 1 段：任务说明（写死，改这里）
# ====================================================================
PART1_TASK = """这是一份 Daggerheart TTRPG 游戏文本的英译中工作。全文已被分块，你负责翻译其中一块。保持原始 Markdown 格式，只输出译文。"""


# ====================================================================
# 第 2 段：内联标记说明（写死，改这里）
# ====================================================================
PART2_MARKUP = """## 内联标记说明

原文中的部分术语已被标记, 格式为：【译文 (原文) — 注释】

各部分含义：
- `译文` — 关键字替换提供的推荐翻译，多个以 `/` 分隔时表示多义词
- `原文` — 被替换的英文原词。如果译文与注释都不合适，则将原文放回上下文里直接翻译
- `注释` — 对该词的用法说明、上下文提示或固定写法指引

翻译时：
- 多义词必须通读段落上下文，选择符合当前含义的译法
- 如果所有备选译法都不适合当前上下文，忽略标记按原文重新翻译
- **输出译文不得保留任何【】标记和标记内的英文括号原文。所有标记在翻译时必须被解析为最终中文译法（采用推荐译文或自行翻译），原标记整体替换为纯中文。英文原文和注释仅作为翻译参考，不得出现在最终输出中。译文应是纯净的中文 Markdown。**"""


# ====================================================================
# 第 3 段：行文规范（SKILL.md 内联；REFERENCE.md 给路径）
# ====================================================================
def _build_part3() -> str:
    skill_md = _load_skill_md()
    return f"""## 行文规范

以下是完整的行文规范，所有翻译必须严格遵守。

{skill_md}

---
术语详细参考表在以下文件中，请自行 Read 查阅：
{REFERENCE_PATH}

翻译游戏机制相关文本时（资源动词、掷骰修正、伤害修正、状态等），请先查阅该文件中的对应表格，确保用词一致。"""


# ====================================================================
# 拼接：输入内容文件路径 + 输出要求
# ====================================================================
_TAIL_WITH_PATH = """## 输入内容

待翻译的 chunk 文件路径：
{chunk_path}

请用 Read 工具读取该文件，获取完整原文，然后翻译。

chunk 文件中已包含特殊标记包装的相邻块上下文：

- `[[[KILO_CONTEXT_PREV_START]]] ... [[[KILO_CONTEXT_PREV_END]]]`
- `[[[KILO_TARGET_START]]] ... [[[KILO_TARGET_END]]]`
- `[[[KILO_CONTEXT_NEXT_START]]] ... [[[KILO_CONTEXT_NEXT_END]]]`

注意：
- 所有 `[[[KILO_...]]]` 标记行必须逐字原样保留，不得翻译、删除或改写
- 可以翻译三个区段中的正文内容；后续合并脚本只会保留 `[[[KILO_TARGET_START]]]` 与 `[[[KILO_TARGET_END]]]` 之间的内容
- 当前输出里必须继续保留这三段完整结构，否则后续无法自动合并

## 输出要求

将上面的输入内容翻译为中文，输出纯净的中文 Markdown。

规则：
- 移除所有【】标记及其内部英文原文，输出纯中文
- 不在中文后添加英文括号备注，中文译文就是最终输出
- 保留所有 Markdown 格式（标题层级、代码块、表格、粗体/斜体）
- 保留图片链接 `![…](_… )` 原样
- 保留作者名、作品名、URL 等专有名词原文
- 保留数据块缩写（ATK、HP、Stress、mag、phy）
- 保留骰子表达式（如 **1d10+6**）
- 保留代词标记（如 (she/her)、(he/him)）

将翻译结果写入文件：
{output_path}"""


# ====================================================================
# 组装函数
# ====================================================================
def build_prompt(chunk_path: str, output_path: str = "", chunk_notes: str = "") -> str:
    """生成翻译 subagent 的完整提示词。

    Args:
        chunk_path: 待翻译 chunk 文件的绝对路径
        output_path: 输出译文文件的绝对路径（如不指定，自动推导）
        chunk_notes: 可选。本块特有的注意事项
    """
    if not output_path:
        # 自动推导：chunks → translated_chunks
        chunk_dir = os.path.dirname(chunk_path)
        chunk_name = os.path.basename(chunk_path)
        output_dir = chunk_dir.replace("_chunks", "_translated_chunks")
        output_path = os.path.join(output_dir, chunk_name)

    parts = [
        PART1_TASK,
        PART2_MARKUP,
        _build_part3(),
    ]

    if chunk_notes.strip():
        parts.append("## 本块特别注意\n\n" + chunk_notes.strip())

    parts.append(
        _TAIL_WITH_PATH.format(
            chunk_path=chunk_path,
            output_path=output_path,
        )
    )

    return "\n\n".join(parts)


# ====================================================================
# CLI：python translation_prompt.py <chunk.md> [--notes "..."]
# ====================================================================
if __name__ == "__main__":
    import sys
    args = sys.argv[1:]

    chunk_notes = ""
    if "--notes" in args:
        idx = args.index("--notes")
        chunk_notes = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    if not args:
        print("Usage: python translation_prompt.py <chunk_file.md> [--notes \"...\"]")
        sys.exit(1)

    chunk_path = os.path.abspath(args[0])
    prompt = build_prompt(chunk_path, chunk_notes=chunk_notes)
    print(prompt)

    # 同时写入 _prompt_xxx.md 方便查看
    out_dir = os.path.dirname(chunk_path) or "."
    basename = os.path.splitext(os.path.basename(chunk_path))[0]
    prompt_path = os.path.join(out_dir, f"_prompt_{basename}.md")
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"\n\n# 提示词已保存至: {prompt_path}")
