"""상세 글(본문 + 이미지 글자)에서 경력·학력 요구조건 확인.

원칙(career-ops jd-years.mjs와 같은 생각): 공고가 '분명히' 요구할 때만 불일치로 본다.
우대사항 줄·수습/연봉 안내 줄·"이에 준하는 경험" 줄은 요구조건이 아니다. 애매하면 none(표기 없음)으로 두고,
none을 어떻게 다룰지는 사용자 설정(conditions.*.unlabeled: keep/hold/drop)이 정한다.
"""
import re

LEVELS = ["무관", "고졸", "초대졸", "대졸", "석사", "박사"]
RANK = {k: i for i, k in enumerate(LEVELS)}

NOT_REQ = re.compile(r"수습|처우|연봉|급여|인센티브|보상|직급|호봉")
EDU_SOFT = re.compile(r"이에\s*준하|동등|상응|or\s*equivalent", re.I)
PREFER = re.compile(r"우대|가산|플러스|있으면\s*좋|선호|nice\s*to\s*have|preferred", re.I)
HEAD_PREFER = re.compile(r"우대|가산|플러스|선호|nice\s*to\s*have|preferred", re.I)
HEAD_OTHER = re.compile(r"자격\s*요건|지원\s*자격|필수|요구\s*사항|이런\s*분|주요\s*업무|담당\s*업무|업무\s*내용|복리|혜택|근무\s*조건|근무\s*환경|전형|절차|접수|"
                        r"모집\s*(분야|부문)|requirements|qualifications|responsibilities", re.I)
CAREER_NEED = [re.compile(r"(?:경력|경험|실무|근무)[^\n]{0,20}?(\d{1,2})\s*년\s*(?:이상|↑|以上)"),
               re.compile(r"(\d{1,2})\s*년\s*(?:이상|↑)[^\n]{0,8}?(?:의\s*)?(?:경력|경험|실무)")]
CAREER_OK = re.compile(r"신입|경력\s*무관|경력\s*상관\s*없|인턴|경력\s*:\s*무관")
EDU_ANY = re.compile(r"학력\s*(?:무관|상관\s*없|제한\s*없)")
# 요구 학력 표현 → 단계. 낮은 단계부터 — 한 줄에 여러 개면 가장 낮은 것이 '이상' 기준
EDU_NEED = [
    ("고졸", re.compile(r"고졸|고등학교\s*졸업")),
    ("초대졸", re.compile(r"초대졸|전문대|2\s*[,·~]?\s*3\s*년제|2년제|3년제")),
    ("대졸", re.compile(r"4\s*년제|학사\s*(?:학위)?\s*(?:이상|소지|취득)|대졸\s*(?:이상|자)|대학교?\s*졸업\s*(?:이상|자|예정)|대학\s*\(\s*4\s*년")),
    ("석사", re.compile(r"석사\s*(?:이상|학위)")),
    ("박사", re.compile(r"박사\s*(?:이상|학위|소지)")),
]
MAJOR_NEED = re.compile(r"(?:관련|해당|컴퓨터|전산|정보|전자|통신)[^\n]{0,12}?전공\s*(?:자\s*)?(?:필수|만|한정|자에\s*한)|전공\s*필수")


def req_lines(text):
    """요구조건으로 볼 줄만 — '우대사항' 제목 아래 줄과 '우대'가 들어간 줄, 수습·연봉 안내 줄은 뺀다."""
    out, prefer = [], False
    for line in re.split(r"[\n•ㆍ■▶◆●]+|\s-\s", text or ""):
        line = line.strip()
        if not line:
            continue
        short = len(line) <= 24
        if short and HEAD_PREFER.search(line):
            prefer = True
            continue
        if short and HEAD_OTHER.search(line):
            prefer = False
        if not prefer and not PREFER.search(line) and not NOT_REQ.search(line):
            out.append(line)
    return out


def edu_required(lines, equivalent_ok=True):
    """요구조건 줄에서 요구 학력 → (단계 또는 None, 근거, soft). '학력 무관'이면 '무관'.
    soft=True: "이에 준하는 경험" 같은 대안이 붙은 줄에서만 나온 학력 — 필수 요건이 아니다."""
    hard, soft = [], []
    for line in lines:
        if EDU_ANY.search(line):
            return "무관", line[:80], False
        bucket = soft if equivalent_ok and EDU_SOFT.search(line) else hard
        for lv, rx in EDU_NEED:
            if rx.search(line):
                bucket.append((RANK[lv], lv, line[:80]))
    if hard:
        _, lv, why = min(hard)
        return lv, why, False
    if soft:
        _, lv, why = min(soft)
        return lv, why, True
    return None, "", False


def verify(text, career="", edu="", cond=None):
    """→ (career_v, edu_v, note) — 값: ok(맞음) / fail(불일치) / none(상세에 표기 없음).
    cond: config['conditions'] (없으면 기본: 경력 2년 이하, 내 학력 초대졸)."""
    cond = cond or {}
    max_years = (cond.get("career") or {}).get("max_required_years", 2)
    ed = cond.get("education") or {}
    my = RANK.get(ed.get("my_level", "초대졸"), 2)
    lines = req_lines(text)
    req = "\n".join(lines)
    notes = []
    need = [int(m.group(1)) for rx in CAREER_NEED for m in rx.finditer(req)]
    if CAREER_OK.search(req) or any(k in (career or "") for k in ("신입", "무관")):
        cv = "ok"
    elif need and min(need) > max_years:
        cv = "fail"
        notes.append(f"경력 {min(need)}년 이상 요구")
    elif need:
        cv = "ok"
    else:
        cv = "none"
    lv, why, soft = (edu, "목록 표기", False) if edu in RANK else edu_required(lines, ed.get("equivalent_ok", True))
    if lv is None:
        ev = "none"
    elif RANK[lv] <= my:
        ev = "ok"
    elif soft:
        ev = "none"   # 내 학력보다 높지만 "이에 준하는 경험"도 받는다 — 필수 아님
    else:
        ev = "fail"
        notes.append(f"학력 {lv} 이상 요구" + (f" — '{why}'" if why and why != "목록 표기" else ""))
    if MAJOR_NEED.search(req):
        notes.append("전공 필수")
    return cv, ev, "; ".join(notes)


def major_required(note):
    return "전공 필수" in (note or "")
