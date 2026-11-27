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

from .dedup import company_key
from .filters import _rx, categorize, company_kinds

OPEN = "_open"      # 공채형, 직무 확인 중(보류)
BODY = "_body"      # 직무를 본문 모집 부문에서 확인
EXCLUDED = "_x"     # 모집 부문을 읽었으나 맞는 직무 없음 — 화면에서 뺌

OPEN_TITLE = re.compile(r"공채|공개\s*채용|신입\s*(?:사원|행원|직원)|채용형\s*인턴|[상하]\s*반기|정기\s*채용|신규\s*(?:직원|채용)|일반직|대졸\s*신입|"
                        r"경력\s*사원\s*채용|\d{4}\s*년?\s*(?:도\s*)?(?:신입|채용)", re.I)
SECTION_HEAD = re.compile(r"모집\s*(?:부문|분야|직무|직군|요강|개요)|채용\s*(?:부문|분야|직무|직군|분야\s*및)|지원\s*분야|선발\s*(?:분야|부문|직무)|"
                          r"직무\s*(?:소개|안내|및\s*자격)|채용\s*인원|모집\s*인원|recruit(?:ing)?\s*(?:field|position)", re.I)
SECTION_END = re.compile(r"전형\s*(?:절차|일정|방법|안내)|접수\s*(?:기간|방법|안내)|지원\s*(?:방법|서류|기간)|제출\s*서류|복리\s*후생|복지|혜택|"
                         r"유의\s*사항|기타\s*사항|문의\s*처?|근무\s*조건|급여|처우", re.I)
# 제목에 IT가 아닌 직무가 분명히 적힌 공채는 받지 않는다(11-28 최종검증: '공무직(시설경비원)', '(미화)', '대체인력(일반사무)')
# 회사 이름으로 은행·공공·대기업이 확인되면 '…채용공고'·'…직원 모집'만 있어도 공채로 본다(11-28: '2026년도 한국자산관리공사 정규직 및 전문계약직 채용공고')
WEAK_OPEN_TITLE = re.compile(r"채용|모집|recruit", re.I)
# 제목에 '하나은행'만 넣은 인력·대행 회사 공고(대출상담사·콜센터 등)는 공채가 아니다
AGENCY = re.compile(r"인력|휴먼|파워|서치|아웃소싱|에이치알|HR|모기지|파트너스|에이전시|리크루|잡|커리어|매니지먼트|서비스\s*\(?주|텔레콤\s*서비스|씨에스|CS", re.I)
NON_IT_TITLE = r"마케팅|마케터|\bMD\b|머천다이저|디자이너|회계|세무|노무|법무|홍보|상담|텔러|대출|콜센터|\bTM\b|아웃바운드|인바운드|영업|보험\s*설계|금융\s*플래너|설계사|간호사|경비|미화|청소|환경\s*미화|조리|급식|운전|기사\s*\(|시설\s*관리|소방|안전\s*관리|일반\s*사무|사무\s*보조|행정\s*보조|간호|요양|보육|돌봄|" \
               r"상담원|안내원|주차|검침|배송|생산직|현장직|물류|영양사|사서|강사|연구원\s*\(?(?:생명|화학|바이오)"
MIN_READABLE = 200   # 공백 뺀 글자 수 — 이보다 짧으면 링크뿐인 본문으로 본다
SHORT_LINE = 40      # 모집 부문에서 직무를 찾을 줄의 최대 길이
# 본문에서는 제목용 표현이 너무 넓은 직무 — '개발'(기획개발·인재개발원), '데이터'(데이터 입력), '네트워크 구축'(투자사 네트워크)에 걸리지 않게
# 좁은 표현을 쓴다. 직무에 body 정규식이 있으면 그것을, 없으면 여기(프리셋 직무 id), 그것도 없으면 제목 표현을 쓴다.
BODY_RX = {
    "digital": r"디지털|\bICT\b|\bIT\b|전산|정보\s*기술|정보\s*시스템|정보화|소프트웨어|\bSW\b|AI\s*[·/]?\s*(?:AX|플랫폼|인프라|서비스)|\bAX\b",
    "infra": r"시스템\s*(?:엔지니어|운영|관리|구축)|IT\s*인프라|(?:AI|클라우드|서버|전산|네트워크|정보)\s*인프라|서버\s*(?:엔지니어|관리|운영)|"
             r"클라우드|네트워크\s*(?:엔지니어|장비|운영)|리눅스|linux|데이터\s*센터",
}


def opts(cfg):
    o = cfg.get("open_call") or {}
    return o.get("enabled", True), set(o.get("companies") or ["bank", "public", "big", "lab"])


# 제목에서 걷어낼 일반 말 — 이것과 회사 이름·연도·회차·지역을 빼고 남는 말이 없으면 '직무명 없음'(11-28 사용자:
# "제목에 직무명이 없는 공개채용·채용형 인턴 모집은 불러오고, 다른 직무명이 명확히 적힌 것은 제외하고 내용까지 확인")
GENERIC = re.compile(r"채용\s*연계형|채용\s*전제형|채용형|체험형|전문\s*계약직|무기\s*계약직|계약직|계약\s*사원|계약|정규직|기간제|대체\s*인력|육아\s*휴직\s*대체|"
                     r"공개\s*채용|공채|채용|공고|모집|선발|안내|신입|경력|인턴십|인턴|청년|직원|사원|행원|임직원|신규|정기|수시|상반기|하반기|"
                     r"일반직|일반|행정직|공무직|부문별|분야별|각\s*부문|부문|분야|및|등|년도|년|분기|회차|회|차|제|대졸|고졸|초대졸|학사|석사|박사|"
                     r"상시|급구|본사|지사|지역\s*본부|본부|센터|지점|전국|수도권|서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|"
                     r"경북|경남|제주|명|각|외|의|를|을|및|with|recruit(?:ment)?|hiring|intern(?:ship)?|new|grad(?:uate)?", re.I)
IT_ABBR = re.compile(r"^(?:IT|ICT|AI|AX|DX|SW|IDC|SRE|QA|DB|ERP|MES|OT|SOC|CERT)$", re.I)


def title_triage(title, company, cfg):
    """제목 → 'role'(설정한 직무가 제목에 있음) / 'none'(직무명 없음 — 본문 모집 부문 확인) / 'other'(다른 직무가 분명함)."""
    t = title or ""
    if categorize(t, company, cfg["roles"]):
        return "role"
    ck = company_key(company)
    s = t
    # 회사 이름(괄호 안 포함)과 영문 약칭(KT&G·HTT 같은 대문자 6자 이하, IT 약어는 남김)을 걷어낸다
    s = re.sub(r"[\[(【<]([^\])】>]*)[\])】>]", lambda m: " " if ck and ck in company_key(m.group(1)) else f" {m.group(1)} ", s)
    s = " ".join(w for w in re.split(r"[\s/·,|~\-_+:]+", s)
                 if not (re.fullmatch(r"[A-Z0-9&.]{1,6}", w) and not IT_ABBR.match(w)) and not (ck and len(ck) >= 2 and ck in company_key(w)))
    s = re.sub(r"\d+", " ", s)
    s = GENERIC.sub(" ", s)
    rest = re.sub(r"[^0-9a-z가-힣\u3040-\u30ff\u4e00-\u9fff]", "", s.lower())   # 한자·가나도 남는 말(중국어 제목 등)
    if ck and len(ck) >= 2:
        rest = rest.replace(ck, "")
    return "none" if len(rest) <= 1 else "other"


def is_open(title, company, cfg):
    """공채로 받아 상세 모집 부문에서 직무를 확인할 공고인지.
    - 회사가 대기업·공공기관·연구기관·은행(사이트 기업형태 필터에서 본 회사 또는 이름으로 확인)이고
    - 제목에 직무명이 없음(title_triage = none — 다른 직무가 분명하면 제외)
    - 제목 감점·즉시 제외 단어가 없음(상세를 읽지 않으므로 직무 확인이 끝나지 않는다)"""
    on, kinds = opts(cfg)
    t = title or ""
    if not on:
        return False
    own = company_kinds("", company) & kinds
    via_title = OPEN_TITLE.search(t) and company_kinds(t, company) & kinds and not AGENCY.search(company or "")   # 법인명이라 회사로 안 잡힐 때
    if not (own or via_title):
        return False
    if re.search((cfg.get("open_call") or {}).get("exclude_title") or NON_IT_TITLE, t, re.I):
        return False
    if title_triage(t, company, cfg) != "none":
        return False
    from .score import score
    return score(t, "", cfg, False)["stage"] not in ("title_minus", "veto")


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
            if len(line) > SHORT_LINE:
                continue   # 부문 이름·표 칸 같은 짧은 줄만 — 업무 설명 문장의 '개발·데이터'에 걸리지 않게(11-28 실수집: 물리치료사·매장 관리가 디지털로)
            if _rx(r.get("body") or BODY_RX.get(r["id"]) or r["title"]).search(line) and not (r.get("exclude_title") and _rx(r["exclude_title"]).search(line)):
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
