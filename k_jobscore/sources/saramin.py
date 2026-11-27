"""사람인 — 공개 검색 결과 페이지(신입·경력무관, 등록일 순). 상세는 view-detail(본문 + 이미지)."""
import html as htmllib
import re
import time
import urllib.parse

from ..normalize import career_from_text, deadline_norm, edu_from_text
from ._util import html_images, html_text

SITE = "saramin"


def queries(cfg):
    oc = cfg.get("open_call") or {}
    return list(cfg["queries"]) + ([q for q in oc.get("queries", []) if q not in cfg["queries"]] if oc.get("enabled") else [])


TYPED = True   # 기업형태 필터 목록(company_type[]) 지원 — 검색어 없이 대기업·공공·연구소·금융 공고 전부(opencall)


def search(ctx, query, pages, ctype=None):
    out = []
    for i in range(1, pages + 1):
        params = {"searchType": "search", "searchword": query, "exp_cd": 1, "exp_none": "y", "recruitPage": i,
                  "recruitPageCount": 100, "recruitSort": "reg_dt"}
        if ctype:
            params["company_type[]"] = ctype
        q = urllib.parse.urlencode(params)
        h = ctx.net.get(f"https://www.saramin.co.kr/zf_user/search/recruit?{q}", site=SITE)
        blocks = h.split('<div class="item_recruit"')[1:]
        for b in blocks:
            rid = re.search(r'value="(\d+)"', b)
            title = re.search(r'<h2 class="job_tit">\s*<a[^>]*title="([^"]+)"', b)
            corp = re.search(r'<strong class="corp_name">\s*<a[^>]*>\s*([^<]+)', b)
            cond = re.search(r'<div class="job_condition">(.*?)</div>', b, re.S)
            spans = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<span>(.*?)</span>", cond.group(1), re.S)] if cond else []
            if not (rid and title):
                continue
            car = next((s for s in spans if "신입" in s or "경력" in s), "")
            edu = next((s for s in spans if any(k in s for k in ("졸", "학력", "석사", "박사"))), "")
            emp = next((s for s in spans if any(k in s for k in ("정규직", "계약직", "인턴", "아르바이트", "파견", "프리랜서"))), "")
            date = re.search(r'<span class="date">([^<]+)', b)
            ctext, cmin, _ = career_from_text(car)
            out.append({"source": SITE, "sid": rid.group(1), "url": f"https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx={rid.group(1)}",
                        "title": htmllib.unescape(title.group(1).strip()), "company": htmllib.unescape(corp.group(1).strip()) if corp else "",
                        "location": re.sub(r"\s+", " ", spans[0]) if spans else "", "career": ctext, "career_min": cmin,
                        "edu": edu_from_text(edu), "emp_type": emp, "deadline": deadline_norm(date.group(1) if date else "")})
        ids = [m.group(1) for b in blocks if (m := re.search(r'value="(\d+)"', b))]
        if len(blocks) < 100 or ctx.seen_enough(SITE, ids):
            break
        time.sleep(ctx.net.delay)
    return out


def detail(ctx, sid):
    h = ctx.net.get(f"https://www.saramin.co.kr/zf_user/jobs/relay/view-detail?rec_idx={sid}&rec_seq=0", site=SITE)
    return html_text(h), html_images(h, "https://www.saramin.co.kr"), ""
