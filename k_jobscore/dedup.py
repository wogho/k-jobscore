"""같은 공고 묶기 — 여러 사이트에 함께 올렸거나 다시 올린 공고.

키 = 회사(법인 표기·기호 뺀 것) + 제목(회사 이름·[신입]/[정규직] 같은 일반 꼬리표·기호 뺀 것) + 시·도.
[공덕]·[아산]처럼 근무지·부서를 가르는 꼬리표는 남긴다(다른 공고를 하나로 묶지 않게).

- 상세 확인: 본문은 사이트마다 받는다(사이트마다 문구가 달라 요구조건을 잡을 기회가 는다). 비싼 이미지 글자 읽기만
  같은 이미지(내용 sha1)면 다시 하지 않는다(store.OcrCache, ocr.read_images).
- 화면: 같은 키의 공고는 한 줄로 — 대표 하나에 나머지를 also로 붙인다(view.items, dedup.enabled).
"""
import re

from .normalize import region

GENERIC_TAG = re.compile(r"\s*(?:신입|경력|신입\s*[/·,]\s*경력|경력\s*[/·,]\s*신입|신입\s*및\s*경력|정규직|계약직|인턴|채용|모집|급구|마감\s*임박|"
                         r"~?\s*\d{1,2}\s*/\s*\d{1,2}|d-\d+|상시)\s*", re.I)
SEVERITY = {"drop": 3, "ok": 2, "hold": 1, "pending": 0}   # 보류 = 표기 없음 — 다른 사이트에서 확인한 '맞음'이 더 많이 안다
BRACKET = re.compile(r"[\[(【<]([^\])】>]*)[\])】>]")


def company_key(company):
    return re.sub(r"\(주\)|㈜|주식회사|\(유\)|유한회사|\(재\)|\(사\)|[^0-9a-z가-힣]", "", (company or "").lower())


def title_key(title, ck):
    t = (title or "").lower()
    t = BRACKET.sub(lambda m: "" if (ck and ck in company_key(m.group(1))) or GENERIC_TAG.fullmatch(m.group(1)) else m.group(1), t)
    t = re.sub(r"[^0-9a-z가-힣]", "", t)
    return t.replace(ck, "") if ck and len(ck) >= 2 else t


def key(title, company, location):
    ck = company_key(company)
    tk = title_key(title, ck)
    return f"{ck}|{tk}|{region(location)}" if ck and tk else ""


def group(items, site_order=("saramin", "jobkorea", "wanted", "remember")):
    """view 항목 목록 → 대표만 남긴 목록. 대표 = 가장 많이 아는 판정(불일치 > 맞음 > 보류 — 한 사이트 본문에서라도 요구조건이 걸리면 불일치, 표기 없는 보류보다 확인된 맞음),
    그다음 상세를 확인했고 마감이 가장 늦은 것(같으면 site_order 순).
    나머지는 대표의 also=[{source, sid, url, deadline}]로."""
    rank = {s: i for i, s in enumerate(site_order)}
    by, order = {}, []
    for it in items:
        k = key(it["title"], it["company"], it.get("location", ""))
        if not k:
            k = f"_{it['source']}:{it['sid']}"
        if k not in by:
            by[k] = []
            order.append(k)
        by[k].append(it)
    out = []
    for k in order:
        g = by[k]
        g.sort(key=lambda x: (-SEVERITY.get(x.get("verdict"), 0), x.get("stage") == "pending", -_dl(x.get("deadline")), rank.get(x["source"], 9)))
        top = g[0]
        top["also"] = [{"source": x["source"], "sid": x["sid"], "url": x["url"], "deadline": x.get("deadline", "")} for x in g[1:]]
        out.append(top)
    return out


def _dl(d):
    """마감일 → 정렬용 숫자(날짜가 아니면 상시로 보고 가장 늦게)."""
    return int(d.replace("-", "")) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d or "") else 99991231
