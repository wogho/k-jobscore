"""화면·내보내기용 공고 목록. 점수는 여기서 지금 설정으로 계산한다(설정을 바꾸면 바로 반영).

본문·이미지 글자는 점수 계산에만 쓰고 내보내지 않는다 — 화면에는 제목·회사·조건·점수·근거와 원문 링크만.
"""
import json
from datetime import datetime, timedelta

from . import score as sc
from .config import SITE_KO
from .filters import judge


def items(c, cfg, now=None):
    now = now or datetime.now()
    today = now.strftime("%Y-%m-%d")
    since = (now - timedelta(days=cfg["conditions"]["open_days"])).isoformat(timespec="seconds")
    c.row_factory = None
    cols = ["source", "sid", "url", "title", "company", "location", "career", "career_min", "edu", "emp_type", "deadline", "first_seen", "last_seen", "cats",
            "d_at", "d_body", "d_ocr", "d_images", "career_v", "edu_v", "v_note", "d_error", "ai_fit", "ai_result", "ai_model"]
    # 읽기 전용으로 연 예전 DB에는 details·ai 표가 없을 수 있다 — 없으면 빈 값으로
    have = {r[0] for r in c.execute("select name from sqlite_master where type='table'")}
    d_cols = ("d.fetched_at, coalesce(d.body,''), coalesce(d.ocr,''), coalesce(d.images,0), coalesce(d.career_v,''), coalesce(d.edu_v,''), "
              "coalesce(d.note,''), coalesce(d.error,'')") if "details" in have else "null, '', '', 0, '', '', '', ''"
    a_cols = "a.fit, a.result, a.model" if "ai" in have else "null, null, null"
    joins = (" left join details d on d.source = p.source and d.sid = p.sid" if "details" in have else "") + \
            (" left join ai a on a.source = p.source and a.sid = p.sid and a.error = ''" if "ai" in have else "")
    rows = c.execute(
        "select p.source, p.sid, p.url, p.title, p.company, p.location, p.career, p.career_min, p.edu, p.emp_type, p.deadline, p.first_seen, p.last_seen, "
        f"coalesce(p.cats,''), {d_cols}, {a_cols} from postings p{joins} "
        "where (p.deadline glob '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' and p.deadline >= ?) "
        "or (p.deadline not glob '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' and p.first_seen >= ?) order by p.first_seen desc", (today, since)).fetchall()
    out, checked = [], 0
    w = cfg["ai"]["weight"] if cfg["ai"]["enabled"] else 0
    for row in rows:
        r = dict(zip(cols, row))
        body = r.pop("d_body") + "\n" + r.pop("d_ocr")
        d_at, d_err = r.pop("d_at"), r.pop("d_error")
        has = bool(d_at) and not d_err
        checked += has
        r.update(sc.score(r["title"], body, cfg, has))
        r["rule_score"] = r["score"]
        ai_fit, ai_res = r.pop("ai_fit"), r.pop("ai_result")
        r["ai"] = None
        if ai_fit is not None and ai_res:
            try:
                r["ai"] = {**json.loads(ai_res), "model": r.get("ai_model")}
            except ValueError:
                r["ai"] = None
            if w and r["stage"] == "detail":
                r["score"] = int(round(r["rule_score"] * (1 - w) + ai_fit * w))
        r.pop("ai_model", None)
        r["verdict"] = judge(r["career_v"], r["edu_v"], r["v_note"], cfg) if has else "pending"
        r["tier"] = sc.tier(r["score"], cfg)
        r["cats"] = [x for x in r["cats"].split(",") if x]
        out.append(r)
    runs = [dict(zip(("at", "source", "fetched", "kept", "new", "error"), x)) for x in c.execute(
        "select r.* from runs r join (select source, max(at) at from runs group by source) m on r.source = m.source and r.at = m.at")] if "runs" in have else []
    return {"items": out, "runs": runs, "sites": SITE_KO, "checked": checked,
            "roles": {r["id"]: r["label"] for r in cfg["roles"]} or {"all": "전체"}}
