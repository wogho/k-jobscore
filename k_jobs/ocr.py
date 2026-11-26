"""이미지 공고 글자 읽기. 국내 공고는 본문이 통이미지인 경우가 많아, 이걸 읽어야 학력·경력을 제대로 판정한다.

엔진: tesseract(기본, `tesseract-ocr-kor` 필요) / none. 로고·아이콘 같은 작은 이미지는 건너뛰고 큰 것부터 읽는다.
tesseract 자동 반전은 켜 둔다 — 끄면 빠르지만 어두운 바탕의 흰 글씨를 영문 잡음으로 읽는다.
"""
import os
import re
import shutil
import subprocess


def available(engine):
    return engine == "tesseract" and shutil.which("tesseract") is not None


def read_images(urls, referer, tmpdir, net, dcfg, site=None, log=print):
    """→ (글, 읽은 장수)."""
    if not urls or dcfg.get("ocr", "tesseract") == "none" or not available(dcfg.get("ocr", "tesseract")):
        return "", 0
    try:
        from PIL import Image
    except ImportError:
        log("  OCR 건너뜀: Pillow가 없습니다(pip install 'k-jobs[ocr]')")
        return "", 0
    got = []
    for i, u in enumerate(urls[:12]):
        f = tmpdir / f"img{i}"
        try:
            net.download(u, f, referer, site=site)
            im = Image.open(f)
            w, h = im.size
            if w >= dcfg["img_min_w"] and h >= dcfg["img_min_h"]:
                g = tmpdir / f"g{i}.png"
                im.convert("L").save(g)
                got.append((w * h, g))
        except Exception:  # noqa: BLE001 — 이미지 하나 실패는 건너뜀
            continue
    texts = []
    for _, g in sorted(got, reverse=True)[:dcfg["images_max"]]:
        try:
            cmd = ["tesseract", str(g), "stdout", "-l", dcfg.get("ocr_langs", "kor+eng")]
            if shutil.which("nice"):
                cmd = ["nice", "-n", "15"] + cmd
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=dcfg["ocr_timeout"],
                               env={**os.environ, "OMP_THREAD_LIMIT": "2"})
            texts.append(r.stdout)
        except Exception as e:  # noqa: BLE001
            log(f"  OCR 실패 {type(e).__name__}")
    return "\n".join(re.sub(r"[ \t]+", " ", t) for t in texts), len(texts)
