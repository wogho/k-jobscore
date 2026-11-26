"""원티드 — /api/v4/jobs (연차 0~N년, 최신 순). 검색은 직무 분류 번호(tag_type_ids) 또는 검색어."""
import json
import time
import urllib.parse

from ..normalize import career_range, deadline_norm

SITE = "wanted"


def queries(cfg):
    return [("tag_type_ids", t) for t in cfg["wanted_tag_ids"]] + [("query", q) for q in cfg["wanted_queries"]]


def search(ctx, query, pages):
    out = []
    max_years = ctx.cfg["conditions"]["career"]["max_required_years"]
    for i in range(pages):
        q = urllib.parse.urlencode([("country", "kr"), ("job_sort", "job.latest_order"), ("years", 0), ("years", max_years),
                                    ("locations", "all"), ("limit", 100), ("offset", i * 100), query])
        d = json.loads(ctx.net.get(f"https://www.wanted.co.kr/api/v4/jobs?{q}", site=SITE))
        for j in d.get("data") or []:
            a = j.get("address") or {}
            lo, hi = j.get("annual_from"), j.get("annual_to")
            out.append({"source": SITE, "sid": str(j["id"]), "url": f"https://www.wanted.co.kr/wd/{j['id']}", "title": j.get("position") or "",
                        "company": (j.get("company") or {}).get("name") or "",
                        "location": " ".join(x for x in (a.get("location"), a.get("district")) if x),
                        "career": career_range(lo, hi), "career_min": lo or 0,
                        "edu": "미표기", "emp_type": "", "deadline": deadline_norm((j.get("due_time") or "")[:10]) or "상시"})
        if not (d.get("links") or {}).get("next") or ctx.seen_enough(SITE, [j["id"] for j in d.get("data") or []]):
            break
        time.sleep(ctx.net.delay)
    return out


def detail(ctx, sid):
    j = json.loads(ctx.net.get(f"https://www.wanted.co.kr/api/v4/jobs/{sid}", site=SITE))["job"]
    d = j.get("detail") or {}
    return "\n".join(str(d.get(k) or "") for k in ("intro", "main_tasks", "requirements", "preferred_points", "benefits", "hire_rounds")), [], ""
