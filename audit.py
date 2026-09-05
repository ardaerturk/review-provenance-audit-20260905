"""Deterministic review-ingestion audit. Python 3.10+, standard library only."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit


def normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def stable_key(row: dict) -> tuple | None:
    values = row.get("source"), row.get("source_review_id")
    return values if all(isinstance(v, str) and v.strip() for v in values) else None


def content_version(row: dict) -> str:
    # Arrival time and transport ID can change on retry. Source/translation
    # changes must remain visible instead of silently selecting the last value.
    payload = {k: v for k, v in row.items() if k not in {"record_id", "fetched_at"}}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate(row: dict, sources: dict, as_of: date) -> list[str]:
    problems = []
    for field in ("record_id", "source", "source_review_id", "source_url", "clinic_name", "language", "original_text", "published_at"):
        if not isinstance(row.get(field), str) or not row[field].strip():
            problems.append("missing_or_invalid_" + field)
    if problems:
        return problems
    if row["source"] not in sources:
        problems.append("unknown_source")
    try:
        url = urlsplit(row["source_url"])
        allowed = sources.get(row["source"], {}).get("hosts", [])
        if url.scheme != "https" or url.hostname not in allowed or url.username or url.password or url.port not in (None, 443):
            problems.append("unapproved_source_url")
    except ValueError:
        problems.append("unapproved_source_url")
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["published_at"]):
            raise ValueError("date format")
        if date.fromisoformat(row["published_at"]) > as_of:
            problems.append("future_publication_date")
    except ValueError:
        problems.append("invalid_publication_date")
    rating = row.get("rating")
    if type(rating) not in (int, float) or not 0 <= rating <= 5:
        problems.append("invalid_rating")
    if not re.fullmatch(r"[a-z]{2}(?:-[A-Z]{2})?", row["language"]):
        problems.append("invalid_language")
    for field in ("translation_en", "source_clinic_id"):
        if field in row and not isinstance(row[field], str):
            problems.append("invalid_" + field)
    return problems


def audit(bundle: dict, as_of: date) -> dict:
    if not isinstance(bundle, dict) or not isinstance(bundle.get("reviews"), list):
        raise ValueError("Input must contain a reviews array")
    clinics, sources = bundle.get("clinics", []), bundle.get("sources", {})
    if not isinstance(clinics, list) or not isinstance(sources, dict):
        raise ValueError("clinics must be an array and sources must be an object")
    def strings(values):
        return isinstance(values, list) and all(isinstance(v, str) and v.strip() for v in values)
    for source, config in sources.items():
        if not isinstance(source, str) or not source.strip() or not isinstance(config, dict):
            raise ValueError("Invalid source registry entry")
        hosts = config.get("hosts")
        if not strings(hosts) or not hosts or not all(re.fullmatch(r"[a-z0-9.-]+", host) for host in hosts):
            raise ValueError("Source hosts must be a non-empty list of lowercase hostnames")
    aliases, external_ids, clinic_by_id = defaultdict(set), {}, {}
    for clinic in clinics:
        if not isinstance(clinic, dict) or any(not isinstance(clinic.get(k), str) or not clinic[k].strip() for k in ("id", "name")):
            raise ValueError("Clinic registry requires string id and name")
        if not strings(clinic.get("aliases", [])) or not isinstance(clinic.get("source_ids", {}), dict):
            raise ValueError("Invalid clinic aliases or source IDs")
        cid = clinic["id"]
        if cid in clinic_by_id:
            raise ValueError("Duplicate canonical clinic ID: " + cid)
        clinic_by_id[cid] = clinic
        for alias in [clinic["name"], *clinic.get("aliases", [])]:
            aliases[normalized(alias)].add(cid)
        for source, ids in clinic.get("source_ids", {}).items():
            if source not in sources or not strings(ids):
                raise ValueError("Clinic source IDs must be string arrays for known sources")
            for external_id in ids:
                key = source, external_id
                if key in external_ids and external_ids[key] != cid:
                    raise ValueError("Source clinic ID maps to multiple branches")
                external_ids[key] = cid

    groups, quarantine, accepted, retries = defaultdict(list), [], [], []
    seen_record_ids = defaultdict(int)
    for raw in bundle["reviews"]:
        if isinstance(raw, dict) and isinstance(raw.get("record_id"), str):
            seen_record_ids[raw["record_id"]] += 1
    for index, raw in enumerate(bundle["reviews"]):
        if not isinstance(raw, dict):
            quarantine.append({"record_id": f"row-{index + 1}", "reasons": ["record_is_not_object"], "raw": raw})
            continue
        key = stable_key(raw)
        groups[key if key is not None else ("invalid-row", index)].append(raw)

    def reject(row: dict, reasons: list[str], candidates=None):
        quarantine.append({"record_id": row.get("record_id", "unknown"), "reasons": reasons, "clinic_candidates": candidates or [], "raw": row})

    for key in sorted(groups, key=str):
        rows = groups[key]
        if len({content_version(row) for row in rows}) > 1:
            for row in rows:
                reject(row, ["source_id_conflict"])
            continue
        issues = sorted({issue for row in rows for issue in validate(row, sources, as_of)})
        if any(isinstance(row.get("record_id"), str) and seen_record_ids.get(row["record_id"], 0) > 1 for row in rows):
            issues.append("duplicate_transport_record_id")
        if issues:
            for row in rows:
                reject(row, issues)
            continue
        row = rows[0]
        source_clinic_id = row.get("source_clinic_id")
        if source_clinic_id:
            cid = external_ids.get((row["source"], source_clinic_id))
            candidates = {cid} if cid else set()
            method = "source_clinic_id"
            if not candidates:
                for item in rows:
                    reject(item, ["unknown_source_clinic_id"])
                continue
        else:
            candidates = aliases.get(normalized(row["clinic_name"]), set())
            method = "exact_curated_alias"
        if len(candidates) != 1:
            reason = "ambiguous_clinic" if candidates else "unknown_clinic"
            for item in rows:
                reject(item, [reason], sorted(candidates))
            continue
        cid = next(iter(candidates))
        uid = hashlib.sha256(json.dumps(key, ensure_ascii=False).encode()).hexdigest()[:16]
        accepted.append({
            "id": uid, "clinic_id": cid, "clinic_name": clinic_by_id[cid]["name"],
            "clinic_match_method": method,
            "record_ids": sorted(item["record_id"] for item in rows),
            "source": row["source"], "source_review_id": row["source_review_id"],
            "source_url": row["source_url"], "published_at": row["published_at"],
            "language": row["language"], "original_text": row["original_text"],
            "translation_en": row.get("translation_en", ""),
            "fixture_note": row.get("fixture_note", "") if bundle.get("synthetic_demo") is True else "",
            "translation_status": "draft_not_reviewed" if row.get("translation_en") else "not_provided",
            "rating": row["rating"], "procedure_verification": "not_verified",
            "publication_status": "needs_editorial_review",
            "raw_records": rows,
        })
        if len(rows) > 1:
            retries.append({"review_id": uid, "record_ids": sorted(item["record_id"] for item in rows), "collapsed_rows": len(rows) - 1, "reason": "identical_source_record_retry"})

    # Candidate detection never changes counts or deletes a review. In
    # particular, translations and short generic praise are not identities.
    fingerprints = defaultdict(list)
    for row in accepted:
        text = normalized(row["original_text"])
        if len(text.replace(" ", "")) >= 40:
            fingerprints[(row["clinic_id"], row["published_at"], row["language"], text)].append(row["id"])
    candidates = [{"review_ids": sorted(ids), "reason": "matching_original_text_clinic_and_date", "action": "review_manually_no_merge"}
                  for ids in fingerprints.values() if len(ids) > 1]
    accepted.sort(key=lambda row: row["id"])
    quarantine.sort(key=lambda row: str(row["record_id"]))
    candidates.sort(key=lambda group: group["review_ids"])
    retries.sort(key=lambda group: group["review_id"])
    return {
        "schema_version": 1, "as_of": as_of.isoformat(),
        "synthetic_demo": bundle.get("synthetic_demo") is True,
        "counts": {"input_rows": len(bundle["reviews"]), "retained_reviews": len(accepted),
                   "retry_rows_collapsed": sum(group["collapsed_rows"] for group in retries),
                   "quarantined_rows": len(quarantine), "candidate_groups": len(candidates)},
        "reviews": accepted, "retries": retries, "duplicate_candidates": candidates,
        "quarantine": quarantine,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, default=Path("report.json"))
    args = parser.parse_args()
    try:
        def reject_constant(value):
            raise ValueError("Non-standard JSON number: " + value)
        result = audit(json.loads(args.input.read_text(encoding="utf-8"), parse_constant=reject_constant), args.as_of)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(2, f"Invalid input: {error}\n")
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    main()
