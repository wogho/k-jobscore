"""사이트마다 다른 표기를 한 가지로 — 마감일, 경력, 학력, 지역."""
import re
from datetime import datetime, timedelta


def deadline_norm(t, now=None):
    """마감일 → 'YYYY-MM-DD' 또는 '상시'·'채용시'(사이트마다 '~ 12/26(토)', '2070-01-01', ISO 등 제각각)."""
    t = (t or "").strip()
    if not t:
        return ""
    if t.startswith(("2070", "2099", "9999")):
        return "상시"
    if "오늘마감" in t or "내일마감" in t:
        return ((now or datetime.now()) + timedelta(days=1 if "내일" in t else 0)).strftime("%Y-%m-%d")
    if any(k in t for k in ("상시", "채용시")):
        return "채용시" if "채용시" in t else "상시"
    m = re.match(r"(20\d{2})-(\d{2})-(\d{2})", t)
    if m:
        return m.group(0)
    m = re.search(r"(\d{1,2})/(\d{1,2})", t)
    if m:
        now = now or datetime.now()
        mo, d = int(m.group(1)), int(m.group(2))
        y = now.year + (1 if mo < now.month - 6 else 0)
        return f"{y}-{mo:02d}-{d:02d}"
    return t[:20]


def career_range(lo, hi):
    """연차 범위 → 표시. 상한 20년 이상(원티드는 100)은 '이상'으로."""
    if not lo:
        return "신입" if not hi or hi >= 20 else f"신입~{hi}년"
    return f"경력 {lo}년 이상" if not hi or hi >= 20 else f"경력 {lo}~{hi}년"


def career_from_text(t):
    """'신입' '경력무관' '신입·경력' '경력 1년↑' '경력(1~3년)' → (표시, 최소 연차 또는 None, 신입 가능)."""
    t = (t or "").replace(" ", "")
    if not t:
        return "", None, None
    newbie = "신입" in t or "무관" in t
    m = re.search(r"(\d+)(?:~\d+)?년", t)
    return t, (int(m.group(1)) if m and not newbie else (0 if newbie else None)), newbie


def edu_from_text(t):
    t = t or ""
    for k, v in (("무관", "무관"), ("박사", "박사"), ("석사", "석사"), ("초대졸", "초대졸"), ("대졸", "대졸"), ("고졸", "고졸")):
        if k in t:
            return v
    return "미표기"


SIDO = {"서울": "서울", "경기": "경기", "인천": "인천", "부산": "부산", "대구": "대구", "광주": "광주", "대전": "대전", "울산": "울산", "세종": "세종",
        "강원": "강원", "충북": "충북", "충청북": "충북", "충남": "충남", "충청남": "충남", "전북": "전북", "전라북": "전북", "전남": "전남", "전라남": "전남",
        "경북": "경북", "경상북": "경북", "경남": "경남", "경상남": "경남", "제주": "제주", "전국": "전국", "해외": "해외"}


def region(loc):
    """'경기도 성남시' '경기전체' '서울특별시 강남구' → '경기' '경기' '서울'. 모르면 ''."""
    s = re.sub(r"\s+", "", loc or "")
    for k in sorted(SIDO, key=len, reverse=True):
        if s.startswith(k):
            return SIDO[k]
    return ""
