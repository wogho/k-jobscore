"""공고 적합도 점수 — 제목 먼저, 그다음 상세(본문 + 이미지 글자).

1. 제목에서 단어를 본다. 즉시 제외(veto) 단어가 있으면 0점, 감점 단어가 있으면(기본 설정) 상세를 보지 않는다.
2. 기본 점수이거나 가점이 있으면 상세까지 보고, 상세 단어 점수를 더한다(합은 ±body_cap 안).
3. 필수(must) 단어가 제목·상세 어디에도 없으면 0점.
점수는 화면을 열 때 지금 설정으로 다시 계산하므로, 설정을 바꾸면 바로 반영된다.
"""
import re

_RE = {}


def _rx(variant, match="auto"):
    """auto: 영문·숫자 4자 이하(OP·IDC·k8s·GPU·EDR…)는 단어 경계로 — 'DevOps'의 'Op', 'Vendor'의 'EDR'를 잡지 않게. 나머지는 포함 여부."""
    key = (variant, match)
    if key not in _RE:
        if match == "regex":
            _RE[key] = re.compile(variant, re.I)
        else:
            e = re.escape(variant)
            word = match == "word" or (match == "auto" and re.fullmatch(r"[A-Za-z0-9/+#.]{1,4}", variant) is not None)
            _RE[key] = re.compile(rf"(?<![A-Za-z0-9]){e}(?![A-Za-z0-9])" if word else e, re.I)
    return _RE[key]


def variants(w):
    return w["word"] if isinstance(w["word"], list) else [w["word"]]


def label(w):
    return variants(w)[0]


def hit(w, text):
    """단어(동의어 묶음 포함)가 글에 있으면 처음 맞은 표기, 없으면 None."""
    text = text or ""
    for v in variants(w):
        if _rx(v, w.get("match", "auto")).search(text):
            return v
    return None


def find(words, text):
    """간단한 형태: 문자열 목록 중 글에 있는 것(예전 API 호환)."""
    return [w for w in words if _rx(w).search(text or "")]


def _pts(w, where, d):
    if where in w:
        return w[where]
    sign = "minus" if w["kind"] == "minus" else "plus"
    return d[f"{sign}_{where}"]


def score(title, body, cfg, has_detail):
    """→ {score, stage, hits, tp, tm, bp, bm}.
    stage: veto(즉시 제외) / title_minus(상세 안 봄) / must_missing(필수 단어 없음) / detail(상세 반영) / pending(상세 확인 전)."""
    sc = cfg["score"] if "score" in cfg else cfg
    d, words = sc["defaults"], sc["words"]
    hits = []

    def add(w, where, found, pts):
        hits.append({"word": label(w), "found": found, "kind": w["kind"], "where": where, "pts": pts})

    def where_ok(w, where):
        return w.get("where", "both") in ("both", where)

    for w in words:
        if w["kind"] == "veto" and where_ok(w, "title") and (f := hit(w, title)):
            add(w, "title", f, 0)
            return _out(0, "veto", hits)
    s = sc["base"]
    for w in words:
        if w["kind"] in ("plus", "minus") and where_ok(w, "title") and (f := hit(w, title)):
            p = _pts(w, "title", d)
            add(w, "title", f, p)
            s += p
    if sc.get("title_minus_skips_detail", True) and any(h["kind"] == "minus" for h in hits):
        return _out(s, "title_minus", hits)
    if not has_detail:
        return _out(s, "pending", hits)
    for w in words:
        if w["kind"] == "veto" and where_ok(w, "body") and (f := hit(w, body)):
            add(w, "body", f, 0)
            return _out(0, "veto", hits)
    in_title = {h["word"] for h in hits}
    body_sum = 0
    for w in words:
        if w["kind"] in ("plus", "minus") and where_ok(w, "body") and label(w) not in in_title and (f := hit(w, body)):
            p = _pts(w, "body", d)
            add(w, "body", f, p)
            body_sum += p
    cap = sc["body_cap"]
    s += max(-cap, min(cap, body_sum))
    for w in words:
        if w["kind"] == "must" and not hit(w, title) and not hit(w, body):
            add(w, "missing", None, 0)
            return _out(0, "must_missing", hits)
    return _out(s, "detail", hits)


def _out(s, stage, hits):
    pick = lambda kind, where: [h["word"] for h in hits if h["kind"] == kind and h["where"] == where]  # noqa: E731
    return {"score": max(0, min(100, int(round(s)))), "stage": stage, "hits": hits,
            "tp": pick("plus", "title"), "tm": pick("minus", "title"), "bp": pick("plus", "body"), "bm": pick("minus", "body")}


def tier(s, cfg):
    t = (cfg["score"] if "score" in cfg else cfg)["tiers"]
    return "high" if s >= t["high"] else "mid" if s >= t["mid"] else "low" if s >= t["low"] else "bad"
