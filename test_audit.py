import copy
import math
import unittest
from datetime import date

from audit import audit
from make_demo import fixture

TODAY = date(2026, 9, 5)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.bundle = fixture()

    def single(self, **changes):
        self.bundle["reviews"] = [dict(self.bundle["reviews"][0], **changes)]
        return audit(self.bundle, TODAY)

    def test_complete_fixture_accounting(self):
        result = audit(self.bundle, TODAY)
        self.assertEqual(result["counts"], {"input_rows": 16, "retained_reviews": 8, "retry_rows_collapsed": 1, "quarantined_rows": 7, "candidate_groups": 1})

    def test_input_rows_never_disappear(self):
        c = audit(self.bundle, TODAY)["counts"]
        self.assertEqual(c["input_rows"], c["retained_reviews"] + c["retry_rows_collapsed"] + c["quarantined_rows"])

    def test_retry_preserves_both_original_records(self):
        result = audit(self.bundle, TODAY)
        row = next(r for r in result["reviews"] if r["source_review_id"] == "a101")
        self.assertEqual(row["record_ids"], ["r01", "r02"])
        self.assertEqual(len(row["raw_records"]), 2)

    def test_branches_never_merge_on_identical_text(self):
        result = audit(self.bundle, TODAY)
        busan = next(r for r in result["reviews"] if r["clinic_id"] == "spring-busan")
        self.assertNotIn(busan["id"], result["duplicate_candidates"][0]["review_ids"])

    def test_ambiguous_alias_is_quarantined(self):
        result = self.single(source_clinic_id="")
        self.assertEqual(result["quarantine"][0]["reasons"], ["ambiguous_clinic"])
        self.assertEqual(len(result["quarantine"][0]["clinic_candidates"]), 2)

    def test_unknown_external_id_does_not_fall_back_to_name(self):
        result = self.single(source_clinic_id="unknown", clinic_name="Spring Gangnam")
        self.assertEqual(result["quarantine"][0]["reasons"], ["unknown_source_clinic_id"])

    def test_unicode_alias_normalization(self):
        result = self.single(source_clinic_id="", clinic_name="  Ｍｏｏｎ  Ｓｅｏｕｌ  ")
        self.assertEqual(result["reviews"][0]["clinic_id"], "moon-seoul")

    def test_same_translation_is_not_identity(self):
        result = audit(self.bundle, TODAY)
        translated_collision = next(r for r in result["reviews"] if r["source_review_id"] == "a104")
        self.assertFalse(any(translated_collision["id"] in group["review_ids"] for group in result["duplicate_candidates"]))

    def test_short_generic_praise_remains_two_reviews(self):
        result = audit(self.bundle, TODAY)
        ids = {r["id"] for r in result["reviews"] if r["original_text"] == "좋아요"}
        self.assertEqual(len(ids), 2)
        self.assertFalse(any(ids.intersection(g["review_ids"]) for g in result["duplicate_candidates"]))

    def test_source_id_conflict_quarantines_all_versions(self):
        result = audit(self.bundle, TODAY)
        conflicts = [r for r in result["quarantine"] if r["reasons"] == ["source_id_conflict"]]
        self.assertEqual({r["record_id"] for r in conflicts}, {"r08", "r09"})

    def test_no_input_verified_flag_promotes_procedure(self):
        result = self.single(verified=True, verification="verified_procedure")
        self.assertEqual(result["reviews"][0]["procedure_verification"], "not_verified")
        self.assertEqual(result["reviews"][0]["publication_status"], "needs_editorial_review")

    def test_source_url_allowlist(self):
        for url in ["javascript:alert(1)", "http://reviews.example/a", "https://reviews.example.evil.test/a", "https://reviews.example@evil.test/a", "https://evil.test@reviews.example/a", "https://reviews.example:8443/a", "https://[invalid/a"]:
            with self.subTest(url=url):
                result = self.single(source_url=url)
                self.assertEqual(result["counts"]["retained_reviews"], 0)

    def test_invalid_ratings(self):
        for rating in [-1, 6, True, "4", None, math.nan, math.inf]:
            with self.subTest(rating=rating):
                self.assertEqual(self.single(rating=rating)["counts"]["retained_reviews"], 0)

    def test_invalid_dates_and_future(self):
        for published_at in ["2026-02-30", "tomorrow", "2026-09-06", "20260901", "2026-9-1"]:
            with self.subTest(date=published_at):
                self.assertEqual(self.single(published_at=published_at)["counts"]["retained_reviews"], 0)

    def test_missing_source_id_is_not_guessed_from_content(self):
        self.assertEqual(self.single(source_review_id="")["counts"]["retained_reviews"], 0)

    def test_transport_ids_cannot_be_reused(self):
        self.bundle["reviews"][1]["record_id"] = "r01"
        result = audit(self.bundle, TODAY)
        self.assertEqual(len([q for q in result["quarantine"] if "duplicate_transport_record_id" in q["reasons"]]), 2)

    def test_malformed_row_does_not_crash_other_rows(self):
        self.bundle["reviews"] += [None, "not a row", {"record_id": {"invalid": True}}]
        result = audit(self.bundle, TODAY)
        self.assertEqual(result["counts"]["retained_reviews"], 8)
        self.assertEqual(result["counts"]["quarantined_rows"], 10)

    def test_source_namespace_prevents_id_collision(self):
        self.bundle["reviews"] = self.bundle["reviews"][:1]
        row = copy.deepcopy(self.bundle["reviews"][0])
        row.update(record_id="another", source="community", source_clinic_id="spring-seoul", source_url="https://community.example/a101")
        self.bundle["reviews"].append(row)
        self.assertEqual(audit(self.bundle, TODAY)["counts"]["retained_reviews"], 2)

    def test_duplicate_registry_ids_fail_loudly(self):
        self.bundle["clinics"].append(copy.deepcopy(self.bundle["clinics"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate canonical"):
            audit(self.bundle, TODAY)

    def test_conflicting_branch_external_ids_fail_loudly(self):
        self.bundle["clinics"][1]["source_ids"]["review-board"] = ["spring-gn"]
        with self.assertRaisesRegex(ValueError, "multiple branches"):
            audit(self.bundle, TODAY)

    def test_stable_ids_independent_of_input_order(self):
        before = audit(self.bundle, TODAY)
        self.bundle["reviews"].reverse()
        after = audit(self.bundle, TODAY)
        self.assertEqual([r["id"] for r in before["reviews"]], [r["id"] for r in after["reviews"]])
        self.assertEqual(before["counts"], after["counts"])


if __name__ == "__main__":
    unittest.main()
