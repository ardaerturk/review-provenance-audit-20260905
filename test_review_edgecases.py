"""Independent regression cases for malformed inputs at trust boundaries."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from datetime import date

from audit import audit
from make_demo import fixture


class ReviewEdgeCases(unittest.TestCase):
    def test_malformed_transport_id_on_identical_retry_is_not_accepted(self):
        missing = object()
        for value in (missing, None, {}, [], ""):
            with self.subTest(record_id=value):
                bundle = fixture()
                valid = copy.deepcopy(bundle["reviews"][0])
                retry = copy.deepcopy(valid)
                if value is missing:
                    retry.pop("record_id")
                else:
                    retry["record_id"] = value
                bundle["reviews"] = [valid, retry]
                result = audit(bundle, date(2026, 9, 5))
                self.assertGreaterEqual(result["counts"]["quarantined_rows"], 1)
                for retained in result["reviews"]:
                    self.assertTrue(all(isinstance(rid, str) and rid.strip()
                                        for rid in retained["record_ids"]))
                counts = result["counts"]
                self.assertEqual(2, counts["retained_reviews"]
                                 + counts["retry_rows_collapsed"]
                                 + counts["quarantined_rows"])

    def test_string_host_allowlist_fails_closed(self):
        bundle = fixture()
        row = copy.deepcopy(bundle["reviews"][0])
        bundle["reviews"] = [row]
        bundle["sources"][row["source"]]["hosts"] = "reviews.example"
        row["source_url"] = "https://example/a101"
        with self.assertRaises(ValueError):
            audit(bundle, date(2026, 9, 5))

    def test_cli_non_finite_json_does_not_emit_unhandled_traceback(self):
        bundle = fixture()
        bundle["reviews"] = [copy.deepcopy(bundle["reviews"][0])]
        bundle["reviews"][0]["rating"] = float("nan")
        with tempfile.TemporaryDirectory() as temp:
            input_path = Path(temp) / "malformed.json"
            output_path = Path(temp) / "report.json"
            input_path.write_text(json.dumps(bundle), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("audit.py")),
                 str(input_path), "--as-of", "2026-09-05", "--output", str(output_path)],
                capture_output=True, text=True, timeout=10)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertIn(proc.returncode, (0, 2))
            if proc.returncode == 0:
                def reject_constant(value):
                    raise AssertionError("Output contains non-standard JSON constant: " + value)
                report = json.loads(output_path.read_text(encoding="utf-8"),
                                    parse_constant=reject_constant)
                self.assertEqual(report["counts"]["retained_reviews"], 0)
            else:
                self.assertIn("Invalid input", proc.stderr)


if __name__ == "__main__":
    unittest.main()
