"""설정 파일(config.json) 읽기·검사·저장.

설정은 하나의 JSON 파일이다. 빠진 항목은 기본값으로 채우고, 틀린 값은 ValueError로 알려 준다.
예전 평면 형식({"base", "title_plus", "plus": [...], "minus": [...]})도 읽어 새 형식으로 바꾼다.
"""
import copy
import json
import os
from pathlib import Path

from .presets import PRESETS

EDU_LEVELS = ["무관", "고졸", "초대졸", "대졸", "석사", "박사"]
SITES = ["wanted", "saramin", "jobkorea", "remember"]
SITE_KO = {"wanted": "원티드", "saramin": "사람인", "jobkorea": "잡코리아", "remember": "리멤버"}
KINDS = ["plus", "minus", "veto", "must"]
WHERE = ["both", "title", "body"]
MATCH = ["auto", "contains", "word", "regex"]
HANDLING = ["keep", "hold", "drop"]   # 판단할 수 없을 때: 통과 / 보류(남기고 표시) / 제외


def _base(preset="infra-junior"):
    p = PRESETS[preset]
    return {
        "version": 2,
        "preset": preset,
        "sources": {s: True for s in SITES},
        "queries": list(p["queries"]),
        "wanted_tag_ids": list(p["wanted_tag_ids"]),
        "wanted_queries": list(p["wanted_queries"]),
        "pages": 2,                        # 검색어 하나당 최대 쪽 수(최신 순, 이미 본 공고가 80% 넘으면 멈춤)
        "network": {"delay_sec": 3, "timeout": 30, "user_agent": "", "proxy": {s: "" for s in SITES}},
        "roles": copy.deepcopy(p["roles"]),
        "conditions": {
            "career": {"max_required_years": 2, "include_intern": True, "unlabeled": "keep"},
            "education": {"my_level": p["my_level"], "unlabeled": "keep", "equivalent_ok": True, "major_required": "keep"},
            "employment_exclude": ["파견"],
            "regions": [],
            "companies_exclude": [],
            "companies_only": [],
            "open_days": 30,               # 마감일이 없는(상시·채용시) 공고를 처음 본 뒤 며칠까지 보여 줄지
        },
        "score": {
            "base": 50,
            "defaults": {"plus_title": 15, "plus_body": 5, "minus_title": -30, "minus_body": -5},
            "body_cap": 30,                # 상세 점수 합의 상한(±)
            "title_minus_skips_detail": True,
            "tiers": {"high": 70, "mid": 50, "low": 30},
            "words": [{"word": w, "kind": "plus"} for w in p["plus"]] + [{"word": w, "kind": "minus"} for w in p["minus"]],
        },
        "detail": {"enabled": True, "ocr": "tesseract", "ocr_langs": "kor+eng", "images_max": 4, "img_min_w": 300, "img_min_h": 200,
                   "ocr_timeout": 240, "budget_sec": 1500, "retry_failed_after_h": 6},
        "ai": {
            "enabled": False,
            "provider": "openai",          # openai(OpenAI 호환: OpenAI·Ollama·OpenRouter·Gemini 호환 주소) / anthropic / cli(설치된 AI 명령어)
            "cli": "auto",                 # provider cli: auto(찾은 것 중 첫째) / claude / codex / gemini
            "cli_command": [],             # provider cli: 직접 지정한 명령(프롬프트는 마지막 인자로 붙음). 비우면 cli 값으로
            "cli_timeout": 300,
            "base_url": "https://api.openai.com/v1",
            "model": "",
            "api_key_env": "KJOBS_AI_KEY",  # 키는 설정 파일이 아니라 환경변수에서만 읽는다
            "weight": 0.3,                 # 최종 점수 = 규칙 점수 × (1-w) + AI 점수 × w
            "min_rule_score": 50,          # 이 점수 이상인 공고만 AI에 보낸다(비용 제어)
            "max_per_run": 20,
            "profile_file": "",            # 내 이력 요약 파일(개인정보는 빼고). 비우면 조건·단어만으로 판단
            "rubric": "",                  # 추가 판단 기준(자유 문장)
            "temperature": 0,
        },
    }


DEFAULT = _base()

LIMITS = {("score", "base"): (0, 100), ("score", "body_cap"): (0, 100),
          ("score", "defaults", "plus_title"): (0, 100), ("score", "defaults", "plus_body"): (0, 50),
          ("score", "defaults", "minus_title"): (-100, 0), ("score", "defaults", "minus_body"): (-50, 0),
          ("conditions", "career", "max_required_years"): (0, 30), ("conditions", "open_days"): (1, 365),
          ("pages",): (1, 20), ("network", "delay_sec"): (1, 60), ("detail", "images_max"): (0, 12),
          ("ai", "weight"): (0, 1), ("ai", "min_rule_score"): (0, 100), ("ai", "max_per_run"): (0, 500), ("ai", "cli_timeout"): (30, 1800)}


def _merge(base, over):
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def from_legacy(old):
    """예전 평면 형식 → 새 형식의 score 부분."""
    sc = {"base": old.get("base", 50), "body_cap": old.get("body_cap", 30),
          "defaults": {"plus_title": old.get("title_plus", 15), "plus_body": old.get("body_plus", 5),
                       "minus_title": old.get("title_minus", -30), "minus_body": old.get("body_minus", -5)}}
    if "plus" in old or "minus" in old:
        sc["words"] = [{"word": w, "kind": "plus"} for w in old.get("plus", [])] + [{"word": w, "kind": "minus"} for w in old.get("minus", [])]
    return {"score": sc}


def load(path=None, preset=None):
    cfg = _base(preset) if preset else copy.deepcopy(DEFAULT)
    if path:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        if isinstance(data, dict):
            if "version" not in data and ("title_plus" in data or "plus" in data):
                data = from_legacy(data)
            if data.get("preset") in PRESETS and data.get("preset") != cfg["preset"]:
                cfg = _base(data["preset"])
            _merge(cfg, data)
    return clean(cfg)


def _get(d, keys):
    for k in keys:
        d = d[k]
    return d


def _set(d, keys, v):
    for k in keys[:-1]:
        d = d[k]
    d[keys[-1]] = v


def _word(w):
    """단어 항목 하나 정리: 문자열 또는 {"word": str|[동의어...], "kind", "title", "body", "where", "match"}."""
    if isinstance(w, (str, list)):
        w = {"word": w}
    if not isinstance(w, dict):
        raise ValueError("단어 항목 형식이 틀렸습니다")
    word = w.get("word")
    variants = [str(x).strip() for x in (word if isinstance(word, list) else [word]) if str(x or "").strip()]
    if not variants or any(len(v) > 60 for v in variants):
        raise ValueError(f"단어가 비었거나 너무 깁니다: {word!r}")
    out = {"word": variants if len(variants) > 1 else variants[0], "kind": w.get("kind", "plus")}
    if out["kind"] not in KINDS:
        raise ValueError(f"kind는 {KINDS} 중 하나: {out['kind']}")
    for k, lo, hi in (("title", -100, 100), ("body", -50, 50)):
        if w.get(k) is not None and w.get(k) != "":
            v = int(w[k])
            if not lo <= v <= hi:
                raise ValueError(f"{variants[0]}의 {k} 점수는 {lo}~{hi}")
            out[k] = v
    for k, allowed in (("where", WHERE), ("match", MATCH)):
        if w.get(k):
            if w[k] not in allowed:
                raise ValueError(f"{k}는 {allowed} 중 하나")
            out[k] = w[k]
    if out.get("match") == "regex":
        import re
        for v in variants:
            re.compile(v)
    return out


def clean(cfg):
    """설정 검사 — 숫자 범위, 선택지, 단어 목록(중복 제거, 최대 200개)."""
    for keys, (lo, hi) in LIMITS.items():
        v = _get(cfg, keys)
        v = float(v) if keys == ("ai", "weight") else int(v)
        if not lo <= v <= hi:
            raise ValueError(f"{'.'.join(keys)}는 {lo}~{hi} 사이여야 합니다")
        _set(cfg, keys, v)
    c = cfg["conditions"]
    if c["education"]["my_level"] not in EDU_LEVELS:
        raise ValueError(f"education.my_level은 {EDU_LEVELS} 중 하나")
    for k in ("unlabeled", "major_required"):
        if c["education"][k] not in HANDLING:
            raise ValueError(f"education.{k}는 {HANDLING} 중 하나")
    if c["career"]["unlabeled"] not in HANDLING:
        raise ValueError(f"career.unlabeled는 {HANDLING} 중 하나")
    for s in list(cfg["sources"]):
        if s not in SITES:
            raise ValueError(f"모르는 사이트: {s}")
    words, seen = [], set()
    for w in cfg["score"]["words"]:
        w = _word(w)
        key = (str(w["word"]).lower(), w["kind"])
        if key not in seen:
            seen.add(key)
            words.append(w)
    if len(words) > 200:
        raise ValueError("단어는 200개까지입니다")
    cfg["score"]["words"] = words
    if cfg["ai"]["provider"] not in ("openai", "anthropic", "cli"):
        raise ValueError("ai.provider는 openai · anthropic · cli 중 하나")
    if cfg["ai"]["cli"] not in ("auto", "claude", "codex", "gemini"):
        raise ValueError("ai.cli는 auto · claude · codex · gemini 중 하나")
    if not isinstance(cfg["ai"]["cli_command"], list) or not all(isinstance(x, str) for x in cfg["ai"]["cli_command"]):
        raise ValueError("ai.cli_command는 문자열 목록")
    return cfg


def save(path, cfg):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(clean(cfg), ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)
