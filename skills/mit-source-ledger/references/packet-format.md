# MIT Source Ledger v1 — packet schema and handoff

## Input manifest

JSON object containing `project`, `scope`, `sources`, optional `lexicon`, optional `relationships`, optional `excluded_sources`, and `notes`. Each source has a unique `key` and a local UTF-8 `text_path`, optionally `raw_path` for an independently retained binary native artifact. Other optional fields: `title`, `source_uri`, `source_id`, `source_type`, `modified_time`, `revision_id`, `claimed_status`, `claimed_authority`, `capture_method`, `extraction_limitations`, `notes`, `jurisdiction`. All these attributes are user/provider-supplied metadata, not independently established truth. Relative paths resolve under the `--input-root` directory (default: manifest's directory).

`operator-turns` JSON may be a list or `{"turns":[...]}`. Each turn needs `text`; optional `key`, `timestamp`, and `origin` (e.g., `direct_user_message`, `quoted_transcript`, `assistant_message`). Preserve speaker categories. `exact_quotes` entries need `turn_key` and a verbatim `quote` present in the corresponding turn; this file is not semantic extraction.

`relationships` is optional and is copied as **explicit, attributed assertions only**. Every item must have `relation_type`, nonempty `endpoints` (source keys or other exact supplied identifiers), and `support` (source/turn segment refs or exact provenance) or be stored as `OPEN` in `relationships_pending.jsonl`. Never infer a relationship from a lexical occurrence. Tool cannot mint HANIDs; original supplied IDs may be included as metadata but are not generated.

## Output files

- `manifest.json`: schema version, project, execution mode, counts, project scope, limitations, file map.
- `sources.jsonl`: one row per retrieved source; original IDs/URIs, exported-text SHA-256, raw SHA (when staged), blob paths, reported status/revision, extraction caveat.
- `text_blobs/<sha256>.txt`: source text bytes, content-addressed once even when multiple distinct source records have the same text.
- `raw_blobs/<sha256>.bin`: optional original bytes, copied unchanged; separate from extracted text.
- `verbatim_lines.jsonl`: line-numbered, byte-offset, reconstruction-safe source records, including line endings.
- `operator_turns.jsonl`: complete supplied utterances with role/source preserved.
- `operator_exact_quotes.jsonl`: validated exact substrings and offsets into turns.
- `lexical_occurrences.jsonl`: purely mechanical term-to-line hits.
- `relationships_asserted.jsonl`: explicitly provided relationship statements with source attribution, **not adjudicated truth**.
- `relationships_pending.jsonl`: unresolved/unasserted relationship items, possibly empty.
- `receipt.json`: validation counts, SHA records and missing/extraction warnings.
- `README_HANDOFF.md`: instructions for a second model or human.

## Reconstruction

For each source, concatenate `verbatim_line` fields for its `source_id` in ascending `line_number`, encode UTF-8 and compare to its `text_sha256`. `byte_start` and `byte_end` are 0-based, half-open byte offsets. The text blob digest does not authenticate a Google Doc's internal native structure, only the staged text export. A source can have an empty text export; in that case record the missing evidence condition explicitly.

## Why content hashes are not HANIDs

Content-addressed deduplication only proves two staged byte sequences are identical. Semantic identity, same referent, equivalent definition, same authority, and same scope require their own evidence and, when available, actual HANID/SSRL assignments. Distinct documents continue to have distinct source records even if they refer to the same blob. This is byte economy without epistemic collapse.

## Suggested handoff prompt

> Interpret the attached MIT Source Ledger, starting with the operator messages and source inventory. Recover complete source context before comparing claims. Preserve every disagreement and version difference. Do not assign canonical meaning, semantic identity, source authority, or HANIDs from term frequency or shared title. For each proposed relationship, cite its exact endpoints and source segments, specify scope and epistemic state, and retain original referential claims. Produce relationship-ledger candidates for review; never silently edit the source packet.

## CLI

```bash
python scripts/build_ledger.py \
  --sources examples/sources.example.json \
  --operators examples/operators.example.json \
  --input-root examples \
  --output /tmp/example-ledger
python scripts/verify_ledger.py /tmp/example-ledger
```

The builder emits `/tmp/example-ledger.zip`. The output is a **new** independent packet for each project; do not append unrelated projects into one namespace unless the user explicitly asks for cross-project integration.
