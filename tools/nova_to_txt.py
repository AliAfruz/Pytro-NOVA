#!/usr/bin/env python3
"""Standalone CLI for lossless text exports from supported NOVA files."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from bridge import run


def main():
    parser = argparse.ArgumentParser(description='Convert supported .nox data to separate clean tab-separated .txt files')
    parser.add_argument('input', help='NOVA .nox file or technique-tagged CSV/TSV')
    parser.add_argument('--output', '-o', required=True, help='Parent output directory (must exist)')
    parser.add_argument('--dataset', help='Optional exact dataset name, e.g. "CV 1"')
    parser.add_argument('--technique', default='auto', help='For CSV/TSV inputs, e.g. GCD, OCP, CA')
    args = parser.parse_args()
    command = ['export-text', args.input, '--dir', args.output, '--technique', args.technique]
    if args.dataset:
        command += ['--dataset', args.dataset]
    try:
        result = run(command)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f'ERROR: {exc}\n')
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
