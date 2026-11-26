"""내보내기: CSV · JSON · career-ops 파이프라인(`data/pipeline.md`의 `- [ ] url | 회사 | 직무 | ...` 형식)."""
import csv
import io
import json

FIELDS = ["score", "tier", "verdict", "source", "title", "company", "location", "career", "edu", "deadline", "url", "why"]


def why(r):
    parts = [("+" if h["pts"] >= 0 else "") + f"{h['pts']} {h['word']}({'제목' if h['where'] == 'title' else '상세'})"
             for h in r.get("hits", []) if h["where"] in ("title", "body") and h["pts"]]
    if r.get("v_note"):
        parts.append(r["v_note"])
    return "; ".join(parts)


def pick(items, min_score=0, include_hold=True):
    ok = ("ok", "hold", "pending") if include_hold else ("ok", "pending")
    return sorted([r for r in items if r["score"] >= min_score and r["verdict"] in ok and r["stage"] not in ("veto", "must_missing")],
                  key=lambda r: -r["score"])


def to_csv(items):
    f = io.StringIO()
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    for r in items:
        w.writerow({k: (why(r) if k == "why" else r.get(k, "")) for k in FIELDS})
    return f.getvalue()


def to_json(items):
    return json.dumps([{k: (why(r) if k == "why" else r.get(k)) for k in FIELDS} for r in items], ensure_ascii=False, indent=1)


def to_career_ops(items):
    """career-ops `/career-ops pipeline`이 읽는 형식 — 고른 공고의 평가·이력서 맞춤·지원 추적은 career-ops가 이어서 한다."""
    lines = []
    for r in items:
        clean = lambda s: (s or "").replace("|", "/").strip()  # noqa: E731
        lines.append(f"- [ ] {r['url']} | {clean(r['company'])} | {clean(r['title'])} | {clean(r['location']) or 'Korea'} | note: k-jobs {r['score']}점"
                     + (f", {clean(why(r))}" if why(r) else ""))
    return "\n".join(lines) + ("\n" if lines else "")
