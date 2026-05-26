"""Post-process PaddleOCR-VL output: remove image divs, convert HTML tables to MD.

Usage:
    python paddle_postprocess.py <input.md> [--output <output.md>]
"""

import re
import sys
import argparse


IMAGE_DIV = re.compile(r'<div[^>]*>\s*<img[^>]*/?>\s*</div>', re.IGNORECASE)

TABLE_TAG = re.compile(r'<table[^>]*>(.*?)</table>', re.IGNORECASE | re.DOTALL)
ROW_TAG = re.compile(r'<tr[^>]*>(.*?)</tr>', re.IGNORECASE | re.DOTALL)
CELL_TAG = re.compile(r'<t[dh][^>]*>(.*?)</t[dh]>', re.IGNORECASE | re.DOTALL)

TEXT_DIV = re.compile(
    r'<div[^>]*>\s*<div[^>]*>\s*([^<]+?)\s*</div>\s*</div>', re.IGNORECASE
)


def remove_image_divs(text):
    return IMAGE_DIV.sub('', text)


def html_table_to_md(text):
    def convert(match):
        html = match.group(0)
        rows = ROW_TAG.findall(html)
        md_rows = []
        for i, row in enumerate(rows):
            cells = [c.strip() for c in CELL_TAG.findall(row)]
            if not cells:
                continue
            md_rows.append('| ' + ' | '.join(cells) + ' |')
            if i == 0:
                md_rows.append('| ' + ' | '.join(['---'] * len(cells)) + ' |')
        return '\n' + '\n'.join(md_rows) + '\n'

    return TABLE_TAG.sub(convert, text)


def demote_text_divs(text):
    """Convert nested <div>text</div> (table section headers) to bold markdown."""
    return TEXT_DIV.sub(r'\n**\1**\n', text)


def collapse_blanks(text):
    """More than 2 consecutive blank lines → 2."""
    return re.sub(r'\n{4,}', '\n\n\n', text)


def postprocess(text):
    text = remove_image_divs(text)
    text = demote_text_divs(text)
    text = html_table_to_md(text)
    text = re.sub(r'</?p[^>]*>', '', text)
    text = collapse_blanks(text)
    return text


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Post-process PaddleOCR-VL output')
    parser.add_argument('input', help='Input .md file')
    parser.add_argument('--output', '-o', help='Output .md file (default: overwrite input)')
    args = parser.parse_args()

    with open(args.input, 'r', encoding='utf-8') as f:
        content = f.read()

    result = postprocess(content)

    out_path = args.output or args.input
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(result)

    print(f'Done: {out_path}')
