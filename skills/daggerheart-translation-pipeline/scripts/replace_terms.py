import json
import os
import re
import sys

# Ensure stdout uses UTF-8 on Windows (avoids GBK UnicodeEncodeError)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def _protect_urls_and_links(text):
    """Replace URLs and Markdown links with placeholders so terms in them won't be touched."""
    placeholders = []

    # Protect full Markdown links: [text](url) — the URL part
    link_pat = re.compile(r'(\[(?:\[??[^\[]*?\])\]\()([^)]+)(\))', re.IGNORECASE)
    def _link_replacer(m):
        url = m.group(2)
        idx = len(placeholders)
        placeholders.append(url)
        fenced_url = f"【【【URL_{idx}】】】"
        return m.group(1) + fenced_url + m.group(3)
    text = link_pat.sub(_link_replacer, text)

    # Protect bare URLs: https://... or www...
    bare_url_pat = re.compile(r'(https?://[^\s<>\"\']+|www\.[^\s<>\"\']+)', re.IGNORECASE)
    def _bare_replacer(m):
        url = m.group(0)
        idx = len(placeholders)
        placeholders.append(url)
        return f"【【URL_{idx}】】"
    text = bare_url_pat.sub(_bare_replacer, text)

    return text, placeholders


def _restore_urls_and_links(text, placeholders):
    """Restore the original URLs from placeholders."""
    for i, url in enumerate(placeholders):
        text = text.replace(f"【【【URL_{i}】】】", url)
        text = text.replace(f"【【URL_{i}】】", url)
    return text


def replace_terms(text, terms_file_path):
    if not os.path.exists(terms_file_path):
        return text

    try:
        with open(terms_file_path, 'r', encoding='utf-8') as f:
            terms_data = json.load(f)
    except Exception as e:
        print(f"Error loading terms file: {e}")
        return text

    # Normalize PDF→MD artifacts: \_ escapes prevent \b from matching
    # "_" is a regex word char, so \b doesn't fire between _ and a letter
    text = text.replace('\\_', '_')

    # Sort terms by length in descending order to avoid partial replacements
    # e.g., replacing "Spell" before "Spellcast Roll"
    terms_data.sort(key=lambda x: len((x.get('term') or '').strip()), reverse=True)

    # Protect URLs and links from term replacement
    replaced_text, url_placeholders = _protect_urls_and_links(text)
    replaced_terms = set()

    # Pattern to split text into protected 【...】 segments and unprotected segments
    PROTECTED_PATTERN = re.compile(r'(【[^】]*】)')

    for term_entry in terms_data:
        main_term = (term_entry.get('term') or '').strip()
        translation = (term_entry.get('translation') or '').strip()
        # Collect all terms to replace: main term + variants (optional)
        if 'variants' in term_entry:
            all_terms = [main_term] + [v.strip() for v in term_entry['variants'] if v.strip()]
        else:
            all_terms = [main_term]

        # VERY AGGRESSIVELY clean up newlines and extra spaces from the translation
        translation = " ".join(translation.split())

        if not main_term or not translation:
            continue

        for original_term in all_terms:
            # Escape the original term to handle regex special characters safely
            escaped_term = re.escape(original_term)

            # Build the pattern — per-term case_sensitive flag (optional, default: case-insensitive)
            try:
                per_term_cs = 'case_sensitive' in term_entry and term_entry['case_sensitive']
                flags = 0 if per_term_cs else re.IGNORECASE
                pattern = re.compile(r'\b' + escaped_term + r'\b', flags)
            except re.error as err:
                continue

            # Include usage note if available (optional)
            if 'note' in term_entry and term_entry['note'].strip():
                note = term_entry['note'].strip()
                note_suffix = f" — {note}"
            else:
                note = ''
                note_suffix = ''

            # Only replace in unprotected segments (outside 【】 brackets)
            # to prevent re-processing already-replaced content
            if not pattern.search(replaced_text):
                continue

            segments = PROTECTED_PATTERN.split(replaced_text)
            new_segments = []
            term_found = False
            for seg in segments:
                if PROTECTED_PATTERN.fullmatch(seg):
                    # This segment is already protected – leave it as-is
                    new_segments.append(seg)
                else:
                    replaced_seg = pattern.sub(lambda m: f"【{translation} ({m.group(0)}){' — ' + note if note else ''}】", seg)
                    if replaced_seg != seg:
                        term_found = True
                    new_segments.append(replaced_seg)
            replaced_text = ''.join(new_segments)
            if term_found:
                replaced_terms.add(original_term)

    # Restore URLs and links that were protected before term replacement
    replaced_text = _restore_urls_and_links(replaced_text, url_placeholders)
    return replaced_text

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="内联术语替换：将原文中的术语标记为【译文 (原文) - 注释】。\n默认不区分大小写；术语条目可设 \"case_sensitive\": true 逐条开启。")
    parser.add_argument("input", help="输入的 .md 文件路径")
    parser.add_argument("terms", help="术语表 JSON 文件路径")
    parser.add_argument("output", nargs="?", help="输出文件路径（可选）")
    args = parser.parse_args()
    input_arg = args.input
    terms_path = args.terms
    output_path = args.output

    # If the first arg is a file path, read from it, otherwise treat as raw text
    if os.path.exists(input_arg):
        with open(input_arg, 'r', encoding='utf-8') as f:
            input_text = f.read()
    else:
        input_text = input_arg

    result = replace_terms(input_text, terms_path)
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)
    else:
        print(result)
