---
name: mit-source-ledger
description: "Use for cross-project source-custody ledgers, MIT-style evidence packets, and Astra handoffs. Ingest explicitly scoped documents, files, and operator utterances; preserve complete text, original source identity, versions, provenance and exact spans; deduplicate bytes without conflating meanings; leave semantic relationships unresolved unless explicitly sourced."
---

# MIT Source Ledger — reusable evidence-custody workflow

Use this skill whenever a user asks to **be a ledger rather than interpret**, to assemble disparate project documents for another model/agent (including Astra), to make a portable MIT-style handoff, or to index many project sources without inventing a final synthesis.

## Purpose and boundaries

This is a **source-custody and transport skill**, not a deployed Metadata Imperial Token (MIT), HANID minter, SSRL service, MERCS engine, or source-of-truth authority. Its package IDs (`SRC-...`, `SEG-...`, `TURN-...`) are **bundle-local surrogate IDs only**. Do not assert that a real semantic web, HANID, or compaction hub has been constructed by this script. Do not turn a mention of a relationship into a verified relationship without a supporting source and scope. Preserve the user's actual project terminology without translating it into a different ontology.

**Full contextual-web work is a downstream activity.** Custody stores all retrievable source context, avoids unnecessary duplicated text, and exposes the material needed for a later agent to establish relationship ledgers and generate contextually differentiated webs. A packet containing indices is not itself a verified relationship graph.

## Runbook

1. **Bound scope.** Start from the current project's files, explicit folders, URLs, repositories, or conversation turns. Specify what is included and what is *not* searched. Never indiscriminately search all connected accounts. If the source set is huge, enumerate known coverage and any omissions; do not claim completeness from a partial listing.
2. **Retrieve read-only.** Prefer the source's actual connected-app retrieval tool when supplied a connector URL; otherwise use Files for library/attachments and appropriate source tools. Do not edit documents/repositories to prepare the packet. Preserve native/raw bytes when possible; when using extracted/plain-text exports, describe what might be lost (equations, figures, tables, comments, embedded objects). A raw-export digest is *not* automatically the canonical native-document checksum.
3. **Stage an explicit project manifest.** Use `examples/sources.example.json` as the shape. Stage the retrieved UTF-8 text into local files; record original title, exact URI/ID, revision if available, modified time if reported, source type, source-claimed status, retrieval/export mode, and known gaps. For files with unreadable or unexported content, record the gap—do not guess contents. Avoid mixing assistant narratives into direct user utterances.
4. **Preserve version distinctions.** Keep every source as a separate `sources.jsonl` record even when two sources share a title or byte-identical content. Content-addressed blobs store identical exported bytes once; distinct document identities and source claims remain distinct. Do not choose a winner between P1–P5 / P1–P6 or between earlier proposal and later ruling. Claims of approval in a document are *claims*, not independently authenticated approval.
5. **Capture exact statements.** Preserve full operator utterances (when provided and authorized), plus optional exact-substring quote pointers. Exact quote validation must fail if the substring is not present. Quotes from source documents remain attributed to *those documents*, regardless of their claims about the operator.
6. **Generate mechanical indices.** Run the offline script under `scripts/build_ledger.py` (see `references/packet-format.md` and the example). It emits SHA-256 text blobs, exact line segmentation with byte offsets, optional lexical occurrences, source inventory, user turns, exact quotes, relation records (explicit-only), empty pending-relation file, receipt and ZIP. A lexical match is never a same-meaning decision.
7. **Verify** with `scripts/verify_ledger.py` before sharing. Verify byte reconstruction, blob hashes, quoted offsets, and source/segment pointers; report any failures and halt claims of success. Quote index, citations, and provenance must remain intact. For a huge corpus, batch inputs and preserve per-batch manifest/receipts rather than sampling silently.
8. **Handoff for interpretation.** Point the receiving agent to `README_HANDOFF.md`, `manifest.json`, `operator_turns.jsonl`, `sources.jsonl`, then `verbatim_lines.jsonl`/`blobs/`. State clearly what relations are `OPEN`, which are explicitly source-asserted, and what is only mechanical indexing. The receiving agent may do further semantic analysis, but **that is not part of custody mode**.

## Relationship mode (only when requested)

Relationship ledgers are **first-class records**. If the operator or a document explicitly provides a typed relation, store it as an attributed assertion with `relation_type`, endpoints/roles, applicable context/scope, source segment(s), claim origin, and validation status. Both originating object references may point to one relation record rather than duplicating its semantic content. Use evidence-bound relation records only; never infer semantic equivalence from lexical similarity, duplicates, filenames, hashes, graph proximity, or dates. Unsupported candidate links belong in `relationships_pending.jsonl` with reason `OPEN`, not in `relationships_asserted.jsonl`.

A single shared referential formulation can have multiple source/SSRL occurrences and eventually a common HANID **if an actual HANID service or authorized operator provides the identity**. Otherwise store `hanid: null` or omit it. Compaction remains conceptually distinct from deletion; never erase documentary occurrences or versioned statements to save space.

## Output contract

Deliver a downloadable ZIP and an independently readable handoff README. Report counted documents, source text blobs, verbatim segments, operator turns and lexical hits **from the generated manifest**, not guessed numbers. List source omissions and extraction limitations. Keep source links intact. Do not upload/save the ledger into shared cloud folders or modify the source project without explicit user direction. Do not automatically forward private source contents to another model/provider: hand off a file the user can choose to share.

## If script/container execution is unavailable

Still follow the custody discipline. Produce a structured, source-grounded manifest and exact statements using whatever file tools are available, label the packet as partial, and never claim SHA validation or ZIP creation that did not happen. Offer the skill package for local execution.

## Files

- `scripts/build_ledger.py` — standard-library offline packet constructor (no API keys).
- `scripts/verify_ledger.py` — checksum and pointer verifier.
- `references/packet-format.md` — file contract, boundaries, data examples.
- `examples/sources.example.json` and `examples/operators.example.json` — reusable inputs with fictional fixtures.
- `tests/test_ledger.py` — smoke and negative tests.
