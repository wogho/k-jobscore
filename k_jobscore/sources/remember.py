"""리멤버 — career-api 공고 검색(min/max_experience, 헤드헌터 공고 제외)."""
import json
import time

from ..normalize import career_range, deadline_norm

SITE = "remember"
EDU = {"none": "무관", "high_school": "고졸", "associate": "초대졸", "bachelor": "대졸", "master": "석사", "doctor": "박사", "doctorate": "박사"}


def queries(cfg):
    oc = cfg.get("open_call") or {}
    return list(cfg["queries"]) + ([q for q in oc.get("queries", []) if q not in cfg["queries"]] if oc.get("enabled") else [])


def search(ctx, query, pages):
    out = []
    max_years = ctx.cfg["conditions"]["career"]["max_required_years"]
    for i in range(1, pages + 1):
        srch = {"min_experience": 0, "max_experience": max_years, "organizationType": "without_headhunter", **({"keywords": [query]} if query else {})}
        d = json.loads(ctx.net.get("https://career-api.rememberapp.co.kr/job_postings/search", site=SITE,
                                   data=json.dumps({"search": srch, "page": i, "per": 50}), headers={"Content-Type": "application/json"}))
        for j in d.get("data") or []:
            ad = (j.get("addresses") or [{}])[0] or {}
            lo, hi = j.get("min_experience"), j.get("max_experience")
            out.append({"source": SITE, "sid": str(j["id"]), "url": f"https://career.rememberapp.co.kr/job/posting/{j['id']}", "title": j.get("title") or "",
                        "company": (j.get("organization") or {}).get("name") or "",
                        "location": " ".join(x for x in (ad.get("address_level1"), ad.get("address_level2")) if x),
                        "career": career_range(lo, hi), "career_min": lo or 0,
                        "edu": EDU.get(str(j.get("education_requirement")), "미표기"), "emp_type": j.get("job_rank_category") or "",
                        "deadline": deadline_norm((j.get("ends_at") or "")[:10]) or "채용시"})
        if i >= (d.get("meta") or {}).get("total_pages", 0) or ctx.seen_enough(SITE, [j["id"] for j in d.get("data") or []]):
            break
        time.sleep(ctx.net.delay)
    return out


def detail(ctx, sid):
    d = json.loads(ctx.net.get(f"https://career-api.rememberapp.co.kr/job_postings/{sid}", site=SITE))
    d = d.get("data", d)
    body = "\n".join(str(d.get(k) or "") for k in ("job_description", "qualifications", "preferred_qualifications", "application_requirements",
                                                   "additional_information", "recruiting_process", "introduction"))
    return body, [], EDU.get(str(d.get("education_requirement")), "")
