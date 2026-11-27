"""HTTP 가져오기. 프록시는 사용자가 설정한 사이트에만 쓴다(기본 없음)."""
import subprocess
import urllib.request

DEFAULT_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"


class Net:
    def __init__(self, cfg):
        n = cfg["network"]
        self.ua = n.get("user_agent") or DEFAULT_UA
        self.timeout = n.get("timeout", 30)
        self.delay = n.get("delay_sec", 3)
        self.proxy = n.get("proxy") or {}

    def get(self, url, site=None, data=None, headers=None):
        proxy = self.proxy.get(site or "", "")
        if proxy:
            return self._curl(url, proxy, data, headers)
        req = urllib.request.Request(url, data=data.encode() if isinstance(data, str) else data,
                                     headers={"User-Agent": self.ua, "Accept-Language": "ko-KR,ko;q=0.9", **(headers or {})})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return r.read().decode("utf-8", "replace")

    def _curl(self, url, proxy, data, headers):
        """프록시(socks5h://, http://)는 curl로 — 표준 라이브러리만으로는 SOCKS를 못 쓴다."""
        cmd = ["curl", "-sS", "--fail", "--max-time", str(self.timeout), "--proxy", proxy, "-A", self.ua, "-H", "Accept-Language: ko-KR,ko;q=0.9"]
        for k, v in (headers or {}).items():
            cmd += ["-H", f"{k}: {v}"]
        if data is not None:
            cmd += ["-X", "POST", "--data-binary", data]
        r = subprocess.run(cmd + ["-w", "\n%{http_code}", url], capture_output=True, timeout=self.timeout + 10)
        if r.returncode:
            # 22 = HTTP 오류 응답(차단·한도), 7·97 = 프록시 연결 실패, 28 = 시간 초과 — 원인을 알 수 있게 코드를 함께
            why = {22: "HTTP 오류 응답(차단·요청 한도 가능)", 7: "프록시 연결 실패", 97: "프록시 연결 실패", 28: "시간 초과", 35: "TLS 연결 실패"}.get(r.returncode, "")
            raise RuntimeError(f"curl exit {r.returncode}" + (f" {why}" if why else "") + (f" · {r.stderr.decode(errors='replace').strip()[:80]}" if r.stderr else ""))
        body, _, code = r.stdout.decode("utf-8", "replace").rpartition("\n")
        return body

    def download(self, url, dest, referer, site=None, max_bytes=15_000_000):
        cmd = ["curl", "-s", "-L", "--fail", "--max-time", "40", "--max-filesize", str(max_bytes), "-A", self.ua, "-e", referer, "-o", str(dest), url]
        proxy = self.proxy.get(site or "", "")
        if proxy:
            cmd[1:1] = ["--proxy", proxy]
        subprocess.run(cmd, timeout=60, check=True)
