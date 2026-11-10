#!/usr/bin/env python3
"""Independent integrity checks for MIT Source Ledger transport packets."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path


def readjsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def sha(blob: bytes):
    return hashlib.sha256(blob).hexdigest()


def verify(root: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    sources = readjsonl(root / "sources.jsonl")
    segments = readjsonl(root / "verbatim_lines.jsonl")
    turns = readjsonl(root / "operator_turns.jsonl")
    quotes = readjsonl(root / "operator_exact_quotes.jsonl")
    lexical = readjsonl(root / "lexical_occurrences.jsonl")
    asserted = readjsonl(root / "relationships_asserted.jsonl")
    pending = readjsonl(root / "relationships_pending.jsonl")

    errors = []
    ids = {s["packet_source_id"] for s in sources}
    if len(ids) != len(sources):
        errors.append("duplicate source id")
    seg_ids = {s["segment_id"] for s in segments}
    if len(seg_ids) != len(segments):
        errors.append("duplicate segment id")
    by_source = defaultdict(list)
    for segment in segments:
        by_source[segment["source_id"]].append(segment)
        if segment["source_id"] not in ids:
            errors.append(f"orphan segment {segment['segment_id']}")

    for src in sources:
        sid = src["packet_source_id"]
        ordered = sorted(by_source.get(sid, []), key=lambda r: r["line_number"])
        data = bytearray()
        for i, segment in enumerate(ordered, start=1):
            if segment["line_number"] != i:
                errors.append(f"nonconsecutive line numbers {sid}")
            if segment["byte_start"] != len(data):
                errors.append(f"wrong byte_start in {segment['segment_id']}")
            b = segment["verbatim_line"].encode("utf-8")
            if segment["byte_end"] != len(data) + len(b):
                errors.append(f"wrong byte_end in {segment['segment_id']}")
            data.extend(b)
        if sha(data) != src["content_sha256"] or len(data) != src["text_bytes"]:
            errors.append(f"text source hash or size mismatch {sid}")
        blob_path = root / src["text_blob"]
        if not blob_path.is_file() or sha(blob_path.read_bytes()) != src["content_sha256"]:
            errors.append(f"text blob missing or corrupt {sid}")
        if src.get("raw_blob"):
            raw_path = root / src["raw_blob"]
            if not raw_path.is_file() or sha(raw_path.read_bytes()) != src["raw_sha256"]:
                errors.append(f"raw blob missing or corrupt {sid}")

    by_turn = {t["provided_key"]: t["verbatim_text"] for t in turns}
    if len(by_turn) != len(turns):
        errors.append("duplicate operator provided keys")
    for quote in quotes:
        text = by_turn.get(quote["turn_key"], "")
        string = quote["verbatim_quote"]
        for start in quote["codepoint_starts"]:
            if text[start:start+len(string)] != string:
                errors.append(f"wrong exact quote position: {quote['quote_id']}")
        if string not in text:
            errors.append(f"missing exact quote {quote['quote_id']}")

    for row in lexical:
        if row["segment_id"] not in seg_ids or row["source_id"] not in ids:
            errors.append(f"orphan lexical row {row}")

    actual_counts = {"source_entries":len(sources),
                     "unique_text_blobs":len({s["text_blob"] for s in sources}),
                     "unique_raw_blobs":len({s["raw_blob"] for s in sources if s.get("raw_blob")}),
                     "verbatim_line_segments":len(segments),
                     "operator_turns":len(turns),
                     "exact_quote_pointers":len(quotes),
                     "lexical_occurrences":len(lexical),
                     "asserted_relation_records":len(asserted),
                     "open_relation_records":len(pending)}
    for key, value in actual_counts.items():
        if manifest.get("counts",{}).get(key) != value:
            errors.append(f"manifest count mismatch: {key}")
    return {"status": "PASS" if not errors else "FAIL", "project":manifest.get("project"),
            "counts":actual_counts, "errors":errors}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("packet_dir", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.packet_dir)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        result = {"status":"FAIL", "errors":[str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
