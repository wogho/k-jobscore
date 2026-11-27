"""HTTP 가져오기. 프록시는 사용자가 설정한 사이트에만 쓴다(기본 없음).

network.proxy.<사이트>는 주소 하나 또는 여러 개(목록, 또는 쉼표로 구분)다. 여러 개면 앞에서부터 쓰고,
프록시 연결이 안 되면(연결 실패·시간 초과) 다음 주소로 넘어간다. 한 번 된 주소는 그 회차 동안 먼저 쓴다.
"""
import subprocess
import urllib.request

ROUTE_FAIL = {5, 7, 28, 97}   # 프록시 이름 못 찾음 · 연결 실패 · 시간 초과 · SOCKS 연결 실패 → 다음 프록시로

DEFAULT_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"


class Net:
    def __init__(self, cfg):
        n = cfg["network"]
        self.ua = n.get("user_agent") or DEFAULT_UA
        self.timeout = n.get("timeout", 30)
        self.delay = n.get("delay_sec", 3)
        self.proxy = n.get("proxy") or {}
        self.first = {}   # 사이트 → 이번 회차에 된 프록시

    def proxies(self, site):
        v = self.proxy.get(site or "", "")
        xs = [x.strip() for x in (v if isinstance(v, list) else str(v or "").split(",")) if x and x.strip()]
        f = self.first.get(site)
        return ([f] + [x for x in xs if x != f]) if f in xs else xs

    def _via(self, site, fn):
        """프록시를 차례로 — 연결이 안 되는 것만 건너뛴다(사이트의 HTTP 오류는 그대로 올린다)."""
        err = None
        for px in self.proxies(site):
            try:
                out = fn(px)
                self.first[site] = px
                return out
            except RuntimeError as e:
                if getattr(e, "code", None) not in ROUTE_FAIL:
                    raise
                err = e
        raise err

    def get(self, url, site=None, data=None, headers=None):
        if self.proxies(site):
            return self._via(site, lambda px: self._curl(url, px, data, headers))
        req = urllib.request.Request(url, data=data.encode() if isinstance(data, str) else data,
                                     headers={"User-Agent": self.ua, "Accept-Language": "ko-KR,ko;q=0.9", **(headers or {})})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return r.read().decode("utf-8", "replace")

    def _curl(self, url, proxy, data, headers):
        """프록시(socks5h://, http://)는 curl로 — 표준 라이브러리만으로는 SOCKS를 못 쓴다."""
        cmd = ["curl", "-sS", "--fail", "--max-time", str(self.timeout), "--connect-timeout", "10", "--proxy", proxy, "-A", self.ua, "-H", "Accept-Language: ko-KR,ko;q=0.9"]
        for k, v in (headers or {}).items():
            cmd += ["-H", f"{k}: {v}"]
        if data is not None:
            cmd += ["-X", "POST", "--data-binary", data]
        r = subprocess.run(cmd + ["-w", "\n%{http_code}", url], capture_output=True, timeout=self.timeout + 10)
        if r.returncode:
            # 22 = HTTP 오류 응답(차단·한도), 7·97 = 프록시 연결 실패, 28 = 시간 초과 — 원인을 알 수 있게 코드를 함께
            why = {22: "HTTP 오류 응답(차단·요청 한도 가능)", 7: "프록시 연결 실패", 97: "프록시 연결 실패", 28: "시간 초과", 35: "TLS 연결 실패"}.get(r.returncode, "")
            e = RuntimeError(f"curl exit {r.returncode}" + (f" {why}" if why else "") + (f" · {r.stderr.decode(errors='replace').strip()[:80]}" if r.stderr else ""))
            e.code = r.returncode
            raise e
        body, _, code = r.stdout.decode("utf-8", "replace").rpartition("\n")
        return body

    def download(self, url, dest, referer, site=None, max_bytes=15_000_000):
        cmd = ["curl", "-s", "-L", "--fail", "--max-time", "40", "--max-filesize", str(max_bytes), "-A", self.ua, "-e", referer, "-o", str(dest), url]
        if not self.proxies(site):
            subprocess.run(cmd, timeout=60, check=True)
            return

        def one(px):
            r = subprocess.run(cmd[:1] + ["--connect-timeout", "10", "--proxy", px] + cmd[1:], timeout=60)
            if r.returncode:
                e = RuntimeError(f"curl exit {r.returncode}")
                e.code = r.returncode
                raise e
        self._via(site, one)
