"""SQLite 저장소. 공고·상세·수집 기록·AI 판정을 사용자 컴퓨터에만 둔다(다시 배포하지 않는다)."""
import sqlite3
from pathlib import Path

SCHEMA = [
    """create table if not exists postings(source text, sid text, url text, title text, company text, location text, career text,
       career_min integer, edu text, emp_type text, deadline text, first_seen text, last_seen text, cats text default '', primary key(source, sid))""",
    "create table if not exists runs(at text, source text, fetched integer, kept integer, new integer, error text)",
    # 조건에 안 맞아 저장하지 않은 공고도 '봤음'으로 — 멈춤 판단(80%)이 거르는 비율에 흔들리지 않게
    "create table if not exists seen(source text, sid text, at text, primary key(source, sid))",
    """create table if not exists details(source text, sid text, fetched_at text, body text, ocr text, images integer,
       career_v text, edu_v text, note text, error text, primary key(source, sid))""",
    # 회사 기업형태 — 사람인·잡코리아 기업형태 필터 목록에서 본 회사(사이트 분류 그대로, 11-28)
    "create table if not exists company_types(ckey text, kind text, site text, at text, primary key(ckey, kind))",
    # 이미지 글자 읽기 결과 — 이미지 내용(sha1)·언어가 같으면 다시 읽지 않는다(dedup)
    "create table if not exists ocr_cache(hash text, langs text, text text, at text, primary key(hash, langs))",
    """create table if not exists ai(source text, sid text, key text, at text, model text, fit integer, result text, error text,
       primary key(source, sid))""",
]


def connect(path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(p, timeout=10)
    for s in SCHEMA:
        c.execute(s)
    if "cats" not in [r[1] for r in c.execute("pragma table_info(postings)")]:
        c.execute("alter table postings add column cats text default ''")
    c.commit()
    return c


class OcrCache:
    def __init__(self, c):
        self.c, self.hits = c, 0

    def get(self, h, langs):
        r = self.c.execute("select text from ocr_cache where hash=? and langs=?", (h, langs)).fetchone()
        if r:
            self.hits += 1
        return r[0] if r else None

    def put(self, h, langs, text):
        self.c.execute("insert or replace into ocr_cache values(?,?,?,datetime('now','localtime'))", (h, langs, text))


def learn_types(c, rows, kind, site, now):
    from .dedup import company_key
    for p in rows:
        ck = company_key(p.get("company"))
        if ck:
            c.execute("insert or replace into company_types values(?,?,?,?)", (ck, kind, site, now))


def load_types(c):
    """→ {회사 키: {종류…}} — filters.LEARNED에 넣어 기업 규모·공채 판단에 쓴다."""
    out = {}
    try:
        for ck, kind in c.execute("select ckey, kind from company_types"):
            out.setdefault(ck, set()).add(kind)
    except Exception:  # noqa: BLE001 — 읽기 전용 예전 DB
        pass
    return out


def save_postings(c, rows, now):
    new = 0
    for p in rows:
        cats = ",".join(p.get("cats") or [])
        old = c.execute("select cats from postings where source=? and sid=?", (p["source"], p["sid"])).fetchone()
        if old and cats == "_open" and old[0]:
            cats = old[0]   # 공채형: 상세 모집 부문에서 이미 정한 직무를 목록 회차가 '확인 중'으로 되돌리지 않게
        if old:
            c.execute("update postings set title=?, company=?, location=?, career=?, career_min=?, edu=?, emp_type=?, deadline=?, last_seen=?, cats=? "
                      "where source=? and sid=?", (p["title"], p["company"], p["location"], p["career"], p["career_min"], p["edu"], p["emp_type"],
                                                    p["deadline"], now, cats, p["source"], p["sid"]))
        else:
            c.execute("insert into postings(source, sid, url, title, company, location, career, career_min, edu, emp_type, deadline, first_seen, last_seen, cats) "
                      "values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (p["source"], p["sid"], p["url"], p["title"], p["company"], p["location"], p["career"],
                                                               p["career_min"], p["edu"], p["emp_type"], p["deadline"], now, now, cats))
            new += 1
    return new
