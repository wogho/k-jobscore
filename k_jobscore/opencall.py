"""공채형 공고의 직무를 본문 '모집 부문'에서 확인.

은행·공공기관·대기업 공채는 제목에 직무가 없다("2026년 상반기 신입행원 채용"). 본문 모집 부문에 정보보안·디지털·AX가 있어도
제목으로만 직무를 나누면 목록 단계에서 버려진다. 그래서:
1) 목록 단계: 회사가 open_call.companies(기본 은행·공공·대기업)이고 제목이 공채형이면 버리지 않고 '_open'(직무 확인 중)으로 남긴다.
2) 상세 단계: 본문·이미지 글자 중 '모집 부문·모집 분야·채용 직무' 단락만 읽고 직무를 다시 나눈다.
   본문 전체를 보면 '디지털 금융', 'IT 역량' 같은 회사 소개 문구에 걸리므로 단락으로 제한한다.
   - 맞는 직무가 있으면 그 직무 + '_body'(본문에서 확인) 표시
   - 단락은 읽었는데 맞는 직무가 없으면 '_x'(화면에서 뺌)
   - 본문이 회사 채용 사이트 링크뿐이라 읽을 게 없거나 모집 부문 단락이 없으면 '_open' 그대로(보류 — 놓치는 것보다 낫다)
"""
import re

from .filters import _rx, company_kinds

OPEN = "_open"      # 공채형, 직무 확인 중(보류)
BODY = "_body"      # 직무를 본문 모집 부문에서 확인
EXCLUDED = "_x"     # 모집 부문을 읽었으나 맞는 직무 없음 — 화면에서 뺌

OPEN_TITLE = re.compile(r"공채|공개\s*채용|신입\s*(?:사원|행원|직원)|채용형\s*인턴|[상하]\s*반기|정기\s*채용|신규\s*(?:직원|채용)|일반직|대졸\s*신입|"
                        r"경력\s*사원\s*채용|\d{4}\s*년?\s*(?:도\s*)?(?:신입|채용)", re.I)
SECTION_HEAD = re.compile(r"모집\s*(?:부문|분야|직무|직군|요강|개요)|채용\s*(?:부문|분야|직무|직군|분야\s*및)|지원\s*분야|선발\s*(?:분야|부문|직무)|"
                          r"직무\s*(?:소개|안내|및\s*자격)|채용\s*인원|모집\s*인원|recruit(?:ing)?\s*(?:field|position)", re.I)
SECTION_END = re.compile(r"전형\s*(?:절차|일정|방법|안내)|접수\s*(?:기간|방법|안내)|지원\s*(?:방법|서류|기간)|제출\s*서류|복리\s*후생|복지|혜택|"
                         r"유의\s*사항|기타\s*사항|문의\s*처?|근무\s*조건|급여|처우", re.I)
MIN_READABLE = 200   # 공백 뺀 글자 수 — 이보다 짧으면 링크뿐인 본문으로 본다


def opts(cfg):
    o = cfg.get("open_call") or {}
    return o.get("enabled", True), set(o.get("companies") or ["bank", "public", "big"])


def is_open(title, company, cfg):
    on, kinds = opts(cfg)
    return bool(on and OPEN_TITLE.search(title or "") and company_kinds(title, company) & kinds)


def section(text):
    """모집 부문 단락들(머리말부터 전형·접수·복리 같은 다음 머리말 전까지, 한 단락 최대 60줄)을 이어 붙인 것. 없으면 ''."""
    lines = [x.strip() for x in re.split(r"\n+", text or "")]
    out, i = [], 0
    while i < len(lines):
        if SECTION_HEAD.search(lines[i]) and len(lines[i]) <= 40:
            j = i + 1
            while j < len(lines) and j - i <= 60 and not (len(lines[j]) <= 30 and SECTION_END.search(lines[j])):
                j += 1
            out.extend(lines[i:j])
            i = j
        else:
            i += 1
    return "\n".join(x for x in out if x)


def body_roles(title, company, text, roles):
    """모집 부문 단락에서 맞는 직무 id 목록. 줄 단위로 대조하고, 직무의 제외 표현(예: '보안 요원')이 든 줄은 그 직무에 쓰지 않는다."""
    sec = section(text)
    kinds = company_kinds(title, company)
    out = []
    for r in roles:
        if not kinds & set(r.get("company") or ["any"]):
            continue
        for line in sec.splitlines():
            if _rx(r["title"]).search(line) and not (r.get("exclude_title") and _rx(r["exclude_title"]).search(line)):
                out.append(r["id"])
                break
    return out, bool(sec)


def resolve(title, company, text, cfg):
    """상세를 읽은 공채형 공고의 직무 → cats 목록."""
    found, has_section = body_roles(title, company, text, cfg["roles"])
    if found:
        return found + [BODY]
    readable = len(re.sub(r"\s", "", text or "")) >= MIN_READABLE
    return [EXCLUDED] if (has_section and readable) else [OPEN]


def scoring_text(cats, body):
    """공채형은 점수도 모집 부문 단락의 단어로만(여러 부문·회사 소개 문구가 섞이지 않게). 단락이 없으면 본문 그대로."""
    if OPEN in cats or BODY in cats:
        return section(body) or body
    return body
