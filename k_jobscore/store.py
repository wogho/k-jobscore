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


def save_postings(c, rows, now):
    new = 0
    for p in rows:
        cats = ",".join(p.get("cats") or [])
        if c.execute("select 1 from postings where source=? and sid=?", (p["source"], p["sid"])).fetchone():
            c.execute("update postings set title=?, company=?, location=?, career=?, career_min=?, edu=?, emp_type=?, deadline=?, last_seen=?, cats=? "
                      "where source=? and sid=?", (p["title"], p["company"], p["location"], p["career"], p["career_min"], p["edu"], p["emp_type"],
                                                    p["deadline"], now, cats, p["source"], p["sid"]))
        else:
            c.execute("insert into postings(source, sid, url, title, company, location, career, career_min, edu, emp_type, deadline, first_seen, last_seen, cats) "
                      "values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (p["source"], p["sid"], p["url"], p["title"], p["company"], p["location"], p["career"],
                                                               p["career_min"], p["edu"], p["emp_type"], p["deadline"], now, now, cats))
            new += 1
    return new
