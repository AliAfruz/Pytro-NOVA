"""JSON command-line bridge between the native Qt GUI and the NOVA decoder.

Protocol (UTF-8 stdout, one JSON object, zero exit code on success):
    python bridge.py read INPUT.nox
    python bridge.py export INPUT.nox --file OUTPUT.csv --dataset "CV 1"
    python bridge.py export INPUT.nox --dir DIRECTORY
    python bridge.py export-package INPUT.nox --dir PARENT_DIRECTORY

Error: non-zero exit code, clear text on stderr. Neither the Qt app nor
this module executes deserialized .NET types or modifies the input file.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nox_reader import export_csv, read_nox
from analysis import analyze_dataset, export_peaks_csv
from nrbf_lite import NrbfError
from csv_package import export_csv_package
from text_export import export_text_package
from techniques import TECHNIQUES, read_technique_csv


def run(argv=None):
    p = argparse.ArgumentParser(description="Metrohm Autolab NOVA .nox Qt backend")
    sub = p.add_subparsers(dest="action", required=True)
    read = sub.add_parser("read", help="Read a file and return decoded datasets as JSON")
    read.add_argument("input")
    read.add_argument("--technique", choices=["auto",*TECHNIQUES], default="auto", help="Required technique when importing CSV/TSV")
    exp = sub.add_parser("export", help="Export one or all datasets using Python")
    exp.add_argument("input")
    destination = exp.add_mutually_exclusive_group(required=True)
    destination.add_argument("--file", help="Single CSV target path")
    destination.add_argument("--dir", help="Output directory for all datasets")
    exp.add_argument("--dataset", help="Exact dataset name, required with --file")
    exp.add_argument("--technique", choices=["auto",*TECHNIQUES], default="auto")
    package = sub.add_parser("export-package", help="Export one plot CSV per curve (three for EIS)")
    package.add_argument("input")
    package.add_argument("--dir", required=True, help="Parent directory for NEW CSV plot folder")
    package.add_argument("--dataset", help="Optional exact dataset name; omit for all plots")
    package.add_argument("--technique", choices=["auto",*TECHNIQUES], default="auto")
    text_package = sub.add_parser("export-text", help="Export clean tab-separated TXT files: all columns, XY plots, recorded segments")
    text_package.add_argument("input")
    text_package.add_argument("--dir", required=True, help="Existing parent directory for a NEW TXT export folder")
    text_package.add_argument("--dataset", help="Optional exact dataset name; omit for all datasets")
    text_package.add_argument("--technique", choices=["auto",*TECHNIQUES], default="auto")
    ana = sub.add_parser("analyze", help="Analyze peaks, time-trace metrics or EIS metrics")
    ana.add_argument("input")
    ana.add_argument("--dataset", required=True)
    ana.add_argument("--technique", choices=["auto",*TECHNIQUES], default="auto")
    ana.add_argument("--window", type=int, default=9, help="Odd Savitzky-Golay window, 5–51")
    ana.add_argument("--prominence-ua", type=float, default=0, help="Minimum peak prominence in µA; 0 = auto")
    ana.add_argument("--distance", type=int, default=6, help="Minimum separation in samples")
    ana.add_argument("--peaks-csv", help="Optional output CSV containing detected CV peaks")
    args = p.parse_args(argv)
    if args.action == "export":
        if args.file and not args.dataset:
            p.error("--dataset is required when exporting a single CSV file")
        if args.dir and args.dataset:
            p.error("--dataset is only used with --file")

    if Path(args.input).suffix.lower() in (".csv", ".tsv", ".txt"):
        if args.technique == "auto":
            raise ValueError("Select GCD, LSV, DPV, SWV, CA, CP or OCP when importing a CSV file")
        doc = read_technique_csv(args.input, args.technique)
    else:
        doc = read_nox(args.input)
    if args.action == "read":
        return doc

    datasets = doc["datasets"]
    if args.action == "export-package":
        return export_csv_package(doc, args.input, args.dir, dataset_name=args.dataset)
    if args.action == "export-text":
        return export_text_package(doc, args.input, args.dir, dataset_name=args.dataset)
    if args.action == "analyze":
        matches = [ds for ds in datasets if ds["name"] == args.dataset]
        if not matches:
            raise ValueError(f"Dataset {args.dataset!r} was not found in {Path(args.input).name}")
        ds = matches[0]
        params = ({"window": args.window, "prominence_ua": args.prominence_ua,
                   "min_distance": args.distance} if ds['kind'] in ('CV','LSV','DPV','SWV') else {})
        output = analyze_dataset(ds, **params)
        if args.peaks_csv:
            if ds['kind'] not in ('CV','LSV','DPV','SWV'):
                raise ValueError('Peak CSV export is available for voltage-sweep datasets only')
            export_peaks_csv(output, args.peaks_csv)
            output['exported_peaks_csv'] = str(Path(args.peaks_csv).resolve())
        return output
    if args.file:
        matches = [ds for ds in datasets if ds["name"] == args.dataset]
        if not matches:
            raise ValueError(f"Dataset {args.dataset!r} was not found in {Path(args.input).name}")
        target = Path(args.file)
        export_csv(matches[0], target)
        return {"ok": True, "paths": [str(target.resolve())], "datasets": 1}

    target_dir = Path(args.dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for ds in datasets:
        # Dataset names are generated by the decoder, but keep exported filenames safe.
        name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in ds["name"])
        target = target_dir / f"{Path(args.input).stem}_{name}.csv"
        export_csv(ds, target)
        paths.append(str(target.resolve()))
    return {"ok": True, "paths": paths, "datasets": len(paths)}


def main():
    # Windows often uses an ANSI console encoding, while QProcess reads UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        result = run()
        sys.stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n")
    except (OSError, NrbfError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
