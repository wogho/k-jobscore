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
    ("초대졸", re.compile(r"초대졸|전문대|전문\s*학사|\(\s*전문\s*\)\s*학사|2\s*[,·~]?\s*3\s*년제|2년제|3년제|"
                         r"(?:대졸|졸업)\s*(?:이상)?\s*\(\s*2\s*(?:년)?\s*[,·~/]\s*3\s*년")),
    ("대졸", re.compile(r"4\s*년제|학사\s*(?:학위)?\s*(?:이상|소지|취득)|대졸\s*(?:이상|자)|대학교?\s*졸업\s*(?:이상|자|예정)|대학\s*\(\s*4\s*년")),
    ("석사", re.compile(r"석사\s*(?:이상|학위|소지|졸업)|석\s*[·ㆍ/,]\s*박사")),
    ("박사", re.compile(r"박사\s*(?:이상|학위|소지)")),
]
# "아래 중 하나의 요건을 충족하면" — 뒤따르는 줄들은 '또는'으로 묶인 갈래(하나만 맞으면 된다)
OR_HEAD = re.compile(r"(?:아래|다음)\s*(?:중|조건\s*중|요건\s*중)\s*(?:하나|한\s*가지|1\s*(?:가지|개))|중\s*(?:하나|한\s*가지)\s*(?:이상\s*)?(?:의\s*)?(?:요건|조건|자격)|one\s+of\s+the\s+following", re.I)
# 본문 학력이 목록 표기보다 우선하는 '분명한' 요구 — '대졸 이상'만으로는 2·3년제 포함인 공고가 많아 목록 표기를 따른다
EDU_STRONG = re.compile(r"4\s*년제|(?<!전문)(?<!\(전문\))학사|석사|박사|석\s*[·ㆍ/,]\s*박사")
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


def or_groups(lines):
    """요구조건 줄에서 '아래 중 하나' 묶음 → [(머리 줄 번호, [갈래 줄 번호…])]. 갈래는 머리 뒤 최대 6줄 중 경력·학력 요구가 있는 줄."""
    out = []
    for i, line in enumerate(lines):
        if not OR_HEAD.search(line):
            continue
        opts = []
        for j in range(i + 1, min(len(lines), i + 7)):
            if OR_HEAD.search(lines[j]) or (len(lines[j]) <= 24 and HEAD_OTHER.search(lines[j])):
                break
            if _career_need(lines[j]) or edu_required([lines[j]])[0] not in (None, "무관"):
                opts.append(j)
        if len(opts) >= 2:
            out.append((i, opts))
    return out


def _career_need(text):
    return [int(m.group(1)) for rx in CAREER_NEED for m in rx.finditer(text)]


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
    notes = []
    # '아래 중 하나' 갈래: 갈래마다 경력·학력을 따로 보고, 모든 갈래가 안 맞으면 불일치(11-27 오탐: '경력 3년 이상' 또는 '석·박사+1년'을 맞음으로 봄)
    or_fail = None
    groups = or_groups(lines)
    skip = {j for _, opts in groups for j in opts}
    for _, opts in groups:
        why = []
        for j in opts:
            n = _career_need(lines[j])
            lv_o, _, soft_o = edu_required([lines[j]], ed.get("equivalent_ok", True))
            bad = []
            if n and min(n) > max_years:
                bad.append(f"경력 {min(n)}년 이상")
            if lv_o in RANK and RANK[lv_o] > my and not soft_o:
                bad.append(f"{lv_o} 이상")
            if not bad:
                break   # 맞는 갈래가 하나라도 있으면 통과
            why.append("·".join(bad))
        else:
            or_fail = " 또는 ".join(why)
    lines = [x for i, x in enumerate(lines) if i not in skip]
    req = "\n".join(lines)
    need = _career_need(req)
    # 본문이 분명히 요구하면 목록 표기('경력무관' 등)보다 본문이 우선(11-27 오탐: 사람인 목록 '경력무관', 본문 '현업 경력 3년 이상')
    if CAREER_OK.search(req):
        cv = "ok"
    elif need and min(need) > max_years:
        cv = "fail"
        notes.append(f"경력 {min(need)}년 이상 요구")
    elif need or any(k in (career or "") for k in ("신입", "무관")):
        cv = "ok"
    else:
        cv = "none"
    if or_fail:
        cv = "fail"
        notes.append(f"요건 중 하나 필요 — 모두 불일치: {or_fail}")
    body_lv, body_why, body_soft = edu_required(lines, ed.get("equivalent_ok", True))
    if edu in RANK and not (body_lv in RANK and not body_soft and RANK[body_lv] > RANK[edu] and EDU_STRONG.search(body_why)):
        lv, why, soft = edu, "목록 표기", False
    else:
        lv, why, soft = body_lv, body_why, body_soft
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
