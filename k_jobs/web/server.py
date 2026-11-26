"""내 컴퓨터에서만 여는 웹 화면(표준 라이브러리 http.server). 기본 주소 http://127.0.0.1:8765

GET  /api/jobs     공고 목록(점수는 지금 설정으로 계산)
GET  /api/config   설정 + 프리셋 목록
POST /api/config   설정 저장(전체 설정) 또는 {"reset": "프리셋 이름"}
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .. import config, store, view
from ..presets import PRESETS

STATIC = Path(__file__).parent / "static"
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}


def make_handler(paths):
    cfg_path, db_path, _ = paths

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            p = urlparse(self.path).path
            if p == "/api/jobs":
                return self._send(200, view.items(store.connect(db_path), config.load(cfg_path)))
            if p == "/api/config":
                return self._send(200, {"cfg": config.load(cfg_path), "presets": {k: v["label"] for k, v in PRESETS.items()},
                                        "levels": config.EDU_LEVELS, "sites": config.SITE_KO})
            name = "index.html" if p in ("/", "/index.html") else p.lstrip("/")
            f = (STATIC / name).resolve()
            if STATIC.resolve() in f.parents and f.is_file():
                return self._send(200, f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream"))
            return self._send(404, {"error": "없음"})

        def do_POST(self):
            # 다른 사이트에서 이 화면으로 요청을 보내지 못하게(같은 주소에서 온 요청만)
            origin = self.headers.get("Origin", "")
            if origin and urlparse(origin).netloc != self.headers.get("Host", ""):
                return self._send(403, {"error": "다른 출처의 요청은 받지 않습니다"})
            if urlparse(self.path).path != "/api/config":
                return self._send(404, {"error": "없음"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                data = json.loads(self.rfile.read(min(n, 2_000_000)) or b"{}")
                if data.get("reset"):
                    if data["reset"] not in PRESETS:
                        raise ValueError("모르는 프리셋")
                    cfg = config.load(preset=data["reset"])
                else:
                    cfg = config.load(cfg_path)
                    config._merge(cfg, data)
                    cfg = config.clean(cfg)
                config.save(cfg_path, cfg)
                return self._send(200, {"cfg": cfg})
            except (ValueError, TypeError, KeyError) as e:
                return self._send(400, {"error": str(e)})

    return H


def serve(paths, host="127.0.0.1", port=8765):
    srv = ThreadingHTTPServer((host, port), make_handler(paths))
    print(f"k-jobs 화면: http://{host}:{port}  (끝내려면 Ctrl+C)")
    if host not in ("127.0.0.1", "localhost", "::1"):
        print("주의: 로그인 없는 화면입니다. 다른 사람이 접속할 수 있는 주소로 열지 마세요.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
