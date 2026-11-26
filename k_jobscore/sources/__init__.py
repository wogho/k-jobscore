"""사이트별 수집기. 새 사이트는 이 폴더에 모듈을 추가하고 SOURCES에 등록한다.

각 모듈은 두 함수를 가진다.
  search(ctx, query, pages) -> list[posting]   # 목록(최신 순). ctx.seen_enough()가 참이면 멈춘다
  detail(ctx, sid) -> (본문 글, 이미지 주소 목록, 학력 힌트)
posting = {source, sid, url, title, company, location, career, career_min, edu, emp_type, deadline}
"""
from ._util import Ctx, html_images, html_text  # noqa: F401
from . import jobkorea, remember, saramin, wanted  # noqa: E402

SOURCES = {"wanted": wanted, "saramin": saramin, "jobkorea": jobkorea, "remember": remember}
