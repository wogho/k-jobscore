# config.json 전체 항목

`k-jobs init --preset <이름>`이 만든 파일을 고칩니다. 빠진 항목은 기본값으로 채우고, 틀린 값은 실행할 때 알려 줍니다.

| 항목 | 기본값 | 설명 |
|---|---|---|
| `preset` | `infra-junior` | 시작점. 화면의 '이 프리셋으로 되돌리기'가 쓰는 값 |
| `sources.<사이트>` | 모두 `true` | wanted · saramin · jobkorea · remember 켜고 끄기 |
| `queries` | 프리셋 | 사람인·잡코리아·리멤버 검색어 |
| `wanted_tag_ids` · `wanted_queries` | 프리셋 | 원티드 직무 분류 번호 · 검색어 |
| `pages` | 2 | 검색어당 최대 쪽 수(1~20). 이미 본 공고가 80% 넘으면 일찍 멈춤 |
| `network.delay_sec` | 3 | 요청 간격(초, 1~60) |
| `network.timeout` | 30 | 요청 시간 제한(초) |
| `network.user_agent` | 비움 | 비우면 일반 브라우저 값 |
| `network.proxy.<사이트>` | 비움 | 본인 프록시(`socks5h://host:port`, `http://...`). curl 필요 |
| `roles[]` | 프리셋 | `{id, label, title(정규식), exclude_title, company: [any|public|bank|big]}`. 비우면 직무로 거르지 않음 |
| `conditions.career.max_required_years` | 2 | 이 연수 이하를 요구하는 공고까지(0 = 신입만) |
| `conditions.career.include_intern` | true | 인턴 공고 포함 |
| `conditions.career.unlabeled` | keep | 경력 표기 없음: keep 통과 / hold 보류 / drop 제외 |
| `conditions.education.my_level` | 프리셋 | 무관·고졸·초대졸·대졸·석사·박사 |
| `conditions.education.unlabeled` | keep | 학력 표기 없음 처리 |
| `conditions.education.equivalent_ok` | true | "이에 준하는 경험" 줄의 학력은 필수가 아님 |
| `conditions.education.major_required` | keep | "관련 전공 필수" 처리 |
| `conditions.employment_exclude` | `["파견"]` | 제목·고용형태에 있으면 저장하지 않음 |
| `conditions.regions` | `[]` | 예: `["서울", "경기"]`. 비우면 전체 |
| `conditions.companies_exclude` · `companies_only` | `[]` | 회사 이름 일부로 거르기 |
| `conditions.open_days` | 30 | 마감일 없는 공고를 처음 본 뒤 보여 줄 일수 |
| `score.base` | 50 | 시작 점수 |
| `score.defaults` | 15 / 5 / −30 / −5 | 단어에 점수를 안 적었을 때: 제목 가점·상세 가점·제목 감점·상세 감점 |
| `score.body_cap` | 30 | 상세 점수 합의 상한(±) |
| `score.title_minus_skips_detail` | true | 제목에 감점 단어가 있으면 상세를 보지 않음 |
| `score.tiers` | 70 / 50 / 30 | 높음·보통·낮음 기준(원 색) |
| `score.words[]` | 프리셋 | 아래 참고 |
| `detail.enabled` | true | 상세 확인 |
| `detail.ocr` | tesseract | `tesseract` / `none` |
| `detail.ocr_langs` | `kor+eng` | tesseract 언어 |
| `detail.images_max` | 4 | 공고당 읽을 이미지 수(큰 것부터) |
| `detail.img_min_w` · `img_min_h` | 300 · 200 | 이보다 작은 이미지(로고 등)는 건너뜀 |
| `detail.budget_sec` | 1500 | 한 번에 상세 확인할 최대 시간 |
| `detail.retry_failed_after_h` | 6 | 실패한 상세를 다시 시도할 간격 |
| `ai.*` | 꺼짐 | README의 AI 판단 참고 |

## score.words

```jsonc
{"word": "EDR"}                                         // 가점, 기본 점수
{"word": ["클라우드", "Cloud"], "kind": "plus"}          // 동의어 묶음 — 한 번만 셈
{"word": "GPU", "kind": "plus", "title": 20, "body": 8}  // 단어별 점수
{"word": "교대근무", "kind": "minus", "where": "body"}    // 상세에서만
{"word": "파견", "kind": "veto"}                         // 있으면 0점(제목·상세)
{"word": "리눅스", "kind": "must"}                        // 제목·상세 어디에도 없으면 0점
{"word": "3\\s*교대", "kind": "minus", "match": "regex"}  // 정규식
```

`match`: `auto`(영문·숫자 4자 이하는 낱말 단위, 나머지는 포함) · `contains` · `word` · `regex`.
