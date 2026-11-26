"""수집기 공용 도구."""
import html as htmllib
import re


class Ctx:
    """수집 한 회차의 공용 상태 — 설정, 네트워크, 이미 본 공고(멈춤 판단)."""
    STOP_RATIO = 0.8

    def __init__(self, cfg, net, seen=None):
        self.cfg, self.net, self.seen = cfg, net, set(seen or ())

    def seen_enough(self, source, ids):
        """한 쪽의 공고 80% 이상이 이미 본 것이면 그 검색어는 그만 읽는다(최신 순이므로)."""
        ids = [str(x) for x in ids]
        return bool(ids) and sum((source, x) in self.seen for x in ids) / len(ids) >= self.STOP_RATIO


def html_text(h):
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", h or "", flags=re.S | re.I)
    h = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</tr>|</h\d>", "\n", h, flags=re.I)
    t = htmllib.unescape(re.sub(r"<[^>]+>", " ", h))
    return "\n".join(re.sub(r"[ \t ]+", " ", line).strip() for line in t.splitlines() if line.strip())


def html_images(h, base):
    out = []
    for src in re.findall(r"<img[^>]+src=[\"']([^\"']+)", h or "", flags=re.I):
        src = htmllib.unescape(src.strip())
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = base + src
        if src.startswith("http") and src not in out:
            out.append(src)
    return out
