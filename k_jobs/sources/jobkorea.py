"""잡코리아 — 공개 검색 페이지 안의 공고 데이터(careerType·educationCode). 상세는 GI_Read_Comt_Ifrm(본문 + 이미지)."""
import json
import re
import time
import urllib.parse

from ..normalize import deadline_norm
from ._util import html_images, html_text

SITE = "jobkorea"
EDU = {"0": "무관", "1": "고졸", "2": "고졸", "3": "고졸", "4": "초대졸", "5": "대졸", "6": "석사", "7": "박사"}   # 1·2(초·중졸)는 고졸 이하로 봄
REGION = re.compile(r"^(서울|경기|인천|부산|대구|광주|대전|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주|전국|해외)")


def queries(cfg):
    return list(cfg["queries"])


def search(ctx, query, pages):
    out = []
    for i in range(1, pages + 1):
        h = ctx.net.get(f"https://www.jobkorea.co.kr/Search/?stext={urllib.parse.quote(query)}&careerType=1&Page_No={i}", site=SITE)
        cards = {}
        for seg in re.split(r'(?=href="[^"]*/Recruit/GI_Read/\d+)', h)[1:]:
            gid = re.search(r'/Recruit/GI_Read/(\d+)', seg).group(1)
            cards.setdefault(gid, []).extend(x.strip() for x in re.findall(r">([^<>]{2,60})<", seg[:6000]) if x.strip())
        chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)\s*</script>', h, re.S)
        big = "".join(json.loads('"' + c + '"') for c in chunks)
        n = 0
        for m in re.finditer(r'\{"id":"(\d+)","legacyJobNo":"\d+","title":"((?:[^"\\]|\\.)*)"', big):
            seg = big[m.start():m.start() + 2500]

            def g(k):
                r = re.search(rf'"{k}":"?([^",}}]*)"?', seg)
                return r.group(1) if r else None
            ct, cr, ec = g("careerType"), g("careerRange"), g("educationCode")
            end = re.search(r'"applicationPeriod":\{"start":"[^"]*","end":"([^"]+)"', seg)
            area = re.search(r'"jobClassificationOrIndustry":"([^"]*)"', seg)
            card = cards.get(m.group(1)) or []
            cmin = 0 if ct in ("1", "3", "4") else (int(cr) if cr and cr.isdigit() and int(cr) < 100 else None)
            out.append({"source": SITE, "sid": m.group(1), "url": f"https://www.jobkorea.co.kr/Recruit/GI_Read/{m.group(1)}",
                        "title": json.loads('"' + m.group(2) + '"'), "company": g("postingCompanyName") or g("companyName") or "",
                        "location": next((x for x in card[:12] if REGION.match(x)), ""),
                        "career": {"1": "신입", "2": f"경력 {cr}년↑" if cr and cr != "100" else "경력", "3": "신입·경력", "4": "경력무관"}.get(ct or "", ""),
                        "career_min": cmin, "edu": EDU.get(ec or "", "미표기"),
                        "emp_type": "인턴" if "인턴" in (area.group(1) if area else "") else "",
                        "deadline": deadline_norm(end.group(1)[:10] if end else "")})
            n += 1
        if n == 0 or ctx.seen_enough(SITE, re.findall(r'\{"id":"(\d+)","legacyJobNo"', big)):
            break
        time.sleep(ctx.net.delay)
    return out


def detail(ctx, sid):
    h = ctx.net.get(f"https://www.jobkorea.co.kr/Recruit/GI_Read_Comt_Ifrm?Gno={sid}", site=SITE,
                    headers={"Referer": f"https://www.jobkorea.co.kr/Recruit/GI_Read/{sid}"})
    return html_text(h), html_images(h, "https://www.jobkorea.co.kr"), ""
