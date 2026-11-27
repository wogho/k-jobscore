"""직무 분류와 조건 거르기.

- 목록 단계(passes): 직무(roles) · 경력 표기 · 학력 표기 · 고용형태 · 지역 · 회사 — 저장할지 정한다.
- 상세 단계(judge): 상세에서 확인한 경력·학력·전공 필수를 사용자 설정(keep/hold/drop)에 맞춰 판정한다.
"""
import re

from .normalize import region
from .verify import RANK, major_required

RE_BANK = re.compile(r"은행|뱅크|금융지주|농협|수협|신협|새마을금고|저축은행|\bbank\b", re.I)
RE_PUBLIC = re.compile(r"공사(?!\s*현장)|공단|진흥원|공공기관|관리원|정보원|평가원|재단|연구원|시청|구청|군청|도청|교육청|국립|국가|정부|위원회|공기업|준정부|"
                       r"중앙회|한국\S*(원|공사|공단|센터)|\(재\)|의회|법원|검찰|경찰청")
RE_NOT_PUBLIC = re.compile(r"학원|아카데미|인재개발원|교육원|직업전문학교|캠퍼스|\(사\)|협회")
RE_PRIVATE = re.compile(r"\(주\)|㈜|주식회사|\(유\)|유한회사")
# 대기업: 공정위 대기업집단 중심, 회사명에만 대조(제목의 일반 낱말과 겹치지 않게)
RE_BIG = re.compile(r"삼성|현대(자동차|모비스|건설|제철|백화점|오토에버|카드|캐피탈|글로비스|엘리베이터|해상|로템|위아|트랜시스|그린푸드|홈쇼핑)|HD현대|"
                    r"\bSK|SK[가-힣]|\bLG|엘지|롯데|포스코|POSCO|한화|\bGS|GS[가-힣]|신세계|이마트|\bKT\b|KT[가-힣]|케이티|\bCJ|CJ[가-힣]|씨제이|한진|대한항공|"
                    r"카카오|네이버|NAVER|\bLS\b|LS[가-힣]|두산|효성|아모레|쿠팡|미래에셋|\bDB[가-힣 ]|코오롱|\bOCI\b|에쓰오일|S-?OIL|^기아|셀트리온|금호|HL[가-힣]|"
                    r"넷마블|엔씨소프트|크래프톤|넥슨|하이브|\bKCC\b|한국타이어|SPC|농심|오뚜기|^대상\b|대상㈜|대상\(주\)|동원|하림|영풍|태광|세아|부영|중흥|호반|"
                    r"^DL|DL[가-힣]|HDC|교보|한국투자|삼천리|현대백화점|HMM|에코프로|한국앤컴퍼니|BGF|이랜드|태영|KG[가-힣]|다우키움|키움", re.I)


def company_kinds(title, company):
    both = f"{title or ''} {company or ''}"
    c = company or ""
    kinds = {"any"}
    if RE_PUBLIC.search(both) and not RE_PRIVATE.search(c) and not RE_NOT_PUBLIC.search(c):
        kinds.add("public")
    if RE_BANK.search(both):
        kinds.add("bank")
    if RE_BIG.search(c):
        kinds.add("big")
    return kinds


_RX = {}


def _rx(p):
    if p not in _RX:
        _RX[p] = re.compile(p, re.I)
    return _RX[p]


def categorize(title, company, roles):
    """→ 맞는 직무 id 목록. roles가 비면 ['all']."""
    if not roles:
        return ["all"]
    kinds = company_kinds(title, company)
    out = []
    for r in roles:
        if not _rx(r["title"]).search(title or ""):
            continue
        if r.get("exclude_title") and _rx(r["exclude_title"]).search(title or ""):
            continue
        if not kinds & set(r.get("company") or ["any"]):
            continue
        out.append(r["id"])
    return out


def passes(p, cfg):
    """목록 단계 거르기. p에 cats를 채운다 → 남길지."""
    c = cfg["conditions"]
    p["cats"] = categorize(p["title"], p.get("company", ""), cfg["roles"])
    if not p["cats"]:
        from . import opencall   # 은행·공공·대기업 공채는 제목에 직무가 없다 — 상세의 모집 부문에서 확인(opencall.py)
        if not opencall.is_open(p["title"], p.get("company", ""), cfg):
            return False
        p["cats"] = [opencall.OPEN]
    text = p["title"] + " " + p.get("emp_type", "")
    if any(x and x in text for x in c["employment_exclude"]):
        return False
    comp = p.get("company", "")
    if any(x and x in comp for x in c["companies_exclude"]):
        return False
    if c["companies_only"] and not any(x and x in comp for x in c["companies_only"]):
        return False
    if c["regions"]:
        rg = region(p.get("location", ""))
        if rg and rg not in c["regions"] and rg != "전국":
            return False
    cr = c["career"]
    intern = "인턴" in text
    cm = p.get("career_min")
    if cm is None and not any(k in p.get("career", "") for k in ("신입", "무관")):
        career_ok = cr["unlabeled"] != "drop"
    else:
        career_ok = (intern and cr["include_intern"]) or (cm or 0) <= cr["max_required_years"] or any(k in p.get("career", "") for k in ("신입", "무관"))
    ed = c["education"]
    e = p.get("edu", "미표기")
    edu_ok = (ed["unlabeled"] != "drop") if e not in RANK else RANK[e] <= RANK[ed["my_level"]]
    return career_ok and edu_ok


def judge(career_v, edu_v, note, cfg):
    """상세 확인 결과를 설정에 맞춰 → 'ok' / 'hold'(남기고 표시) / 'drop'(숨김)."""
    c = cfg["conditions"]
    if career_v == "fail" or edu_v == "fail":
        return "drop"
    flags = []
    if career_v == "none":
        flags.append(c["career"]["unlabeled"])
    if edu_v == "none":
        flags.append(c["education"]["unlabeled"])
    if major_required(note):
        flags.append(c["education"]["major_required"])
    return "drop" if "drop" in flags else "hold" if "hold" in flags else "ok"
