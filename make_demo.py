"""Create fictional fixtures; does not download or synthesize patient records."""
import copy
import json
from pathlib import Path


def fixture():
    original = "상담 전에 질문 목록을 준비했습니다. 직원이 비용과 다음 방문 일정을 설명했고, 상담 후 안내문을 받았습니다."
    base = dict(record_id="r01", source="review-board", source_review_id="a101", source_clinic_id="spring-gn",
                clinic_name="봄 클리닉", source_url="https://reviews.example/reviews/a101", language="ko",
                original_text=original, translation_en="I prepared questions before the consultation. Staff explained the cost and next appointment, and gave me written instructions.",
                published_at="2026-09-01", rating=4.0, fetched_at="2026-09-05T06:00:00Z")
    def row(record_id, **changes):
        return dict(copy.deepcopy(base), record_id=record_id, **changes)
    return {
        "synthetic_demo": True,
        "sources": {"review-board": {"hosts": ["reviews.example"]}, "community": {"hosts": ["community.example"]}},
        "clinics": [
            {"id": "spring-gangnam", "name": "Spring Clinic · Gangnam (fictional)", "aliases": ["봄 클리닉", "봄클리닉 강남", "Spring Gangnam"], "source_ids": {"review-board": ["spring-gn"], "community": ["spring-seoul"]}},
            {"id": "spring-busan", "name": "Spring Clinic · Busan (fictional)", "aliases": ["봄 클리닉", "봄클리닉 부산", "Spring Busan"], "source_ids": {"review-board": ["spring-bs"]}},
            {"id": "moon-seoul", "name": "Moon Clinic · Seoul (fictional)", "aliases": ["달 클리닉", "Moon Seoul"], "source_ids": {"review-board": ["moon-sl"]}},
        ],
        "reviews": [
            base,
            row("r02", fetched_at="2026-09-05T06:01:00Z"),
            row("r03", source="community", source_review_id="c909", source_clinic_id="spring-seoul", source_url="https://community.example/posts/c909"),
            row("r04", source_review_id="b101", source_clinic_id="spring-bs", source_url="https://reviews.example/reviews/b101"),
            row("r05", source_review_id="a102", source_clinic_id="", source_url="https://reviews.example/reviews/a102"),
            row("r06", source_review_id="m201", source_clinic_id="moon-sl", clinic_name="달 클리닉", source_url="https://reviews.example/reviews/m201", original_text="좋아요", translation_en="Good."),
            row("r07", source_review_id="m202", source_clinic_id="moon-sl", clinic_name="달 클리닉", source_url="https://reviews.example/reviews/m202", original_text="좋아요", translation_en="Good."),
            row("r08", source_review_id="m203", source_clinic_id="moon-sl", clinic_name="달 클리닉", source_url="https://reviews.example/reviews/m203"),
            row("r09", source_review_id="m203", source_clinic_id="moon-sl", clinic_name="달 클리닉", source_url="https://reviews.example/reviews/m203", rating=2.0),
            row("r10", source_review_id="a103", source_url="javascript:alert('untrusted')"),
            row("r11", source_review_id="a104", source_url="https://reviews.example/reviews/a104", original_text="버스로 방문했습니다. 예약 시간을 바꾸고 싶었는데 전화로 변경할 수 있었고, 다음 주에 다시 방문하기로 했습니다."),
            row("r12", source_review_id=""),
            row("r13", source_review_id="m204", source_clinic_id="moon-sl", clinic_name="달 클리닉", source_url="https://reviews.example/reviews/m204", language="en", original_text="<script>alert('untrusted review')</script> This is a rendering safety fixture, not a real patient statement.", translation_en=""),
            row("r14", source_review_id="a105", source_url="https://reviews.example/reviews/a105", published_at="2026-02-30"),
            row("r15", source_review_id="a106", source_url="https://reviews.example/reviews/a106", source_clinic_id="not-in-registry", clinic_name="Spring Gangnam"),
            row("r16", source_review_id="m205", source_url="https://reviews.example/reviews/m205", source_clinic_id="", clinic_name=" Ｍｏｏｎ   Ｓｅｏｕｌ ", original_text="예약 안내문을 읽었습니다.", translation_en=""),
        ],
    }


if __name__ == "__main__":
    Path("fixtures.json").write_text(json.dumps(fixture(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
