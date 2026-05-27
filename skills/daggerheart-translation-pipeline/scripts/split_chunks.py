"""Split markdown into translation chunks using block-aware heuristics.

Usage:
    python split_chunks.py <input.md>
    python split_chunks.py <input.md> --min-chars 4000 --target-chars 5500 --max-chars 7000 --context-chars 1200
    python split_chunks.py <translated_chunks_dir> --merge --output <translated.md>

The splitter treats tables as first-class blocks, estimates size by non-blank
character count, and searches for the best boundary inside a min/target/max
window instead of hard-cutting on headings. Each chunk embeds previous/next
context inside explicit KILO markers so the merge step can later keep only the
KILO_TARGET section.
"""

import argparse
import datetime
import os
import re


BLANK = re.compile(r"^\s*$")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
TABLE_DELIM = re.compile(r"^\s*\|?\s*:?-{1,}:?\s*(?:\|\s*:?-{1,}:?\s*)+\|?\s*$")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]\s+|\d+\.\s+)")
IMAGE = re.compile(r"^\s*!\[[^\]]*\]\([^\)]*\)\s*$")
TITLE_CASE = re.compile(r"^(?:[A-Z][A-Za-z0-9'’/&()\-]*|[A-Z0-9]+)(?:\s+(?:[A-Z][A-Za-z0-9'’/&()\-]*|[A-Z0-9]+))*$")

DEFAULT_MIN_CHARS = 4000
DEFAULT_TARGET_CHARS = 5500
DEFAULT_MAX_CHARS = 7000
DEFAULT_CONTEXT_CHARS = 1200
LEGACY_CHARS_PER_LINE = 20

META_START = "[[[KILO_META_START]]]"
META_END = "[[[KILO_META_END]]]"
CTX_PREV_START = "[[[KILO_CONTEXT_PREV_START]]]"
CTX_PREV_END = "[[[KILO_CONTEXT_PREV_END]]]"
TARGET_START = "[[[KILO_TARGET_START]]]"
TARGET_END = "[[[KILO_TARGET_END]]]"
CTX_NEXT_START = "[[[KILO_CONTEXT_NEXT_START]]]"
CTX_NEXT_END = "[[[KILO_CONTEXT_NEXT_END]]]"


def is_blank(line):
    return BLANK.match(line) is not None


def is_table_row(line):
    return TABLE_ROW.match(line) is not None


def is_table_delim(line):
    return TABLE_DELIM.match(line) is not None


def is_list_item(line):
    return LIST_ITEM.match(line) is not None


def is_image(line):
    return IMAGE.match(line) is not None


def normalize_title_text(text):
    text = text.strip()
    text = re.sub(r"^#{1,6}\s*", "", text)
    text = text.replace("\\*", "*")
    text = re.sub(r"[*_`~]+", "", text)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -:\t")


def estimate_size(lines):
    return sum(len(line.strip()) for line in lines if line.strip())


def ensure_trailing_newline(text):
    if text and not text.endswith("\n"):
        return text + "\n"
    return text


def excerpt_head(text, max_chars):
    if not text.strip() or max_chars <= 0:
        return ""

    kept = []
    total = 0
    for line in text.splitlines(True):
        kept.append(line)
        total += len(line.strip())
        if total >= max_chars:
            break
    return ensure_trailing_newline("".join(kept))


def excerpt_tail(text, max_chars):
    if not text.strip() or max_chars <= 0:
        return ""

    kept = []
    total = 0
    for line in reversed(text.splitlines(True)):
        kept.append(line)
        total += len(line.strip())
        if total >= max_chars:
            break
    kept.reverse()
    return ensure_trailing_newline("".join(kept))


def render_blocks(blocks):
    return ensure_trailing_newline("".join(line for block in blocks for line in block["lines"]))


def wrap_chunk_text(label, input_path, start_line, end_line, target_text, prev_context, next_context):
    prev_context = ensure_trailing_newline(prev_context)
    target_text = ensure_trailing_newline(target_text)
    next_context = ensure_trailing_newline(next_context)

    return (
        f"{META_START}\n"
        f"source_file: {input_path}\n"
        f"chunk_label: {label}\n"
        f"target_line_start: {start_line}\n"
        f"target_line_end: {end_line}\n"
        f"{META_END}\n\n"
        f"{CTX_PREV_START}\n"
        f"{prev_context}"
        f"{CTX_PREV_END}\n\n"
        f"{TARGET_START}\n"
        f"{target_text}"
        f"{TARGET_END}\n\n"
        f"{CTX_NEXT_START}\n"
        f"{next_context}"
        f"{CTX_NEXT_END}\n"
    )


def extract_target_text(chunk_text, chunk_path):
    lines = chunk_text.splitlines(True)
    start_index = None
    end_index = None

    for idx, line in enumerate(lines):
        if line.strip() == TARGET_START:
            start_index = idx
            continue
        if line.strip() == TARGET_END and start_index is not None:
            end_index = idx
            break

    if start_index is None or end_index is None or end_index < start_index:
        raise ValueError(f"未找到目标区块标记: {chunk_path}")

    return ensure_trailing_newline("".join(lines[start_index + 1:end_index]))


def is_heading_like(lines, index):
    line = lines[index]
    stripped = line.strip()
    if not stripped:
        return False
    if is_table_row(stripped) or is_list_item(stripped) or is_image(stripped):
        return False
    if stripped.startswith("#"):
        return True

    plain = normalize_title_text(stripped)
    if not plain:
        return False
    if len(plain) > 90:
        return False

    prev_blank = index == 0 or is_blank(lines[index - 1])
    next_blank = index == len(lines) - 1 or is_blank(lines[index + 1])
    if not (prev_blank or next_blank):
        return False

    words = plain.split()
    if len(words) > 12:
        return False

    if plain.endswith((".", ",", ";", "?", "!", "。", "，", "；", "？", "！")):
        return False

    letters = [ch for ch in plain if ch.isalpha()]
    if letters:
        upper_ratio = sum(1 for ch in letters if ch.isupper()) / len(letters)
        if len(letters) >= 5 and upper_ratio >= 0.6:
            return True

    return TITLE_CASE.match(plain) is not None


def split_trailing_blanks(lines):
    cut = len(lines)
    while cut > 0 and is_blank(lines[cut - 1]):
        cut -= 1
    return lines[:cut], lines[cut:]


def make_block(block_type, lines, start_line, end_line):
    return {
        "type": block_type,
        "lines": list(lines),
        "start_line": start_line,
        "end_line": end_line,
        "size": estimate_size(lines),
    }


def read_table_block(lines, start_index):
    block_lines = []
    i = start_index
    while i < len(lines) and is_table_row(lines[i]):
        block_lines.append(lines[i])
        i += 1
    while i < len(lines) and is_blank(lines[i]):
        block_lines.append(lines[i])
        i += 1
    return block_lines, i


def read_heading_block(lines, start_index):
    block_lines = [lines[start_index]]
    i = start_index + 1
    while i < len(lines) and is_blank(lines[i]):
        block_lines.append(lines[i])
        i += 1
    return block_lines, i


def read_image_block(lines, start_index):
    block_lines = [lines[start_index]]
    i = start_index + 1
    while i < len(lines) and is_blank(lines[i]):
        block_lines.append(lines[i])
        i += 1
    return block_lines, i


def read_list_block(lines, start_index):
    block_lines = []
    i = start_index
    while i < len(lines):
        line = lines[i]
        if is_blank(line):
            block_lines.append(line)
            i += 1
            break
        if i != start_index and (is_heading_like(lines, i) or is_table_row(line) or is_image(line)):
            break
        if i != start_index and is_list_item(line) and block_lines and is_blank(block_lines[-1]):
            break
        block_lines.append(line)
        i += 1
    while i < len(lines) and is_blank(lines[i]):
        block_lines.append(lines[i])
        i += 1
    return block_lines, i


def read_paragraph_block(lines, start_index):
    block_lines = []
    i = start_index
    while i < len(lines):
        line = lines[i]
        if is_blank(line):
            block_lines.append(line)
            i += 1
            break
        if i != start_index and (is_heading_like(lines, i) or is_table_row(line) or is_image(line) or is_list_item(line)):
            break
        block_lines.append(line)
        i += 1
    while i < len(lines) and is_blank(lines[i]):
        block_lines.append(lines[i])
        i += 1
    return block_lines, i


def parse_blocks(lines):
    blocks = []
    leading_blanks = []
    i = 0
    while i < len(lines):
        if is_blank(lines[i]):
            if blocks:
                blocks[-1]["lines"].append(lines[i])
                blocks[-1]["end_line"] = i + 1
                blocks[-1]["size"] = estimate_size(blocks[-1]["lines"])
            else:
                leading_blanks.append(lines[i])
            i += 1
            continue

        start_line = i + 1 - len(leading_blanks)
        prefix = leading_blanks
        leading_blanks = []

        if is_table_row(lines[i]):
            block_lines, next_i = read_table_block(lines, i)
            block_type = "table"
        elif is_image(lines[i]):
            block_lines, next_i = read_image_block(lines, i)
            block_type = "image"
        elif is_heading_like(lines, i):
            block_lines, next_i = read_heading_block(lines, i)
            block_type = "heading"
        elif is_list_item(lines[i]):
            block_lines, next_i = read_list_block(lines, i)
            block_type = "list"
        else:
            block_lines, next_i = read_paragraph_block(lines, i)
            block_type = "paragraph"

        full_lines = prefix + block_lines
        block = make_block(block_type, full_lines, start_line, next_i)
        blocks.append(block)
        i = next_i

    if leading_blanks:
        if blocks:
            blocks[-1]["lines"].extend(leading_blanks)
            blocks[-1]["end_line"] = len(lines)
            blocks[-1]["size"] = estimate_size(blocks[-1]["lines"])
        else:
            blocks.append(make_block("blank", leading_blanks, 1, len(lines)))

    return blocks


def split_large_table_block(block, max_chars):
    content, trailing = split_trailing_blanks(block["lines"])
    if len(content) < 3:
        return [block]

    has_header = is_table_row(content[0]) and is_table_delim(content[1])
    if not has_header:
        return split_large_text_block(block, max_chars)

    header = content[:2]
    data_rows = content[2:]
    if not data_rows:
        return [block]

    row_infos = []
    row_start = block["start_line"] + 2
    for offset, row in enumerate(data_rows):
        row_infos.append((row, row_start + offset))

    groups = []
    current_rows = []
    current_size = estimate_size(header)
    group_start = block["start_line"]

    for row, source_line in row_infos:
        row_size = estimate_size([row])
        if current_rows and current_size + row_size > max_chars:
            group_lines = header + [item[0] for item in current_rows]
            groups.append(make_block("table", group_lines, group_start, current_rows[-1][1]))
            current_rows = []
            current_size = estimate_size(header)
            group_start = source_line

        current_rows.append((row, source_line))
        current_size += row_size

    if current_rows:
        group_lines = header + [row for row, _ in current_rows]
        group = make_block("table", group_lines, group_start, current_rows[-1][1])
        groups.append(group)

    if trailing:
        groups[-1]["lines"].extend(trailing)
        groups[-1]["end_line"] = block["end_line"]
        groups[-1]["size"] = estimate_size(groups[-1]["lines"])

    return groups


def split_large_text_block(block, max_chars):
    content, trailing = split_trailing_blanks(block["lines"])
    if len(content) <= 1:
        return [block]

    groups = []
    current_lines = []
    current_start = block["start_line"]
    line_no = block["start_line"]

    for line in content:
        candidate = current_lines + [line]
        if current_lines and estimate_size(candidate) > max_chars:
            groups.append(make_block(block["type"], current_lines, current_start, line_no - 1))
            current_lines = [line]
            current_start = line_no
        else:
            current_lines.append(line)
        line_no += 1

    if current_lines:
        groups.append(make_block(block["type"], current_lines, current_start, line_no - 1))

    if trailing:
        groups[-1]["lines"].extend(trailing)
        groups[-1]["end_line"] = block["end_line"]
        groups[-1]["size"] = estimate_size(groups[-1]["lines"])

    return groups


def split_oversized_blocks(blocks, max_chars):
    result = []
    for block in blocks:
        if block["size"] <= max_chars or block["type"] == "heading":
            result.append(block)
            continue
        if block["type"] == "table":
            result.extend(split_large_table_block(block, max_chars))
        else:
            result.extend(split_large_text_block(block, max_chars))
    return result


def boundary_score(blocks, start, end, size, target_chars):
    current = blocks[end]
    next_block = blocks[end + 1] if end + 1 < len(blocks) else None

    score = -abs(size - target_chars) / 40.0

    if current["type"] == "table":
        score += 120
    elif current["type"] == "list":
        score += 70
    elif current["type"] == "paragraph":
        score += 35
    elif current["type"] == "image":
        score += 15
    elif current["type"] == "heading":
        score -= 160

    if next_block and next_block["type"] == "heading":
        score += 90
    if next_block and next_block["type"] == "table":
        score += 85
    if start == end and current["type"] == "heading":
        score -= 200

    return score


def choose_chunk_end(blocks, start, min_chars, target_chars, max_chars):
    size = 0
    best_end = None
    best_score = None
    end = start
    soft_min_before_table = max(1200, int(min_chars * 0.5))

    while end < len(blocks):
        next_size = size + blocks[end]["size"]
        if size > 0 and next_size > max_chars and best_end is not None:
            break

        size = next_size
        next_block = blocks[end + 1] if end + 1 < len(blocks) else None
        allow_early_table_cut = (
            next_block is not None
            and next_block["type"] == "table"
            and size >= soft_min_before_table
        )

        if size >= min_chars or allow_early_table_cut:
            score = boundary_score(blocks, start, end, size, target_chars)
            if best_score is None or score > best_score:
                best_end = end
                best_score = score

        if size >= max_chars:
            break
        end += 1

    if best_end is not None:
        return best_end + 1
    return min(end + 1, len(blocks))


def chunk_blocks(blocks, min_chars, target_chars, max_chars):
    chunks = []
    start = 0
    while start < len(blocks):
        end = choose_chunk_end(blocks, start, min_chars, target_chars, max_chars)
        chunks.append(blocks[start:end])
        start = end

    if len(chunks) >= 2:
        last_size = sum(block["size"] for block in chunks[-1])
        prev_size = sum(block["size"] for block in chunks[-2])
        if last_size < min_chars * 0.5 and prev_size + last_size <= max_chars * 1.35:
            chunks[-2].extend(chunks[-1])
            chunks.pop()

    return chunks


def slugify(text):
    text = normalize_title_text(text).lower()
    text = re.sub(r"[^a-z0-9一-鿿]+", "_", text)
    return text.strip("_")[:40]


def first_nonblank_line(lines):
    for line in lines:
        if line.strip():
            return line
    return ""


def label_chunk(blocks, idx):
    for block in blocks[:8]:
        if block["type"] == "heading":
            label = slugify(first_nonblank_line(block["lines"]))
            if label:
                return f"{idx:02d}_{label}"
    for block in blocks:
        label = slugify(first_nonblank_line(block["lines"]))
        if label:
            return f"{idx:02d}_{label}"
    return f"{idx:02d}"


def chunk_file_sort_key(name):
    match = re.match(r"^(\d+)", name)
    order = int(match.group(1)) if match else 10**9
    return (order, name.lower())


def backup_existing_output_dir(outdir):
    if not os.path.exists(outdir):
        return None

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{outdir}_backup_{stamp}"
    suffix = 1
    while os.path.exists(backup):
        backup = f"{outdir}_backup_{stamp}_{suffix:02d}"
        suffix += 1

    os.replace(outdir, backup)
    return backup


def write_chunks(chunk_groups, input_path, context_chars):
    outdir = os.path.join(os.path.dirname(input_path), "_chunks")
    backup = backup_existing_output_dir(outdir)
    os.makedirs(outdir, exist_ok=True)

    if backup:
        print(f"Existing output moved to: {backup}")

    rendered_targets = [render_blocks(blocks) for blocks in chunk_groups]
    labels = [label_chunk(blocks, idx) for idx, blocks in enumerate(chunk_groups, 1)]
    written = []
    for idx, blocks in enumerate(chunk_groups, 1):
        label = labels[idx - 1]
        target_text = rendered_targets[idx - 1]
        prev_context = excerpt_tail(rendered_targets[idx - 2], context_chars) if idx > 1 else ""
        next_context = excerpt_head(rendered_targets[idx], context_chars) if idx < len(chunk_groups) else ""

        start_line = blocks[0]["start_line"]
        end_line = blocks[-1]["end_line"]
        chunk_text = wrap_chunk_text(
            label=label,
            input_path=input_path,
            start_line=start_line,
            end_line=end_line,
            target_text=target_text,
            prev_context=prev_context,
            next_context=next_context,
        )
        fpath = os.path.join(outdir, f"{label}.md")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(chunk_text)

        size = sum(block["size"] for block in blocks)
        written.append((label, start_line, end_line, size, len(chunk_text)))
        print(f"  {label}.md: L{start_line}-{end_line} ({size:5d} est chars, {len(chunk_text):6d} raw chars)")

    print(f"\n{len(written)} chunks written to {outdir}")
    return written


def default_merge_output_path(chunks_dir):
    parent = os.path.dirname(chunks_dir)
    basename = os.path.basename(chunks_dir.rstrip("\\/"))
    if basename == "_translated_chunks":
        return os.path.join(parent, "_translated.md")
    if basename == "_chunks":
        return os.path.join(parent, "_merged.md")
    return os.path.join(parent, f"{basename}_merged.md")


def merge_translated_chunks(chunks_dir, output_path=""):
    if not os.path.isdir(chunks_dir):
        raise ValueError(f"不是目录: {chunks_dir}")

    chunk_files = [
        name for name in os.listdir(chunks_dir)
        if name.endswith(".md") and not name.startswith("_prompt_")
    ]
    chunk_files.sort(key=chunk_file_sort_key)
    if not chunk_files:
        raise ValueError(f"目录中没有可合并的 chunk: {chunks_dir}")

    merged = []
    for name in chunk_files:
        path = os.path.join(chunks_dir, name)
        with open(path, "r", encoding="utf-8") as f:
            merged.append(extract_target_text(f.read(), path))

    final_text = "".join(merged)
    output_path = output_path or default_merge_output_path(chunks_dir)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_text)

    print(f"Merged {len(chunk_files)} chunks -> {output_path}")
    return output_path


def resolve_legacy_sizes(max_lines, min_chars, target_chars, max_chars):
    if max_lines is None:
        return min_chars, target_chars, max_chars

    if any(value is not None for value in (min_chars, target_chars, max_chars)):
        raise SystemExit("Do not mix --max-lines with --min-chars/--target-chars/--max-chars")

    target = max(2000, max_lines * LEGACY_CHARS_PER_LINE)
    min_value = int(target * 0.7)
    max_value = int(target * 1.3)
    print(f"Legacy --max-lines={max_lines} mapped to chars: min={min_value}, target={target}, max={max_value}")
    return min_value, target, max_value


def split_chunks(input_path, min_chars=DEFAULT_MIN_CHARS, target_chars=DEFAULT_TARGET_CHARS, max_chars=DEFAULT_MAX_CHARS, context_chars=DEFAULT_CONTEXT_CHARS):
    if not (0 < min_chars <= target_chars <= max_chars):
        raise ValueError("Require 0 < min_chars <= target_chars <= max_chars")

    with open(input_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    blocks = parse_blocks(lines)
    blocks = split_oversized_blocks(blocks, max_chars)
    chunk_groups = chunk_blocks(blocks, min_chars, target_chars, max_chars)
    return write_chunks(chunk_groups, input_path, context_chars)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Split markdown into translation chunks or merge translated chunks")
    parser.add_argument("input", help="Input .md file path, or chunk directory when using --merge")
    parser.add_argument("--merge", action="store_true", help="Merge translated chunk files by extracting only [[[KILO_TARGET_*]]] sections")
    parser.add_argument("--output", default="", help="Optional output path for merged markdown")
    parser.add_argument("--min-chars", type=int, default=None, help=f"Minimum chunk size in non-blank chars (default: {DEFAULT_MIN_CHARS})")
    parser.add_argument("--target-chars", type=int, default=None, help=f"Target chunk size in non-blank chars (default: {DEFAULT_TARGET_CHARS})")
    parser.add_argument("--max-chars", type=int, default=None, help=f"Maximum chunk size in non-blank chars (default: {DEFAULT_MAX_CHARS})")
    parser.add_argument("--context-chars", type=int, default=DEFAULT_CONTEXT_CHARS, help=f"Context chars to embed from adjacent chunks on each side (default: {DEFAULT_CONTEXT_CHARS})")
    parser.add_argument("--max-lines", type=int, default=None, help="Legacy compatibility flag. Roughly maps lines to char-based limits.")
    args = parser.parse_args()

    if args.merge:
        merge_translated_chunks(args.input, output_path=args.output)
        raise SystemExit(0)

    if args.max_lines is not None:
        min_chars, target_chars, max_chars = resolve_legacy_sizes(
            args.max_lines, args.min_chars, args.target_chars, args.max_chars
        )
    else:
        min_chars = args.min_chars if args.min_chars is not None else DEFAULT_MIN_CHARS
        target_chars = args.target_chars if args.target_chars is not None else DEFAULT_TARGET_CHARS
        max_chars = args.max_chars if args.max_chars is not None else DEFAULT_MAX_CHARS

    split_chunks(
        args.input,
        min_chars=min_chars,
        target_chars=target_chars,
        max_chars=max_chars,
        context_chars=args.context_chars,
    )
