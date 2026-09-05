# Review provenance audit

A small, working ingestion audit and self-contained operator report. All fixtures are fictional; this repository contains no patient data, credentials, confidential questions, or third-party review exports.

[Open the interactive report](https://ardaerturk.github.io/review-provenance-audit-20260905/)

```sh
python3 -m unittest -v
python3 make_demo.py
python3 audit.py fixtures.json --as-of 2026-09-05 --output report.json
python3 render_report.py
python3 -m http.server 8080
```

Open `http://localhost:8080`. Python 3.10+; no packages, API keys, paid services or build tool required. `index.html` also opens directly from disk.

## What it does

- Resolves curated source clinic IDs and exact normalized aliases to a specific clinic branch. Ambiguous names and unknown source IDs go to quarantine.
- Collapses an identical retry only when both the source namespace and source review ID match. It preserves every original input record. A changed record under the same source ID quarantines **all** versions rather than letting the last write win.
- Flags sufficiently long, identical original text with the same clinic, language and date for manual inspection. It never merges those candidates, matching translations, or generic short praise.
- Keeps original language, original text, draft translation, date and source URL visible. Source provenance never establishes patient or procedure verification.
- Validates dates, ratings, required fields and approved HTTPS source hosts. Imported text renders through `textContent`, and the embedded JSON escapes closing script tags.

The sample accounts for **16 input rows = 8 retained reviews + 1 collapsed retry + 7 quarantined rows**. One duplicate candidate group remains unmerged. “Retained” means structurally suitable for editorial review, not approved for publication.

Validation: **24 automated tests pass**. The report was exercised in Chrome: candidate filtering retains both source records, quarantine gives reasons, retries preserve both inputs, and imported HTML is shown as text. CI repeats tests and checks regeneration against the committed artifacts.

## Deliberate scope

This is a local batch prototype, not a scraper, translation service, medical recommendation engine or production patient database. The English text is an illustrative draft, not a live model response. Synthetic URLs use reserved `.example` domains and will not resolve.

The prototype uses a curated registry instead of guessing identity with an LLM. The regex/date/URL checks are input quality checks, not permission to collect or republish a review. A real adapter would need authorized access, stable source IDs, retrieval timestamps, consent/licensing rules, deletion handling and a retention policy.

Next steps would be an editor-reviewed alias registry, a persistent unique constraint on `(source, source_review_id)`, append-only revision history, translation quality checks on time/negation/uncertainty, and precision evaluation on a labeled, lawfully obtained duplicate set. Embeddings would propose candidates only; editorial decisions would control merges and clinical verification.

## Ownership

Copyright © 2026 The Flywheel Corporation. Published as an evaluation deliverable. No reuse license is granted.
