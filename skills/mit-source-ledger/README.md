# MIT Source Ledger — TwinGlass skill

**Role:** cross-project evidence custody and portable handoff, not a new epistemic authority, MIT runtime implementation, HANID minter, MERCS compactor, or automatic semantic interpretation engine.

This skill has been moved from the *unmerged* Metadata Imperial Token draft proposal to TwinGlass, where reusable agent skills are maintained. The MIT repository continues to own its runtime and `MITLedger` contract; SSRL remains responsible for source/evidence history. The skill uses fictional fixtures, contains no private corpus, and never mutates source repositories or Drive documents by default.

## Invocation

Use the TwinGlass plugin/skill named `mit-source-ledger` for a project-scoped custody packet, such as:

> Use mit-source-ledger on this project. Stage all in-scope files and my operator statements read-only; preserve their original source/version identities, exact text and SHA-256 provenance; produce a verified packet for Astra. Keep semantic questions OPEN unless explicitly asserted with evidence.

Run from the Twinglass repository root:

```bash
python3 skills/mit-source-ledger/scripts/build_ledger.py \
  --sources skills/mit-source-ledger/examples/sources.example.json \
  --operators skills/mit-source-ledger/examples/operators.example.json \
  --input-root skills/mit-source-ledger/examples \
  --output /tmp/example-ledger

python3 skills/mit-source-ledger/scripts/verify_ledger.py /tmp/example-ledger
python3 -m unittest discover -s skills/mit-source-ledger/tests -v
```

The Python scripts use only local, already-staged files and the standard library. Source acquisition requires separately authorized connectors or host filesystem access; simply installing the skill does not grant those permissions.

## Avoid duplicate registration

TwinGlass has a **single-source skill loading** policy. The host installation report for November 10, 2026 shows `mit-source-ledger` already installed separately in Antigravity, Grok, shared `~/.agents/skills`, and Claude, with Codex/Cursor/Copilot discovery paths.

**Do not enable two copies in one harness.** Choose the standalone installation **or** this TwinGlass-bundled skill for each harness. Verify native skill discovery after the switch. Do not remove unrelated skills, safety gates or isolated workers. The ChatGPT personal plugin can remain a separate distribution and does not automatically sync with this repository.

See [SKILL.md](SKILL.md) for custody rules and [packet-format.md](references/packet-format.md) for packet structure.
