"""미리 만든 설정(프리셋). `k-jobscore init --preset <이름>`으로 고르고, 이후 config.json에서 자유롭게 고친다.

직무(roles)는 제목 정규식 + 회사 종류(any / public 공공기관 / bank 은행권 / big 대기업)로 정의한다.
roles가 비어 있으면 직무로 거르지 않는다(검색어로 모은 공고를 모두 남김).
"""

INFRA_ROLES = [
    {"id": "infra", "label": "시스템·인프라", "company": ["any"],
     "title": r"시스템\s*엔지니어|시스템\s*(운영|관리|엔지니어링|구축)|인프라|서버\s*(엔지니어|관리|운영)|클라우드\s*(엔지니어|운영|인프라|아키텍트)|"
              r"네트워크\s*(엔지니어|관리|운영|구축)|데이터\s*센터|\bIDC\b|system\s*engineer|infra|cloud\s*engineer|network\s*engineer|리눅스|linux"},
    {"id": "devops", "label": "DevOps", "company": ["any"],
     "title": r"dev\s*ops|데브옵스|devsecops|\bSRE\b|site\s*reliability|플랫폼\s*엔지니어|platform\s*engineer|CI\s*/?\s*CD|쿠버네티스|kubernetes|mlops"},
    {"id": "security", "label": "정보보안", "company": ["any"],
     "title": r"정보\s*보안|보안\s*(관제|엔지니어|컨설턴트|컨설팅|운영|담당|솔루션|진단|기술|분석|관리|인증)|사이버\s*보안|침해\s*(사고|대응)|모의\s*해킹|"
              r"화이트\s*해커|취약점|\bCERT\b|개인\s*정보\s*보호|정보\s*보호|\bISMS|security|보안\s*SW",
     "exclude_title": r"보안\s*요원|경비|시설\s*보안|보안\s*검색|경호"},
    {"id": "digital", "label": "디지털·IT(은행·공공·대기업)", "company": ["bank", "public", "big"],
     "title": r"디지털|\bIT\b|ICT|전산|정보\s*기술|정보\s*시스템|정보화|데이터|개발|프로그래머|SW|소프트웨어"},
    {"id": "jeonsan", "label": "전산(공공)", "company": ["public"], "title": r"전산|정보\s*보호|정보\s*보안|정보화"},
]

DEV_ROLES = [
    {"id": "backend", "label": "백엔드", "company": ["any"], "title": r"백엔드|back[\s-]?end|서버\s*개발|API\s*개발|java|spring|node\.?js|python|golang|\bgo\b"},
    {"id": "frontend", "label": "프론트엔드", "company": ["any"], "title": r"프론트|front[\s-]?end|웹\s*퍼블리|react|vue|typescript"},
    {"id": "mobile", "label": "모바일", "company": ["any"], "title": r"안드로이드|android|\biOS\b|모바일\s*앱|flutter|react\s*native"},
    {"id": "data", "label": "데이터·AI", "company": ["any"], "title": r"데이터\s*(엔지니어|분석|사이언)|data\s*(engineer|analyst|scien)|머신\s*러닝|machine\s*learning|\bAI\b|\bML\b|딥\s*러닝"},
]

PRESETS = {
    "infra-junior": {
        "label": "인프라·DevOps·보안 신입(고졸~초대졸)",
        "queries": ["시스템엔지니어", "인프라 엔지니어", "서버 엔지니어", "클라우드 엔지니어", "네트워크 엔지니어", "DevOps", "SRE",
                    "정보보안", "보안관제", "보안 엔지니어", "모의해킹", "정보보호", "전산", "디지털", "ICT"],
        "wanted_tag_ids": [665, 674, 671],
        "wanted_queries": ["전산", "디지털", "ICT", "정보보호"],
        "roles": INFRA_ROLES,
        "plus": ["EDR", "NGAV", ["클라우드", "Cloud"], "n8n", ["쿠버네티스", "k8s", "kubernetes"], "IaC", "CI/CD", "GPU"],
        "minus": ["datacenter", "데이터센터", "IDC", "OP", "교대근무", "총무", "사무기기", "영업", "파견", "사업", "헬프데스크", "키오스크", "PDA"],
        "my_level": "초대졸",
    },
    "dev-junior": {
        "label": "개발 신입(학력 제한 없음 기준)",
        "queries": ["백엔드 신입", "프론트엔드 신입", "웹개발 신입", "앱개발 신입", "데이터 엔지니어 신입"],
        "wanted_tag_ids": [872, 669, 873],
        "wanted_queries": [],
        "roles": DEV_ROLES,
        "plus": ["Spring", "React", "TypeScript", "AWS", "Docker", "CI/CD", "테스트"],
        "minus": ["SI", "파견", "상주", "영업", "교대근무"],
        "my_level": "대졸",
    },
    "all": {
        "label": "직무 제한 없음(검색어로 모은 공고 전부)",
        "queries": ["신입"],
        "wanted_tag_ids": [],
        "wanted_queries": ["신입"],
        "roles": [],
        "plus": [],
        "minus": ["파견"],
        "my_level": "대졸",
    },
}
