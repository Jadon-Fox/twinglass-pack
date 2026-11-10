#!/usr/bin/env python3
"""Offline, source-preserving, cross-project handoff builder. Python stdlib only.

This builds transport-local source IDs, not real MIT/HANID/SSRL identifiers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0.0"


def die(message: str) -> None:
    raise ValueError(message)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        die(f"Unable to read JSON file {path}: {exc}")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def output_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def output_jsonl(path: Path, values: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def resolve_input(root: Path, relative: str) -> Path:
    if not relative or not isinstance(relative, str):
        die("A nonempty text_path is required for each source")
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root.resolve()):
        die(f"Path must remain within input root: {relative}")
    if not candidate.is_file():
        die(f"Input file not found: {candidate}")
    return candidate


def read_text_strict(path: Path) -> tuple[bytes, str]:
    raw = path.read_bytes()
    try:
        return raw, raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        die(f"Input is not UTF-8 text: {path}. Extract it first, record the extraction method, "
            f"and provide the result via text_path. Error: {exc}")


def source_ref(s: dict, id: str, data: bytes, blob_path: str, raw_hash: str | None, raw_path: str | None) -> dict:
    keep = ["key", "title", "source_uri", "source_id", "source_type", "revision_id",
            "modified_time", "claimed_status", "claimed_authority", "capture_method",
            "extraction_limitations", "jurisdiction", "notes"]
    record = {k: s[k] for k in keep if k in s}
    record.update({
        "packet_source_id": id,
        "source_record_type": "separate_source_occurrence",
        "content_sha256": sha(data),
        "text_bytes": len(data),
        "text_blob": blob_path,
        "raw_sha256": raw_hash,
        "raw_blob": raw_path,
        "content_hash_scope": "staged_utf8_export_not_necessarily_native_document_bytes",
        "claimed_status_is_authority": False,
    })
    return record


def main() -> None:
    p = argparse.ArgumentParser(description="Build a non-interpretive MIT-style source ledger")
    p.add_argument("--sources", required=True, type=Path, help="JSON source manifest")
    p.add_argument("--operators", type=Path, help="Optional operator message/quote JSON")
    p.add_argument("--input-root", type=Path, help="Root for input paths; defaults to manifest directory")
    p.add_argument("--output", required=True, type=Path, help="New output directory")
    args = p.parse_args()

    spec = read_json(args.sources)
    if not isinstance(spec, dict) or not isinstance(spec.get("sources"), list):
        die("Source JSON must be an object with an array named sources")
    project = spec.get("project")
    if not isinstance(project, str) or not project.strip():
        die("Source manifest requires a nonblank project name")
    root = (args.input_root or args.sources.parent).resolve()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        die(f"Output directory not empty; use a new path (will not overwrite): {output}")
    if not output.exists():
        output.mkdir(parents=True)
    text_dir = output / "text_blobs"
    raw_dir = output / "raw_blobs"
    text_dir.mkdir(exist_ok=True)
    sources: list[dict] = []
    lines: list[dict] = []
    source_inputs: dict[str, str] = {}
    source_ids: dict[str, str] = {}
    text_hashes: set[str] = set()
    raw_hashes: set[str] = set()
    keys: set[str] = set()
    segmentation_count = 0

    for n, item in enumerate(spec["sources"], start=1):
        if not isinstance(item, dict):
            die(f"sources[{n-1}] must be an object")
        key = item.get("key")
        if not isinstance(key, str) or not key.strip() or key in keys:
            die(f"Each source must have a unique, nonblank key; invalid: {key!r}")
        keys.add(key)
        input_path = resolve_input(root, item.get("text_path"))
        data, text = read_text_strict(input_path)
        s_id = f"SRC-{n:05d}"
        source_ids[key] = s_id
        source_inputs[key] = text
        digest = sha(data)
        text_blob = f"text_blobs/{digest}.txt"
        if digest not in text_hashes:
            (output / text_blob).write_bytes(data)
            text_hashes.add(digest)

        original_hash: str | None = None
        raw_blob: str | None = None
        if item.get("raw_path"):
            native_bytes = resolve_input(root, item["raw_path"]).read_bytes()
            original_hash = sha(native_bytes)
            raw_blob = f"raw_blobs/{original_hash}.bin"
            if original_hash not in raw_hashes:
                raw_dir.mkdir(exist_ok=True)
                (output / raw_blob).write_bytes(native_bytes)
                raw_hashes.add(original_hash)

        rec = source_ref(item, s_id, data, text_blob, original_hash, raw_blob)
        sources.append(rec)

        byte_cursor = 0
        for line_index, line in enumerate(text.splitlines(keepends=True), start=1):
            encoded = line.encode("utf-8")
            row = {
                "segment_id": f"SEG-{n:05d}-{line_index:07d}",
                "source_id": s_id,
                "source_key": key,
                "line_number": line_index,
                "byte_start": byte_cursor,
                "byte_end": byte_cursor + len(encoded),
                "verbatim_line": line,
                "source_text_sha256": digest,
            }
            lines.append(row)
            byte_cursor += len(encoded)
            segmentation_count += 1
        if byte_cursor != len(data):
            die(f"UTF-8 reconstruction failure: {key}")

    if not sources:
        die("Source list is empty; no packet created")

    turns: list[dict] = []
    quotes: list[dict] = []
    by_turn: dict[str, str] = {}
    if args.operators:
        operators = read_json(args.operators)
        if isinstance(operators, list):
            operators = {"turns": operators}
        if not isinstance(operators, dict) or not isinstance(operators.get("turns", []), list):
            die("operators must be an array or object with turns array")
        for n, turn in enumerate(operators.get("turns", []), start=1):
            if not isinstance(turn, dict) or not isinstance(turn.get("text"), str):
                die(f"Invalid operator turn at {n}")
            key = turn.get("key") or f"TURN-{n:04d}"
            if key in by_turn:
                die(f"Duplicate operator key: {key}")
            by_turn[key] = turn["text"]
            turns.append({
                "turn_id": f"TURN-{n:05d}", "provided_key": key,
                "origin": turn.get("origin", "speaker_unspecified"),
                "timestamp": turn.get("timestamp"),
                "verbatim_text": turn["text"],
                "source_identity_note": "origin supplied, not independently authenticated",
            })
        for n, quote in enumerate(operators.get("exact_quotes", []), start=1):
            if not isinstance(quote, dict) or not isinstance(quote.get("quote"), str):
                die(f"Invalid exact quote at {n}")
            key = quote.get("turn_key")
            if key not in by_turn:
                die(f"Exact quote references unknown turn: {key}")
            string = quote["quote"]
            if not string or string not in by_turn[key]:
                die(f"Exact quote does not occur verbatim in turn: {key}")
            offsets = []
            cursor = 0
            while (index := by_turn[key].find(string, cursor)) != -1:
                offsets.append(index)
                cursor = index + len(string)
            quotes.append({
                "quote_id": f"Q-{n:05d}", "turn_key": key,
                "verbatim_quote": string, "codepoint_starts": offsets,
                "index_type": "verbatim_substring_no_semantic_adjudication",
            })

    lexical: list[dict] = []
    lexicon = spec.get("lexicon", [])
    if not isinstance(lexicon, list) or any(not isinstance(w, str) or not w for w in lexicon):
        die("lexicon must be an array of nonempty strings")
    lexicon = list(dict.fromkeys(lexicon))
    for row in lines:
        lower = row["verbatim_line"].casefold()
        for surface in lexicon:
            count = lower.count(surface.casefold())
            if count:
                lexical.append({
                    "surface_form": surface, "source_id": row["source_id"],
                    "segment_id": row["segment_id"], "count": count,
                    "index_type": "lexical_only_no_identity_claim",
                })

    asserted: list[dict] = []
    pending: list[dict] = []
    for n, relation in enumerate(spec.get("relationships", []), start=1):
        if not isinstance(relation, dict):
            die(f"Invalid relationship item {n}")
        relation = dict(relation)
        relation["relationship_record_id"] = f"REL-{n:05d}"
        relation["status_note"] = "source_or_operator_assertion_not_independently_verified"
        valid = (isinstance(relation.get("relation_type"), str) and
                 isinstance(relation.get("endpoints"), list) and len(relation["endpoints"]) >= 2 and
                 isinstance(relation.get("support"), list) and bool(relation["support"]))
        for endpoint in relation.get("endpoints", []):
            if not isinstance(endpoint, dict):
                valid = False
                continue
            if "source_key" in endpoint and endpoint["source_key"] not in source_ids:
                die(f"Relationship {n} references unknown source key {endpoint['source_key']}")
            if not endpoint.get("source_key") and not endpoint.get("external_id"):
                valid = False
        for support in relation.get("support", []):
            if not isinstance(support, dict):
                valid = False
                continue
            if "source_key" in support:
                key = support["source_key"]
                if key not in source_inputs:
                    die(f"Relationship {n} support unknown source key: {key}")
                if "verbatim_quote" in support:
                    text = support["verbatim_quote"]
                    if not isinstance(text, str) or not text or text not in source_inputs[key]:
                        die(f"Relationship {n} unsupported verbatim_quote for {key}")
                    support["verified_substring_codepoint_start"] = source_inputs[key].index(text)
            if "turn_key" in support:
                turn_key = support["turn_key"]
                if turn_key not in by_turn:
                    die(f"Relationship {n} references unknown turn key: {turn_key}")
                if "verbatim_quote" in support:
                    statement = support["verbatim_quote"]
                    if not isinstance(statement, str) or not statement or statement not in by_turn[turn_key]:
                        die(f"Relationship {n} unsupported operator quotation for {turn_key}")
                    support["verified_substring_codepoint_start"] = by_turn[turn_key].index(statement)
            if "turn_key" not in support and "source_key" not in support and "external_locator" not in support:
                valid = False
        if valid:
            relation["classification"] = "explicitly_supplied_relationship_claim"
            asserted.append(relation)
        else:
            relation["classification"] = "OPEN"
            relation["open_reason"] = "missing_relation_type_endpoints_or_evidence"
            pending.append(relation)

    output_jsonl(output / "sources.jsonl", sources)
    output_jsonl(output / "verbatim_lines.jsonl", lines)
    output_jsonl(output / "operator_turns.jsonl", turns)
    output_jsonl(output / "operator_exact_quotes.jsonl", quotes)
    output_jsonl(output / "lexical_occurrences.jsonl", lexical)
    output_jsonl(output / "relationships_asserted.jsonl", asserted)
    output_jsonl(output / "relationships_pending.jsonl", pending)

    counts = {
        "source_entries": len(sources), "unique_text_blobs": len(text_hashes),
        "unique_raw_blobs": len(raw_hashes), "verbatim_line_segments": len(lines),
        "operator_turns": len(turns), "exact_quote_pointers": len(quotes),
        "lexical_occurrences": len(lexical), "asserted_relation_records": len(asserted),
        "open_relation_records": len(pending),
    }
    manifest = {
        "schema_version": SCHEMA_VERSION, "project": project,
        "scope": spec.get("scope", "Not separately specified"),
        "exclusions": spec.get("excluded_sources", []),
        "notes": spec.get("notes", ""),
        "purpose": "Non-interpretive source custody and transport; not canonical semantic graph",
        "read_only_source_intent": True,
        "identifiers": "All packet-generated SRC/SEG/TURN/REL IDs are transport-local and not minted MIT/HANID/SSRL/MERCS IDs",
        "extraction_warning": "Text extraction is only as complete as staged source exports; not guaranteed native-content preservation",
        "counts": counts,
        "files": ["sources.jsonl", "verbatim_lines.jsonl", "operator_turns.jsonl",
                  "operator_exact_quotes.jsonl", "lexical_occurrences.jsonl",
                  "relationships_asserted.jsonl", "relationships_pending.jsonl",
                  "receipt.json", "text_blobs/", "raw_blobs/"],
    }
    output_json(output / "manifest.json", manifest)
    receipt = {"schema_version": SCHEMA_VERSION, "source_text_sha256": {s["packet_source_id"]: s["content_sha256"] for s in sources},
               "counts": counts, "build_status": "written_unverified", "warnings": []}
    for s in sources:
        if s.get("extraction_limitations"):
            receipt["warnings"].append({"source_id": s["packet_source_id"], "limitation": s["extraction_limitations"]})
        if s.get("text_bytes") == 0:
            receipt["warnings"].append({"source_id": s["packet_source_id"], "limitation": "empty_text"})
    output_json(output / "receipt.json", receipt)

    readme = f"""# MIT Source Ledger — handoff packet\n\n**Project:** {project}\n\n**Scope:** {manifest['scope']}\n\n## Custody, not interpretation\n\nThis packet preserves supplied source data, exact utterances, and mechanical indices for a separate interpreter (such as Astra). No source-status, alleged operator ruling, title, or lexical similarity is independently verified by this packet. No HANID/SSRL/MERCS identifier is minted.\n\nRead `manifest.json` and `operator_turns.jsonl` first, then `sources.jsonl`. Recover exact statements from `verbatim_lines.jsonl` and `text_blobs/`. Compare versions and contradictions only after reading source context. `relationships_asserted.jsonl` contains **attributed claims**, not settled facts; `relationships_pending.jsonl` contains incomplete relationship records.\n\n## Reconstruction\n\nConcatenate `verbatim_line` by source and line number, UTF-8 encode, check against `sources.jsonl:content_sha256`; or use `scripts/verify_ledger.py` from the reusable skill.\n\n## Counts\n\n""" + "\n".join(f"- {k}: {v}" for k, v in counts.items()) + "\n\n## Known exclusions\n\n" + json.dumps(manifest['exclusions'], ensure_ascii=False, indent=2) + "\n\n## Boundaries\n\nOnly staged sources are covered; extracted text may omit graphics/equations/tables. Blob hashes apply to staged bytes, not necessarily original native objects. No connected source is modified by the offline builder.\n"
    (output / "README_HANDOFF.md").write_text(readme, encoding="utf-8")

    # Inline integrity validation before packaging. Independent verifier should also be run.
    grouped: dict[str, list[dict]] = {}
    for row in lines:
        grouped.setdefault(row["source_id"], []).append(row)
    for source in sources:
        reconstructed = "".join(x["verbatim_line"] for x in grouped.get(source["packet_source_id"], [])).encode("utf-8")
        if sha(reconstructed) != source["content_sha256"]:
            die(f"Reconstructed hash mismatch: {source['packet_source_id']}")
        if (output / source["text_blob"]).read_bytes() != reconstructed:
            die(f"Text blob differs from source: {source['packet_source_id']}")
    receipt["build_status"] = "validated_during_build_run_independent_verifier_recommended"
    output_json(output / "receipt.json", receipt)

    archive = output.with_suffix(".zip")
    if archive.exists():
        die(f"Archive already exists; will not overwrite: {archive}")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                z.write(path, path.relative_to(output))
    print(json.dumps({"output_directory": str(output), "zip_path": str(archive), "counts": counts}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
