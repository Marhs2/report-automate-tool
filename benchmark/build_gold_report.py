"""test-data/daily-reports.md → gold_dataset_report.json 생성기.

daily-reports.md 는 수기로 작성한 테스트 보고 32건(2주치)이다. 이 스크립트는
그 원문을 파싱하고, backend/model_asset/prompt.txt + json_Schema.json 규칙에 따라
사람(여기서는 라벨러)이 직접 판정한 정답(gold)을 붙여 벤치마크 데이터셋으로 만든다.
gold_dataset.json / gold_dataset_diverse.json 과 동일한 라벨링 규칙을 따른다.

라벨링 핵심 규칙 (prompt.txt 와 동일):
- projectName 은 업무가 속한 프로젝트 이름. 소속을 정할 수 없으면 '미분류 프로젝트'.
- completedTasks: 완료 표현(~했습니다, 완료, 개조식 동사 어근). 해결된 문제도 여기.
- inProgressTasks: 현재형(진행 중, 개발 중, 확인 중). 문제 + 그 해결·조사 작업이 같이
  보고되면 문제는 issues, 작업은 inProgress 양쪽에 둔다 (기존 gold 규범과 동일).
- issues: 보고 시점에 남아 있는 문제(미해결). status 는 원문이 해결을 명시한 경우만 '해결'.
- requests: 다른 사람·팀에게 하는 요청(요청드립니다, 부탁, 문의).
- nextPlans: 아직 시작 안 한 예정 업무(예정, 내일, 다음 주, ~하겠습니다).
- 메신저체는 작성자 본인 발화만, 접두어([시간] 이름:)는 제거.
- 표는 헤더 제거, 구분열=projectName, 진행률 열로 필드 판정.
- 업무가 전혀 없으면 {"projects": []}.

엣지 케이스 라벨링 판단:
- D06: '| 회의록자동화 | 녹음 파일 업로드 기능 개발 | 진행 중 || 회의록자동화 | ... | 완료 |'
  는 표 구분선 누락으로 두 행이 병합된 형태. 같은 업무가 '진행 중'과 '완료'로 모순되므로
  최종 상태인 '완료'만 gold 로 취한다.
- D04: '개발 개발 예정' 오타는 '개발 예정'으로 정리.
- D11/D15 의 '대시보드·통합 확인 화면'은 일일보고취합 도구의 모아보기 기능으로 분류.
- D21 '전체' 행, D25 취합 보고, D28/D32 팀 단위 계획은 소속 프로젝트가 없어 '미분류 프로젝트'.
- D16 은 사내 교육만 참석해 업무 없음 → {"projects": []}.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MD_PATH = ROOT / "test-data" / "daily-reports.md"
OUT_PATH = ROOT / "benchmark" / "dataset" / "gold_dataset_report.json"

HEADER_RE = re.compile(r"^##\s+(D\d+)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([^\|]+?)\s*\|\s*([^\|]+?)\s*$")

# case id → gold. 원문 문장은 가능한 그대로 두되, 표·메신저체 가공은 기존 gold 규범을 따른다.
GOLD: dict[str, dict] = {
    "D01": {
        "projects": [
            {
                "projectName": "일일보고취합",
                "completedTasks": ["보고서 날짜 선택 화면 개발 완료"],
                "inProgressTasks": [
                    "작성한 내용 임시 저장 기능 개발 중",
                    "긴 글 입력 시 줄바꿈이 사라지는 문제 원인 분석 중",
                    "내일 보고서 미리보기 화면 기본 구조 설계 중",
                ],
                "issues": [{"content": "긴 글 입력 시 줄바꿈이 사라지는 문제", "status": "미해결"}],
                "requests": ["입력 화면 동작 다시 확인 요청"],
                "nextPlans": [],
            }
        ]
    },
    "D02": {
        "projects": [
            {
                "projectName": "회의록자동화",
                "completedTasks": ["회의 녹음 파일 업로드와 요약 기능 개발 완료"],
                "inProgressTasks": ["녹음 파일이 너무 길 경우 중간에 멈추는 문제 원인 확인 중"],
                "issues": [{"content": "녹음 파일이 너무 길 경우 중간에 멈추는 문제", "status": "미해결"}],
                "requests": ["박현빈 팀장님께 회의록자동화 양식 요청"],
                "nextPlans": ["내일부터 회의 내용 정리 화면 개발 시작 예정"],
            }
        ]
    },
    "D03": {
        "projects": [
            {
                "projectName": "명함주소록",
                "completedTasks": ["명함 사진 30장 확인 완료"],
                "inProgressTasks": ["회사명과 부서명이 붙어서 표시되는 문제 확인 중"],
                "issues": [
                    {"content": "회사명과 부서명이 붙어서 표시되는 문제", "status": "미해결"},
                    {"content": "동일 명함이 두 개 생성되는 문제", "status": "미해결"},
                ],
                "requests": [],
                "nextPlans": ["내일 어떤 경우를 같은 명함으로 판단할지 기준을 정해서 다시 확인 예정"],
            }
        ]
    },
    "D04": {
        "projects": [
            {
                "projectName": "일일보고취합",
                "completedTasks": ["사람별 저장 보고서 확인 기능 구현"],
                "inProgressTasks": [],
                "issues": [],
                "requests": [],
                "nextPlans": ["보고서 미리보기 화면 기본 구조 개발 예정", "내일 제출 기능 테스트 예정"],
            }
        ]
    },
    "D05": {
        "projects": [
            {
                "projectName": "명함주소록",
                "completedTasks": [],
                "inProgressTasks": [
                    "연락처 목록 화면 개발 시작",
                    "연락처 검색 시 결과가 나오지 않는 문제 원인 확인 중",
                ],
                "issues": [
                    {"content": "연락처 검색 시 결과가 나오지 않는 문제", "status": "미해결"},
                    {"content": "명함 이름을 길게 입력하면 화면이 깨지는 문제", "status": "미해결"},
                ],
                "requests": [],
                "nextPlans": ["내일 검색 문제 발생 경우 재확인 후 기획팀에 화면 표시 문구 문의 예정"],
            }
        ]
    },
    "D06": {
        "projects": [
            {
                "projectName": "일일보고취합",
                "completedTasks": ["사람별 보고서 확인 기능 연결 완료"],
                "inProgressTasks": [],
                "issues": [],
                "requests": [],
                "nextPlans": [],
            },
            {
                "projectName": "회의록자동화",
                "completedTasks": ["녹음 파일 업로드 기능 개발 완료"],
                "inProgressTasks": [],
                "issues": [],
                "requests": [],
                "nextPlans": [],
            },
        ]
    },
    "D07": {
        "projects": [
            {
                "projectName": "일일보고취합",
                "completedTasks": [
                    "저장 목록 테스트 완료",
                    "날짜를 변경해도 작성했던 내용이 유지되도록 수정",
                    "긴 글 줄바꿈 문제 해결",
                ],
                "inProgressTasks": ["보고서 미리보기 화면 개발 중"],
                "issues": [],
                "requests": [],
                "nextPlans": ["보고서 미리보기 화면 내일까지 완료 예정", "팀원 한 명에게 실제 화면 테스트 요청 예정"],
            }
        ]
    },
    "D08": {
        "projects": [
            {
                "projectName": "회의록자동화",
                "completedTasks": ["회의 녹음 업로드 테스트 12개 작성 완료", "기본 회의록 생성 테스트 완료"],
                "inProgressTasks": ["녹음 내용을 참석자별로 나누는 기능 확인 중"],
                "issues": [],
                "requests": ["팀장님께 녹음 원본 확인 요청"],
                "nextPlans": [],
            }
        ]
    },
    "D09": {
        "projects": [
            {
                "projectName": "명함주소록",
                "completedTasks": ["명함 상세 보기 화면 개발 완료"],
                "inProgressTasks": [],
                "issues": [],
                "requests": [],
                "nextPlans": [],
            }
        ]
    },
    "D10": {
        "projects": [
            {
                "projectName": "일일보고취합",
                "completedTasks": ["보고서 미리보기 화면 기능 개발 완료", "보고서 목록 렌더링 속도 개선"],
                "inProgressTasks": [],
                "issues": [],
                "requests": [],
                "nextPlans": ["다음 주 월요일 활동 현황 화면 반영 예정"],
            }
        ]
    },
    "D11": {
        "projects": [
            {
                "projectName": "일일보고취합",
                "completedTasks": ["테스트 자동화를 위해 CI pipeline에 test 파일 추가, 빌드 시간 8분에서 3분으로 단축"],
                "inProgressTasks": [],
                "issues": [],
                "requests": [],
                "nextPlans": ["다음 주 세 프로젝트 진행 상황을 한눈에 확인할 수 있는 대시보드 구축 예정"],
            },
            {
                "projectName": "회의록자동화",
                "completedTasks": [],
                "inProgressTasks": ["녹음 내용 요약 작업 진행 중"],
                "issues": [{"content": "긴 회의록을 열 때 처리 속도가 느려지는 문제", "status": "미해결"}],
                "requests": [],
                "nextPlans": [],
            },
            {
                "projectName": "명함주소록",
                "completedTasks": [],
                "inProgressTasks": [],
                "issues": [{"content": "사진 인식 시 흐린 부분 처리 문제", "status": "미해결"}],
                "requests": [],
                "nextPlans": [],
            },
        ]
    },
    "D12": {
        "projects": [
            {
                "projectName": "회의록자동화",
                "completedTasks": ["오늘 회의록자동화 2차 요약 테스트 진행"],
                "inProgressTasks": ["회의 제목이 없는 파일도 저장 가능한지 확인 중"],
                "issues": [{"content": "녹음 소리가 작거나 잡음이 있으면 내용 인식률이 떨어지는 문제", "status": "미해결"}],
                "requests": [],
                "nextPlans": ["내일 녹음 파일 20개 더 모아서 테스트 예정"],
            }
        ]
    },
    "D13": {
        "projects": [
            {
                "projectName": "일일보고취합",
                "completedTasks": ["활동 현황 화면 반영 완료"],
                "inProgressTasks": [],
                "issues": [],
                "requests": [],
                "nextPlans": ["다음 주 주간보고 초안을 자동으로 생성하는 기능 개발 계속 진행 예정"],
            }
        ]
    },
    "D14": {
        "projects": [
            {
                "projectName": "명함주소록",
                "completedTasks": [
                    "명함 이름 선택 화면 개발",
                    "이름이 길 경우 버튼 영역을 넘어가는 문제를 글자가 줄어들어 표시되도록 수정",
                    "연락처 검색 빈 화면 문제를 안내 문구 추가로 해결",
                ],
                "inProgressTasks": [],
                "issues": [],
                "requests": [],
                "nextPlans": ["다음 주 명함을 다른 사람에게 공유하는 화면 개발 예정"],
            }
        ]
    },
    "D15": {
        "projects": [
            {
                "projectName": "일일보고취합",
                "completedTasks": ["이번 주 개발 화면 확인 완료"],
                "inProgressTasks": [],
                "issues": [],
                "requests": [],
                "nextPlans": ["다음 주 세 프로젝트 통합 확인 화면 개발 예정"],
            },
            {
                "projectName": "명함주소록",
                "completedTasks": ["명함 사진 인식 결과 확인 완료"],
                "inProgressTasks": [],
                "issues": [],
                "requests": [],
                "nextPlans": [],
            },
            {
                "projectName": "회의록자동화",
                "completedTasks": [],
                "inProgressTasks": [],
                "issues": [{"content": "녹음 정리 기준 팀장 확인 대기", "status": "미해결"}],
                "requests": [],
                "nextPlans": [],
            },
        ]
    },
    "D16": {"projects": []},
    "D17": {
        "projects": [
            {
                "projectName": "일일보고취합",
                "completedTasks": ["주간보고 초안 자동 생성 기능 개발 완료"],
                "inProgressTasks": ["주간보고 초안 생성 결과가 두 번 표시되는 문제 원인 분석 중"],
                "issues": [{"content": "주간보고 초안 생성 결과가 두 번 표시되는 문제", "status": "미해결"}],
                "requests": [],
                "nextPlans": ["내일 지난주 보고서 데이터도 함께 적용 테스트 예정"],
            }
        ]
    },
    "D18": {
        "projects": [
            {
                "projectName": "명함주소록",
                "completedTasks": [
                    "명함 공유 화면 구성 정리",
                    "명함 이름이 길 때 버튼 영역이 깨지는 문제를 글자 크기 조정으로 수정",
                ],
                "inProgressTasks": ["명함 공유 화면 개발 진행 중"],
                "issues": [],
                "requests": [],
                "nextPlans": [],
            }
        ]
    },
    "D19": {
        "projects": [
            {
                "projectName": "회의록자동화",
                "completedTasks": ["녹음 파일 20개 수집 완료", "요약 결과를 박현빈 팀장님께 공유", "기본 회의록 생성 테스트 완료"],
                "inProgressTasks": ["여러 사람이 동시에 말할 경우 음성이 섞이는 문제 확인 중"],
                "issues": [{"content": "여러 사람이 동시에 말할 경우 음성이 섞이는 문제", "status": "미해결"}],
                "requests": [],
                "nextPlans": [],
            }
        ]
    },
    "D20": {
        "projects": [
            {
                "projectName": "일일보고취합",
                "completedTasks": ["제출 현황이 두 번 표시되던 문제를 중복 날짜 데이터 계산 제거로 수정"],
                "inProgressTasks": [
                    "주간보고 초안에 지난주 내용이 정상적으로 들어가는지 테스트 중",
                    "보고서가 없는 날짜 표시 문제 추가 수정 중",
                ],
                "issues": [{"content": "보고서가 없는 날짜가 표시되지 않는 문제", "status": "미해결"}],
                "requests": [],
                "nextPlans": [],
            }
        ]
    },
    "D21": {
        "projects": [
            {
                "projectName": "일일보고취합",
                "completedTasks": ["주간보고 초안 첫 화면 개발 확인 완료"],
                "inProgressTasks": [],
                "issues": [],
                "requests": [],
                "nextPlans": [],
            },
            {
                "projectName": "명함주소록",
                "completedTasks": [],
                "inProgressTasks": ["흐린 명함 사진 인식 개선 확인 진행 중"],
                "issues": [],
                "requests": [],
                "nextPlans": [],
            },
            {
                "projectName": "회의록자동화",
                "completedTasks": [],
                "inProgressTasks": ["녹음 내용을 참석자별로 나누는 기능 확인 진행 중"],
                "issues": [],
                "requests": [],
                "nextPlans": [],
            },
        ]
    },
    "D22": {
        "projects": [
            {
                "projectName": "명함주소록",
                "completedTasks": ["명함 공유 화면 개발"],
                "inProgressTasks": ["명함을 사람별로 분류해서 보는 기능 개발 중"],
                "issues": [],
                "requests": ["기획팀에 명함 공유 대상 기준을 정해 달라고 요청"],
                "nextPlans": ["공유 화면까지 마무리하면 목요일쯤 화면 확인 가능"],
            }
        ]
    },
    "D23": {
        "projects": [
            {
                "projectName": "일일보고취합",
                "completedTasks": ["지난주 보고서 데이터 정상 취합 확인 완료", "보고서가 없는 날짜 표시 테스트 완료"],
                "inProgressTasks": ["이전 보고서 데이터를 유지하는 기능 개발 중"],
                "issues": [],
                "requests": ["운영팀에 이전 보고서 보관 기간 문의"],
                "nextPlans": ["이번 주 안에 전체 흐름 테스트 예정"],
            }
        ]
    },
    "D24": {
        "projects": [
            {
                "projectName": "회의록자동화",
                "completedTasks": ["녹음 내용을 상황별로 정리", "음성 전처리 적용 시 인식 정확도가 40%에서 72%로 향상되는 것 확인"],
                "inProgressTasks": [],
                "issues": [{"content": "긴 회의록을 불러올 때 처리 속도가 느려지는 문제", "status": "미해결"}],
                "requests": [],
                "nextPlans": ["내일 회의 상세 보기 화면 테스트 내용 작성 예정"],
            }
        ]
    },
    "D25": {"projects": []},
    "D26": {
        "projects": [
            {
                "projectName": "일일보고취합",
                "completedTasks": ["이전 보고서를 유지하는 기능 개발 완료", "이전 보고서 유지 기능 테스트 실행"],
                "inProgressTasks": [],
                "issues": [{"content": "날짜 저장 형식이 서로 달라 2건의 데이터 이동 실패", "status": "미해결"}],
                "requests": [],
                "nextPlans": ["날짜 변환 방식을 다시 정리한 뒤 내일 두 번째 테스트 진행 예정"],
            }
        ]
    },
    "D27": {
        "projects": [
            {
                "projectName": "명함주소록",
                "completedTasks": ["연락처 목록 화면 개발 완료"],
                "inProgressTasks": ["목록 처리 방식을 개선하는 방법 탐색 중"],
                "issues": [{"content": "연락처가 100개 이상일 때 화면 이동 속도가 느려지는 문제", "status": "미해결"}],
                "requests": ["디자인팀에 연락처 목록 화면 확인 요청"],
                "nextPlans": ["내일 성능 개선 방법을 추가로 확인 예정"],
            }
        ]
    },
    "D28": {
        "projects": [
            {
                "projectName": "일일보고취합",
                "completedTasks": ["export pipeline의 한글 파일 이름 테스트 완료"],
                "inProgressTasks": [],
                "issues": [],
                "requests": [],
                "nextPlans": [],
            },
            {
                "projectName": "회의록자동화",
                "completedTasks": [],
                "inProgressTasks": ["log 처리 방식을 변경 중"],
                "issues": [{"content": "긴 회의록 처리 과정에서 컴퓨터 메모리 사용량이 85%까지 증가하는 문제", "status": "미해결"}],
                "requests": [],
                "nextPlans": [],
            },
            {
                "projectName": "명함주소록",
                "completedTasks": [],
                "inProgressTasks": ["중복 판단 기준을 다시 확인 중"],
                "issues": [{"content": "중복이 아닌 명함에서도 duplicate 알림이 발생하는 문제", "status": "미해결"}],
                "requests": [],
                "nextPlans": [],
            },
        ]
    },
    "D29": {
        "projects": [
            {
                "projectName": "일일보고취합",
                "completedTasks": [
                    "날짜 저장 방식 결정 및 이전 보고서 이동 기능 반영 완료",
                    "이전 보고서 이동 두 번째 테스트 완료, 전체 데이터 정상 처리 확인",
                    "일일보고취합 사용 방법 정리 완료",
                ],
                "inProgressTasks": [],
                "issues": [],
                "requests": [],
                "nextPlans": ["다음 주 화요일 실제 데이터 이동 예정"],
            }
        ]
    },
    "D30": {
        "projects": [
            {
                "projectName": "회의록자동화",
                "completedTasks": ["회의록자동화 상세 보기 화면 테스트 내용 작성"],
                "inProgressTasks": [],
                "issues": [{"content": "긴 회의록을 열 때 처리 속도가 느려지는 문제", "status": "미해결"}],
                "requests": [],
                "nextPlans": ["아직 해결되지 않은 문제로 등록 예정", "다음 주 짧은 회의록부터 다시 테스트 예정"],
            }
        ]
    },
    "D31": {
        "projects": [
            {
                "projectName": "명함주소록",
                "completedTasks": ["연락처 목록의 속도 문제 개선", "긴 명함 이름의 화면 정상 표시 확인"],
                "inProgressTasks": [],
                "issues": [],
                "requests": [],
                "nextPlans": ["다음 주 모바일 화면 마무리 및 작은 화면에서 글자가 잘 보이는지 테스트 예정"],
            }
        ]
    },
    "D32": {
        "projects": [
            {
                "projectName": "일일보고취합",
                "completedTasks": ["Word 출력 시 작업 내용이 없는 경우 빈칸으로 표시되던 문제를 '없음'으로 표시되도록 수정"],
                "inProgressTasks": [],
                "issues": [],
                "requests": [],
                "nextPlans": [],
            },
            {
                "projectName": "명함주소록",
                "completedTasks": ["연락처 목록 속도 문제 개선"],
                "inProgressTasks": [],
                "issues": [],
                "requests": [],
                "nextPlans": [],
            },
            {
                "projectName": "회의록자동화",
                "completedTasks": [],
                "inProgressTasks": [],
                "issues": [{"content": "긴 회의록 처리 속도 저하 문제", "status": "미해결"}],
                "requests": [],
                "nextPlans": [],
            },
        ]
    },
}


def parse_md(text: str) -> list[dict]:
    cases = []
    current = None
    body = []
    for line in text.splitlines():
        m = HEADER_RE.match(line)
        if m:
            if current is not None:
                current["raw"] = "\n".join(body).strip()
                cases.append(current)
            current = {
                "id": m.group(1),
                "date": m.group(2),
                "member": m.group(3),
                "style": m.group(4),
            }
            body = []
        elif current is not None:
            body.append(line)
    if current is not None:
        current["raw"] = "\n".join(body).strip()
        cases.append(current)
    return cases


def main() -> None:
    text = MD_PATH.read_text(encoding="utf-8")
    cases = parse_md(text)
    if len(cases) != len(GOLD):
        raise SystemExit(f"건수 불일치: md={len(cases)} gold={len(GOLD)}")
    missing = set(GOLD) - {c["id"] for c in cases}
    if missing:
        raise SystemExit(f"gold 누락: {sorted(missing)}")

    dataset = {
        "meta": {
            "name": "daily-report-extraction-gold-report",
            "description": (
                "일일보고 자동 구조화 벤치마크용 자체 작성 테스트 데이터셋. "
                "가상 인물 4명(정동일, 신찬혁, 김재휘, 박현빈), 가상 프로젝트 3개"
                "(일일보고취합, 명함주소록, 회의록자동화), 2주치(2026-07-13~07-24) 32건. "
                "작성 스타일은 개조식/줄글/메신저체/표/한 줄/혼합/영문 혼합/업무 없음을 섞음. "
                "표 구분선 누락(진행 중 || 완료 행 병합), '개발 개발' 오타, 같은 업무의 "
                "모순 상태(진행 중/완료) 등 데이터 품질 엣지 케이스 포함."
            ),
            "members": ["정동일", "신찬혁", "김재휘", "박현빈"],
            "projects": ["일일보고취합", "명함주소록", "회의록자동화"],
            "label_spec": "backend/model_asset/prompt.txt + backend/model_asset/json_Schema.json 규칙에 따라 사람이 직접 라벨링 (gold_dataset.json과 동일 규칙)",
        },
        "cases": [],
    }

    counts = {}
    for c in cases:
        gold = GOLD[c["id"]]
        counts[c["style"]] = counts.get(c["style"], 0) + 1
        dataset["cases"].append(
            {
                "id": c["id"],
                "date": c["date"],
                "member": c["member"],
                "style": c["style"],
                "raw": c["raw"],
                "gold": gold,
            }
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"생성: {OUT_PATH} ({len(cases)}건)")
    print("스타일 분포:", dict(sorted(counts.items())))


if __name__ == "__main__":
    main()