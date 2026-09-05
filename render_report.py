"""Generate a self-contained operator report. All imported values stay text."""
import json
from pathlib import Path

report = json.loads(Path("report.json").read_text(encoding="utf-8"))
template = Path("report.template.html").read_text(encoding="utf-8")
# A review can contain a literal closing script tag. Escape before embedding.
payload = json.dumps(report, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
Path("index.html").write_text(template.replace("__AUDIT_JSON__", payload), encoding="utf-8")
