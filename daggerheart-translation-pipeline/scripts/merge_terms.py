"""Merge multiple term JSON files with explicit priority order.

Usage:
    python merge_terms.py --terms game.json doc1.json [doc2.json ...] --output merged.json --original orig.md

Priority is left-to-right: earlier files win.

- Normal mode: conflicting translations are written to a separate report and the
  script exits non-zero so the user can review them.
- Auto mode (--auto-resolve): conflicts are still reported, but the higher-priority
  entry is kept automatically and the merged file is written.

Before merging, the first (highest-priority) terms file is filtered so only entries
that actually appear in the original text are kept.
"""

import argparse
import copy
import json
import re
import sys


if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def _terms_in_text(terms, text):
    """Return only terms whose main term or variants appear in text."""
    kept = []
    for t in terms:
        all_forms = [t['term']] + [v.strip() for v in (t.get('variants') or []) if v.strip()]
        for form in all_forms:
            try:
                if re.search(r'\b' + re.escape(form) + r'\b', text, re.IGNORECASE):
                    kept.append(t)
                    break
            except re.error:
                continue
    return kept


def _normalize_translation(text):
    return " ".join((text or '').split())


def _default_conflicts_output_path(output_path):
    if output_path.lower().endswith('.json'):
        return output_path[:-5] + '_conflicts.json'
    return output_path + '_conflicts.json'


def _make_conflict_report(priority_order, auto_resolve, conflicts):
    return {
        'priority_order': priority_order,
        'auto_resolve': auto_resolve,
        'conflict_count': len(conflicts),
        'conflicts': conflicts,
    }


def main(term_paths, output_path, orig_path, auto_resolve=False, conflicts_output_path=None):
    if not term_paths:
        print("No term files provided.")
        return 1

    conflicts_output_path = conflicts_output_path or _default_conflicts_output_path(output_path)

    with open(orig_path, 'r', encoding='utf-8') as f:
        orig = f.read()
    orig = orig.replace('\\_', '_')

    # Load all term files
    term_sets = []
    for path in term_paths:
        with open(path, 'r', encoding='utf-8') as f:
            term_sets.append(json.load(f))

    # Filter first (game base) against original text
    n_before = len(term_sets[0])
    term_sets[0] = _terms_in_text(term_sets[0], orig)
    n_after = len(term_sets[0])
    print(f'高优先级术语: {n_before}→{n_after}(-{n_before - n_after})')

    # Build merged dict: first file has the highest priority
    by_term = {}
    by_term_source = {}
    conflicts_by_term = {}

    for t in term_sets[0]:
        term = t.get('term')
        if not term:
            continue
        by_term[term] = copy.deepcopy(t)
        by_term_source[term] = term_paths[0]

    # Later files are lower priority. They cannot override earlier files.
    for i, terms in enumerate(term_sets[1:], 2):
        name = term_paths[i - 1]
        n_added = 0
        n_same = 0
        n_conflict = 0

        for t in terms:
            term = t.get('term')
            if not term:
                continue

            if term not in by_term:
                n_added += 1
                by_term[term] = copy.deepcopy(t)
                by_term_source[term] = name
                continue

            current = by_term[term]
            if _normalize_translation(current.get('translation')) == _normalize_translation(t.get('translation')):
                n_same += 1
                continue

            n_conflict += 1
            if term not in conflicts_by_term:
                conflicts_by_term[term] = {
                    'term': term,
                    'chosen': {
                        'source': by_term_source[term],
                        'entry': copy.deepcopy(current),
                    },
                    'ignored': [],
                }

            conflicts_by_term[term]['ignored'].append({
                'source': name,
                'entry': copy.deepcopy(t),
            })

        print(f'  文件{i}({name}): 新增{n_added}, 同译名重复{n_same}, 冲突{n_conflict}')

    conflicts = list(conflicts_by_term.values())
    with open(conflicts_output_path, 'w', encoding='utf-8') as f:
        json.dump(
            _make_conflict_report(term_paths, auto_resolve, conflicts),
            f,
            ensure_ascii=False,
            indent=2,
        )

    if conflicts and not auto_resolve:
        print(f'发现 {len(conflicts)} 条术语冲突，已写入: {conflicts_output_path}')
        print('普通模式不会自动裁决冲突；请先处理冲突后再重新运行。')
        return 1

    merged = list(by_term.values())
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    if conflicts and auto_resolve:
        print(f'自动模式: 按输入顺序优先级保留高优先级译名，冲突报告: {conflicts_output_path}')
    else:
        print(f'冲突报告: {conflicts_output_path}')

    print(f'最终: {len(merged)} 条术语, {len(conflicts)} 条冲突 → {output_path}')
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Merge term JSON files')
    parser.add_argument('-t', '--terms', nargs='+', required=True,
                        help='Term JSON files in priority order (earlier wins)')
    parser.add_argument('-o', '--output', required=True,
                        help='Output merged JSON path')
    parser.add_argument('-r', '--original', required=True,
                        help='Original markdown file (for filtering game terms)')
    parser.add_argument('--conflicts-output',
                        help='Conflict report JSON path (default: <output>_conflicts.json)')
    parser.add_argument('--auto-resolve', action='store_true',
                        help='Resolve conflicts automatically by keeping the highest-priority entry')
    args = parser.parse_args()

    sys.exit(main(args.terms, args.output, args.original, args.auto_resolve, args.conflicts_output))
