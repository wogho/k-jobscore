"""수집 한 회차: 목록 모으기 → 조건 거르기 → 저장 → 상세 확인(본문 + 이미지 글자, 경력·학력 판정)."""
import tempfile
import time
from datetime import datetime
from pathlib import Path

from . import ocr, score, store, verify
from .config import SITE_KO
from .filters import categorize, passes
from .http import Net
from .sources import SOURCES, Ctx


def reclassify(c, cfg):
    """직무 설정이 바뀌면 저장된 공고를 다시 분류 — 맞는 직무가 없으면 지운다 → (남김, 지움)."""
    keep = drop = 0
    for source, sid, title, company in c.execute("select source, sid, title, company from postings").fetchall():
        cats = categorize(title, company, cfg["roles"])
        if cats:
            c.execute("update postings set cats=? where source=? and sid=?", (",".join(cats), source, sid))
            keep += 1
        else:
            c.execute("delete from postings where source=? and sid=?", (source, sid))
            drop += 1
    c.commit()
    return keep, drop


def collect(c, cfg, only=None, log=print):
    now = datetime.now().isoformat(timespec="seconds")
    net = Net(cfg)
    seen = set(c.execute("select source, sid from postings").fetchall()) | set(c.execute("select source, sid from seen").fetchall())
    ctx = Ctx(cfg, net, seen)
    summary = []
    for name, mod in SOURCES.items():
        if not cfg["sources"].get(name) or (only and only != name):
            continue
        try:
            rows, ids, errs = [], set(), []
            for q in mod.queries(cfg):
                try:
                    got = mod.search(ctx, q, cfg["pages"])
                except Exception as e:  # noqa: BLE001 — 검색어 하나 실패는 건너뜀
                    errs.append(f"{type(e).__name__}: {e}"[:160])
                    log(f"  {SITE_KO[name]} '{q}' 실패: {errs[-1]}")
                    continue
                for p in got:
                    if p["sid"] not in ids:
                        ids.add(p["sid"])
                        rows.append(p)
                time.sleep(net.delay)
            c.executemany("insert or ignore into seen values(?,?,?)", [(p["source"], p["sid"], now) for p in rows])
            kept = [p for p in rows if passes(p, cfg)]
            new = store.save_postings(c, kept, now)
            # 검색어가 모두 실패해 하나도 못 읽었으면 그 사이트 회차를 실패로 남긴다(화면의 '마지막 수집'에 이유가 보이게)
            err = f"모든 검색어 실패({len(errs)}개) — {errs[0]}" if errs and not rows else ""
            c.execute("insert into runs values(?,?,?,?,?,?)", (now, name, len(rows), len(kept), new, err[:300]))
            summary.append((name, len(rows), len(kept), new))
            log(f"{SITE_KO[name]}: 읽음 {len(rows)} · 조건 통과 {len(kept)} · 새 공고 {new}")
        except Exception as e:  # noqa: BLE001 — 한 사이트가 막혀도 나머지는 계속
            c.execute("insert into runs values(?,?,?,?,?,?)", (now, name, 0, 0, 0, f"{type(e).__name__}: {e}"[:300]))
            log(f"{SITE_KO[name]}: 실패 {type(e).__name__}: {e}")
        c.commit()
    return summary


def reverify(c, cfg):
    """저장된 상세 글로 경력·학력 판정을 지금 규칙·설정으로 다시 → 바뀐 건수."""
    n = 0
    for source, sid, body, text, cv0, ev0, note0, career, edu in c.execute(
            "select d.source, d.sid, d.body, d.ocr, d.career_v, d.edu_v, d.note, p.career, p.edu "
            "from details d join postings p using(source, sid) where d.error = ''").fetchall():
        cv, ev, note = verify.verify((body or "") + "\n" + (text or ""), career, edu, cfg["conditions"])
        if (cv, ev, note) != (cv0, ev0, note0):
            c.execute("update details set career_v=?, edu_v=?, note=? where source=? and sid=?", (cv, ev, note, source, sid))
            n += 1
    c.commit()
    return n


class _Lock:
    """상세 확인은 한 번에 하나만(정기 수집과 수동 실행이 같은 이미지를 동시에 읽지 않게)."""

    def __init__(self, path):
        self.f = open(path, "w")

    def acquire(self):
        try:
            import fcntl
        except ImportError:   # Windows — 잠금 없이 진행
            return True
        try:
            fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False


def enrich(c, cfg, lock_path, budget=None, limit=400, log=print):
    """상세 확인 안 한 공고(제목 감점·즉시 제외 공고는 빼고) 최신 순으로 → details 표. 실패한 것은 retry_failed_after_h 뒤 다시."""
    dcfg = cfg["detail"]
    if not dcfg["enabled"]:
        return 0
    lock = _Lock(lock_path)
    if not lock.acquire():
        log("상세 확인: 다른 회차가 진행 중이라 이번엔 건너뜀")
        return 0
    changed = reverify(c, cfg)
    if changed:
        log(f"경력·학력 판정 다시 계산: {changed}건 바뀜")
    budget = budget or dcfg["budget_sec"]
    rows = c.execute(f"""select p.source, p.sid, p.url, p.title, p.career, p.edu from postings p left join details d on d.source = p.source and d.sid = p.sid
                        where d.sid is null or (d.error != '' and d.fetched_at < datetime('now', 'localtime', '-{int(dcfg["retry_failed_after_h"])} hours'))
                        order by p.first_seen desc""").fetchall()
    rows = [r for r in rows if score.score(r[3], "", cfg, False)["stage"] == "pending"][:limit]   # 제목 감점·즉시 제외는 상세를 보지 않음
    net = Net(cfg)
    ctx = Ctx(cfg, net)
    t0, done, imgs = time.time(), 0, 0
    for source, sid, url, title, career, edu in rows:
        if time.time() - t0 > budget:
            break
        now = datetime.now().isoformat(timespec="seconds")
        try:
            body, urls, edu_hint = SOURCES[source].detail(ctx, sid)
            with tempfile.TemporaryDirectory() as td:
                text, n = ocr.read_images(urls, url, Path(td), net, dcfg, site=source, log=log)
            cv, ev, note = verify.verify(body + "\n" + text, career, edu_hint or edu, cfg["conditions"])
            c.execute("insert or replace into details values(?,?,?,?,?,?,?,?,?,?)", (source, sid, now, body[:60000], text[:60000], n, cv, ev, note, ""))
            done, imgs = done + 1, imgs + n
        except Exception as e:  # noqa: BLE001
            c.execute("insert or replace into details values(?,?,?,?,?,?,?,?,?,?)", (source, sid, now, "", "", 0, "", "", "", f"{type(e).__name__}: {e}"[:300]))
        c.commit()
        time.sleep(min(2, net.delay))
    log(f"상세 확인: {done}건(이미지 {imgs}장 글자 읽음) · 남은 {max(0, len(rows) - done)}건 · {int(time.time() - t0)}초")
    return done
