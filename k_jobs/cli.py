"""k-jobs 명령어.

  k-jobs init [--preset infra-junior|dev-junior|all]   설정 파일 만들기
  k-jobs collect [--only 사이트] [--no-detail]          목록 수집 + 상세 확인(+ AI 판단, 켰다면)
  k-jobs enrich [--budget 초]                          밀린 상세 확인만
  k-jobs ai [--limit N]                                AI 판단만(설정에서 켰을 때)
  k-jobs list [--min 점수] [--limit N]                  점수 순 목록
  k-jobs export --format csv|json|career-ops [-o 파일]  내보내기
  k-jobs serve [--port 8765]                           웹 화면(내 컴퓨터에서만)
  k-jobs suggest --resume 이력.txt                     이력 → 검색어·단어 초안(AI)
  k-jobs reclassify                                    직무 설정을 바꾼 뒤 저장된 공고 다시 분류
  k-jobs doctor                                        설치·설정·사이트 연결 점검
데이터 폴더: $KJOBS_HOME 또는 ~/.k-jobs (config.json, jobs.sqlite3)
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__, ai, collect, config, export, store, view
from .presets import PRESETS


def home():
    return Path(os.environ.get("KJOBS_HOME") or Path.home() / ".k-jobs").expanduser()


def paths():
    h = home()
    return h / "config.json", h / "jobs.sqlite3", h / "enrich.lock"


def _cfg():
    cfg_path, _, _ = paths()
    if not cfg_path.exists():
        sys.exit(f"설정 파일이 없습니다: {cfg_path}\n먼저 `k-jobs init`을 실행하세요.")
    return config.load(cfg_path)


def cmd_init(a):
    cfg_path, _, _ = paths()
    if cfg_path.exists() and not a.force:
        sys.exit(f"이미 있습니다: {cfg_path} (덮어쓰려면 --force)")
    config.save(cfg_path, config.load(preset=a.preset))
    print(f"설정을 만들었습니다: {cfg_path} (프리셋: {a.preset} — {PRESETS[a.preset]['label']})")
    print("다음: 설정을 고친 뒤 `k-jobs collect`, 화면은 `k-jobs serve`.")


def cmd_collect(a):
    cfg = _cfg()
    _, db, lock = paths()
    c = store.connect(db)
    collect.collect(c, cfg, only=a.only)
    if not a.no_detail:
        collect.enrich(c, cfg, lock, budget=a.budget)
        ai.run(c, cfg)


def cmd_enrich(a):
    cfg = _cfg()
    _, db, lock = paths()
    collect.enrich(store.connect(db), cfg, lock, budget=a.budget, limit=100000)


def cmd_ai(a):
    cfg = _cfg()
    if not cfg["ai"]["enabled"]:
        sys.exit("AI 판단이 꺼져 있습니다(config.json의 ai.enabled).")
    ai.run(store.connect(paths()[1]), cfg, limit=a.limit)


def _items(cfg, min_score=0, include_hold=True):
    return export.pick(view.items(store.connect(paths()[1]), cfg)["items"], min_score, include_hold)


def cmd_list(a):
    cfg = _cfg()
    for r in _items(cfg, a.min)[:a.limit]:
        mark = {"ok": " ", "hold": "?", "pending": "…"}.get(r["verdict"], " ")
        print(f"{r['score']:>3}{mark} [{config.SITE_KO[r['source']]}] {r['title'][:60]} · {r['company'][:20]} · {r['deadline'] or '-'}")
        w = export.why(r)
        if w:
            print(f"      {w[:140]}")
        print(f"      {r['url']}")


def cmd_export(a):
    cfg = _cfg()
    items = _items(cfg, a.min, include_hold=not a.no_hold)
    text = {"csv": export.to_csv, "json": export.to_json, "career-ops": export.to_career_ops}[a.format](items)
    if a.output:
        Path(a.output).write_text(text, encoding="utf-8")
        print(f"{len(items)}건 → {a.output}")
    else:
        sys.stdout.write(text)


def cmd_serve(a):
    from .web.server import serve
    _cfg()
    serve(paths(), a.host, a.port)


def cmd_suggest(a):
    cfg = _cfg()
    if not cfg["ai"]["model"]:
        sys.exit("ai.model과 API 키 환경변수를 먼저 설정하세요(ai.enabled는 꺼 둬도 됩니다).")
    print(json.dumps(ai.suggest(cfg, Path(a.resume).read_text(encoding="utf-8")), ensure_ascii=False, indent=1))
    print("\n위 초안을 검토해 config.json의 queries·score.words·conditions에 옮기세요.", file=sys.stderr)


def cmd_reclassify(a):
    keep, drop = collect.reclassify(store.connect(paths()[1]), _cfg())
    print(f"남김 {keep} · 지움 {drop}")


def cmd_doctor(a):
    ok = True

    def line(good, text):
        nonlocal ok
        ok &= good
        print(("✓ " if good else "✗ ") + text)
    cfg_path, db, _ = paths()
    line(sys.version_info >= (3, 10), f"Python {sys.version.split()[0]} (3.10 이상)")
    try:
        cfg = config.load(cfg_path) if cfg_path.exists() else None
        line(cfg is not None, f"설정 {cfg_path}" + ("" if cfg else " — `k-jobs init` 필요"))
    except ValueError as e:
        cfg = None
        line(False, f"설정 오류: {e}")
    line(shutil.which("curl") is not None, "curl(이미지 받기·프록시)")
    tess = shutil.which("tesseract")
    langs = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout if tess else ""
    line(bool(tess) and "kor" in langs, "tesseract + 한국어(kor) — 이미지 공고 글자 읽기" + ("" if tess else " (없으면 이미지 공고는 못 읽음)"))
    try:
        import PIL  # noqa: F401
        line(True, "Pillow")
    except ImportError:
        line(False, "Pillow 없음 — pip install 'k-jobs[ocr]'")
    if cfg and cfg["ai"]["enabled"]:
        line(bool(os.environ.get(cfg["ai"]["api_key_env"])) or "localhost" in cfg["ai"]["base_url"],
             f"AI 키 환경변수 {cfg['ai']['api_key_env']}")
    if cfg and a.network:
        from .http import Net
        net = Net(cfg)
        for site, url in (("wanted", "https://www.wanted.co.kr/robots.txt"), ("saramin", "https://www.saramin.co.kr/robots.txt"),
                          ("jobkorea", "https://www.jobkorea.co.kr/robots.txt"), ("remember", "https://career.rememberapp.co.kr/robots.txt")):
            if not cfg["sources"].get(site):
                continue
            try:
                net.get(url, site=site)
                line(True, f"{config.SITE_KO[site]} 연결")
            except Exception as e:  # noqa: BLE001
                line(False, f"{config.SITE_KO[site]} 연결 실패({type(e).__name__}) — 차단되면 network.proxy.{site}에 본인 프록시를 넣을 수 있습니다")
    print(f"데이터: {db}")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="k-jobs", description="한국 채용 사이트용 공고 적합도 필터")
    ap.add_argument("--version", action="version", version=f"k-jobs {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("--preset", choices=list(PRESETS), default="infra-junior")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_init)
    p = sub.add_parser("collect")
    p.add_argument("--only", choices=config.SITES)
    p.add_argument("--no-detail", action="store_true")
    p.add_argument("--budget", type=int)
    p.set_defaults(fn=cmd_collect)
    p = sub.add_parser("enrich")
    p.add_argument("--budget", type=int)
    p.set_defaults(fn=cmd_enrich)
    p = sub.add_parser("ai")
    p.add_argument("--limit", type=int)
    p.set_defaults(fn=cmd_ai)
    p = sub.add_parser("list")
    p.add_argument("--min", type=int, default=50)
    p.add_argument("--limit", type=int, default=30)
    p.set_defaults(fn=cmd_list)
    p = sub.add_parser("export")
    p.add_argument("--format", choices=["csv", "json", "career-ops"], default="csv")
    p.add_argument("--min", type=int, default=50)
    p.add_argument("--no-hold", action="store_true", help="보류(표기 없음 등) 공고 빼기")
    p.add_argument("-o", "--output")
    p.set_defaults(fn=cmd_export)
    p = sub.add_parser("serve")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.set_defaults(fn=cmd_serve)
    p = sub.add_parser("suggest")
    p.add_argument("--resume", required=True)
    p.set_defaults(fn=cmd_suggest)
    p = sub.add_parser("reclassify")
    p.set_defaults(fn=cmd_reclassify)
    p = sub.add_parser("doctor")
    p.add_argument("--network", action="store_true", help="사이트 연결도 확인")
    p.set_defaults(fn=cmd_doctor)
    a = ap.parse_args(argv)
    return a.fn(a) or 0


if __name__ == "__main__":
    raise SystemExit(main())
