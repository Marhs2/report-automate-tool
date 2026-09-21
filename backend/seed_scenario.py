"""테스트용 사무 시나리오를 현재 DB에 넣는다.

재실행하면 시나리오 인원만 지우고 다시 채운다. 관리자 계정은 건드리지 않는다.

로그인 (비밀번호 모두 test1234)
  김서연  기획  성실 제출. 지난주 주간보고 있음. 오늘 제출됨.
  박민준  개발  오늘 초안만. 지난주 주간보고 있음.
  이하늘  운영  오늘 미제출. 지난주 목요일 빠짐. 주간보고 없음.
  최도윤  개발  오늘 제출. 지난주 주간보고 있음. 다른 사람 보고 읽기용.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from auth import hash_password
from db import DB_PATH
from weekly_deck import SCHEMA, format_dot_date, week_labels, week_start_of

SCENARIO_NAMES = ("김서연", "박민준", "이하늘", "최도윤")
PASSWORD = "test1234"

PROJECTS = (
    ("대한전선 IoT", "대한전선, IoT"),
    ("HD 현대건설기계 RTLS 유지보수", "RTLS, 현대건설기계"),
    ("MES", "MES"),
    ("내부 보고 자동화", "보고자동화, 일일보고"),
)


def weekdays(start: date, count: int = 5) -> list[date]:
    days = []
    day = start
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def this_monday(today: date) -> date:
    return today - timedelta(days=today.weekday())


def daily(project_name, *, done=None, progress=None, issues=None, requests=None, nxt=None):
    return {
        "projectName": project_name,
        "completedTasks": list(done or []),
        "inProgressTasks": list(progress or []),
        "issues": list(issues or []),
        "requests": list(requests or []),
        "nextPlans": list(nxt or []),
    }


def raw_lines(day: date, projects: list[dict]) -> str:
    lines = [f"{day.month}월 {day.day}일 일일보고"]
    for project in projects:
        lines.append(f"\n[{project['projectName']}]")
        for item in project["completedTasks"]:
            lines.append(f"- 완료: {item}")
        for item in project["inProgressTasks"]:
            lines.append(f"- 진행: {item}")
        for item in project["issues"]:
            lines.append(f"- 이슈: {item}")
        for item in project["requests"]:
            lines.append(f"- 요청: {item}")
        for item in project["nextPlans"]:
            lines.append(f"- 예정: {item}")
    return "\n".join(lines).strip()


def upsert_team(conn, name: str) -> int:
    row = conn.execute("SELECT id FROM teams WHERE team_name = ?", (name,)).fetchone()
    if row:
        return row[0]
    return conn.execute("INSERT INTO teams (team_name) VALUES (?)", (name,)).lastrowid


def upsert_member(conn, name: str, team_id: int) -> int:
    hashed = hash_password(PASSWORD)
    row = conn.execute("SELECT id FROM members WHERE name = ?", (name,)).fetchone()
    if row:
        conn.execute(
            "UPDATE members SET team_id = ?, password_hash = ?, is_admin = 0 WHERE id = ?",
            (team_id, hashed, row[0]),
        )
        return row[0]
    return conn.execute(
        """
        INSERT INTO members (name, team_id, password_hash, is_admin)
        VALUES (?, ?, ?, 0)
        """,
        (name, team_id, hashed),
    ).lastrowid


def clear_member_work(conn, member_id: int) -> None:
    for table in (
        "daily_reports",
        "projects",
        "weekly_reports",
        "report_drafts",
        "daily_report_drafts",
        "sessions",
    ):
        conn.execute(f"DELETE FROM {table} WHERE member_id = ?", (member_id,))


def insert_daily(conn, member_id: int, day: date, projects: list[dict]) -> None:
    raw = raw_lines(day, projects)
    parsed = {"projects": projects}
    iso = day.isoformat()
    conn.execute(
        """
        INSERT INTO daily_reports (member_id, report_date, raw_text, parsed_json)
        VALUES (?, ?, ?, ?)
        """,
        (member_id, iso, raw, json.dumps(parsed, ensure_ascii=False)),
    )
    for project in projects:
        conn.execute(
            """
            INSERT INTO projects (
                member_id, name, completed_tasks, in_progress_tasks,
                issues, requests, next_plans, report_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                member_id,
                project["projectName"],
                json.dumps(project["completedTasks"], ensure_ascii=False),
                json.dumps(project["inProgressTasks"], ensure_ascii=False),
                json.dumps(project["issues"], ensure_ascii=False),
                json.dumps(project["requests"], ensure_ascii=False),
                json.dumps(project["nextPlans"], ensure_ascii=False),
                iso,
            ),
        )


def insert_weekly(conn, member_id: int, name: str, team: str, days: list[date], deck: dict) -> None:
    selects = [day.isoformat() for day in days]
    done_label, next_label = week_labels(selects)
    payload = {
        "schema": SCHEMA,
        "report_date": format_dot_date(days[-1]),
        "author": name,
        "center": team,
        "week_label_done": done_label,
        "week_label_next": next_label,
        "director": "",
        **deck,
    }
    conn.execute(
        "INSERT INTO weekly_reports (member_id, selected_date, report_json) VALUES (?, ?, ?)",
        (member_id, json.dumps(selects), json.dumps(payload, ensure_ascii=False)),
    )
    week_start_of(selects)


def next_month_label(day: date) -> str:
    month = day.month + 1
    year = day.year
    if month == 13:
        month = 1
        year += 1
    return f"{month}월 초"


def seed(db_path: Path | str = DB_PATH) -> dict:
    today = date.today()
    monday = this_monday(today)
    last_week = weekdays(monday - timedelta(days=7), 5)
    this_week_so_far = [day for day in weekdays(monday, 5) if day <= today]

    conn = sqlite3.connect(db_path)
    try:
        planning = upsert_team(conn, "기획")
        develop = upsert_team(conn, "개발")
        ops = upsert_team(conn, "운영")

        seoyeon = upsert_member(conn, "김서연", planning)
        minjun = upsert_member(conn, "박민준", develop)
        haneul = upsert_member(conn, "이하늘", ops)
        doyun = upsert_member(conn, "최도윤", develop)
        ids = {
            "김서연": seoyeon,
            "박민준": minjun,
            "이하늘": haneul,
            "최도윤": doyun,
        }
        for member_id in ids.values():
            clear_member_work(conn, member_id)

        conn.execute("DELETE FROM known_projects")
        for name, keywords in PROJECTS:
            conn.execute(
                "INSERT INTO known_projects (name, keywords) VALUES (?, ?)",
                (name, keywords),
            )

        last = {day.strftime("%a"): day for day in last_week}
        mon, tue, wed, thu, fri = (
            last["Mon"],
            last["Tue"],
            last["Wed"],
            last["Thu"],
            last["Fri"],
        )

        seoyeon_days = {
            mon: [
                daily(
                    "대한전선 IoT",
                    done=["현장 인터뷰 일정 3건 확정", "지난주 미결 요구사항 12건 목록화"],
                    nxt=["화요일 현장 방문 질문지 초안"],
                )
            ],
            tue: [
                daily(
                    "대한전선 IoT",
                    done=["현장 질문지 초안 작성", "설비팀 김대리와 센서 위치 사전 협의"],
                    progress=["관제 화면 메뉴 구성안 작성 중"],
                    nxt=["수요일 내부 리뷰"],
                )
            ],
            wed: [
                daily(
                    "대한전선 IoT",
                    done=["메뉴 구성안 내부 리뷰 반영"],
                    issues=["현장 도면이 2019년 버전이어서 센서 좌표가 어긋남"],
                    requests=["설비팀에 최신 도면 요청"],
                    nxt=["목요일 도면 수령 후 좌표표 수정"],
                )
            ],
            thu: [
                daily(
                    "대한전선 IoT",
                    done=["최신 도면 수령", "1층 센서 좌표 18곳 수정"],
                    progress=["2층 좌표 대조 중"],
                    nxt=["금요일 고객 중간 공유 자료"],
                )
            ],
            fri: [
                daily(
                    "대한전선 IoT",
                    done=["고객 중간 공유 자료 발송", "다음 주 현장 실측 일정 합의"],
                    nxt=["다음 주 월요일 실측 체크리스트"],
                ),
                daily(
                    "내부 보고 자동화",
                    done=["주간보고 초안 문구 정리"],
                    nxt=["다음 주 팀 공유용 한 장 요약"],
                ),
            ],
        }
        for day, projects in seoyeon_days.items():
            insert_daily(conn, seoyeon, day, projects)
        today_projects_seoyeon = [
            daily(
                "대한전선 IoT",
                done=["현장 실측 체크리스트 확정", "설비팀 동행 시간 10시로 맞춤"],
                progress=["2층 좌표 잔여 4곳 확인 중"],
                nxt=["실측 후 관제 메뉴 시안 수정"],
            )
        ]
        if today not in seoyeon_days:
            insert_daily(conn, seoyeon, today, today_projects_seoyeon)
        for day in this_week_so_far:
            if day == today or day in seoyeon_days:
                continue
            insert_daily(
                conn,
                seoyeon,
                day,
                [
                    daily(
                        "대한전선 IoT",
                        done=[f"{day.month}/{day.day} 현장 실측 메모 정리"],
                        progress=["관제 메뉴 시안 수정"],
                        nxt=["고객 리뷰 일정 잡기"],
                    )
                ],
            )

        insert_weekly(
            conn,
            seoyeon,
            "김서연",
            "기획",
            last_week,
            {
                "notices": [
                    {
                        "title": "대한전선 현장 실측",
                        "body": ["다음 주 월요일 10시 설비팀 동행", "최신 도면 기준으로만 좌표를 말함"],
                    }
                ],
                "month_events": [
                    {"when": f"{last_week[0].month}/말", "title": "대한전선 중간 공유"}
                ],
                "next_month_events": [
                    {"when": next_month_label(last_week[0]), "title": "관제 화면 1차 시연"}
                ],
                "collab": {
                    "supports": ["AC"],
                    "done": ["설비팀과 센서 위치 사전 협의"],
                    "next": ["현장 실측 동행"],
                },
                "done": [
                    {
                        "title": "대한전선 IoT",
                        "items": [
                            "현장 인터뷰 일정 확정 및 질문지 작성",
                            "최신 도면 기준으로 1층 센서 좌표 18곳 수정",
                            "고객 중간 공유 자료 발송",
                        ],
                    },
                    {
                        "title": "내부 보고 자동화",
                        "items": ["주간보고 초안 문구 정리"],
                    },
                ],
                "next": [
                    {
                        "title": "대한전선 IoT",
                        "items": ["현장 실측 체크리스트", "관제 메뉴 시안 수정"],
                    },
                    {
                        "title": "내부 보고 자동화",
                        "items": ["팀 공유용 한 장 요약"],
                    },
                ],
            },
        )

        minjun_days = {
            mon: [
                daily(
                    "MES",
                    done=["작업지시 화면 필터 버그 수정", "스테이징 배포"],
                    nxt=["실데이터로 검색 속도 확인"],
                )
            ],
            tue: [
                daily(
                    "MES",
                    done=["검색 쿼리 인덱스 추가", "응답 1.8초 → 0.4초"],
                    issues=["특정 거래처 코드에 공백이 들어가면 결과가 비움"],
                    nxt=["공백 트림 처리"],
                ),
                daily(
                    "HD 현대건설기계 RTLS 유지보수",
                    progress=["태그 배터리 알림 조건 확인 중"],
                ),
            ],
            wed: [
                daily(
                    "MES",
                    done=["거래처 코드 공백 트림 반영", "QA 재현 시나리오 3건 통과"],
                    nxt=["목요일 운영 반영"],
                )
            ],
            thu: [
                daily(
                    "MES",
                    done=["운영 반영 완료"],
                    requests=["운영팀에 거래처 마스터 공백 점검 요청"],
                ),
                daily(
                    "HD 현대건설기계 RTLS 유지보수",
                    done=["배터리 30% 이하 알림 조건 수정"],
                    nxt=["현장 오탐 여부 모니터링"],
                ),
            ],
            fri: [
                daily(
                    "HD 현대건설기계 RTLS 유지보수",
                    done=["목·금 오탐 0건 확인"],
                    nxt=["다음 주 게이트웨이 로그 주기 조정"],
                )
            ],
        }
        for day, projects in minjun_days.items():
            insert_daily(conn, minjun, day, projects)
        for day in this_week_so_far:
            if day == today or day in minjun_days:
                continue
            insert_daily(
                conn,
                minjun,
                day,
                [
                    daily(
                        "MES",
                        done=[f"{day.month}/{day.day} 운영 문의 2건 처리"],
                        progress=["작업지시 엑셀 업로드 검증"],
                    )
                ],
            )
        conn.execute(
            """
            INSERT INTO report_drafts (member_id, report_date, raw_text, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                minjun,
                today.isoformat(),
                (
                    f"{today.month}월 {today.day}일 일일보고(초안)\n"
                    "[MES]\n"
                    "- 진행: 작업지시 엑셀 업로드 시 빈 행을 건너뛰게 수정 중\n"
                    "- 예정: 오후 운영 반영 전 스테이징 한 번 더\n"
                    "[HD 현대건설기계 RTLS 유지보수]\n"
                    "- 진행: 게이트웨이 로그 주기를 5분에서 2분으로 바꿀지 현장과 확인 필요"
                ),
            ),
        )
        insert_weekly(
            conn,
            minjun,
            "박민준",
            "개발",
            last_week,
            {
                "notices": [
                    {
                        "title": "MES 운영 반영",
                        "body": ["거래처 코드 공백 트림은 목요일 반영됨", "마스터 공백은 운영팀 점검 중"],
                    }
                ],
                "month_events": [{"when": f"{last_week[-1].month}/{last_week[-1].day}", "title": "MES 운영 배포"}],
                "next_month_events": [],
                "collab": {
                    "supports": ["AC", "CSC"],
                    "done": ["운영팀에 거래처 마스터 공백 점검 요청"],
                    "next": ["게이트웨이 로그 주기 협의"],
                },
                "done": [
                    {
                        "title": "MES",
                        "items": [
                            "작업지시 필터 버그 수정 및 검색 속도 개선",
                            "거래처 코드 공백 트림 운영 반영",
                        ],
                    },
                    {
                        "title": "HD 현대건설기계 RTLS 유지보수",
                        "items": ["배터리 30% 알림 오탐 조건 수정", "목·금 오탐 0건"],
                    },
                ],
                "next": [
                    {
                        "title": "MES",
                        "items": ["작업지시 엑셀 업로드 검증"],
                    },
                    {
                        "title": "HD 현대건설기계 RTLS 유지보수",
                        "items": ["게이트웨이 로그 주기 조정"],
                    },
                ],
            },
        )

        haneul_days = {
            mon: [
                daily(
                    "MES",
                    done=["야간 배치 실패 1건 재처리", "거래처 마스터 공백 37건 추출"],
                    nxt=["화요일 현업에 수정 요청"],
                )
            ],
            tue: [
                daily(
                    "MES",
                    done=["현업 수정 요청 메일 발송"],
                    progress=["공백 37건 중 12건 회신"],
                    nxt=["미회신 건 전화 확인"],
                )
            ],
            wed: [
                daily(
                    "MES",
                    done=["미회신 25건 전화 확인, 18건 수정"],
                    issues=["7건은 폐업 거래처라 마스터 정책 필요"],
                    requests=["기획에 폐업 거래처 처리 기준 요청"],
                )
            ],
            fri: [
                daily(
                    "HD 현대건설기계 RTLS 유지보수",
                    done=["현장 장애 콜 2건 종료"],
                    progress=["게이트웨이 재부팅 후 태그 유실 여부 관찰"],
                    nxt=["다음 주 월요일 유실 건수 공유"],
                )
            ],
        }
        for day, projects in haneul_days.items():
            insert_daily(conn, haneul, day, projects)
        if this_week_so_far and this_week_so_far[0] != today and this_week_so_far[0] not in haneul_days:
            insert_daily(
                conn,
                haneul,
                this_week_so_far[0],
                [
                    daily(
                        "MES",
                        done=["폐업 거래처 7건 비활성 처리 초안"],
                        requests=["기획 기준 회신 대기"],
                    )
                ],
            )

        doyun_days = {
            mon: [
                daily(
                    "내부 보고 자동화",
                    done=["일일보고 원문 옆 패널 복구 확인", "로그인 세션 만료 메시지 수정"],
                    nxt=["설정 화면에서 타인 부서 선택 제거 검토"],
                )
            ],
            tue: [
                daily(
                    "내부 보고 자동화",
                    done=["설정은 내 부서·프로젝트명만 남김"],
                    progress=["관리자 화면 사용자/부서 탭 작업 중"],
                )
            ],
            wed: [
                daily(
                    "내부 보고 자동화",
                    done=["관리자만 사용자·부서 추가 가능"],
                    nxt=["관리자는 타인 보고 수정 가능하도록 API 맞춤"],
                )
            ],
            thu: [
                daily(
                    "내부 보고 자동화",
                    done=["관리자 타인 일일·주간 수정 API 반영"],
                    issues=["주간 수정 화면을 일일과 같게 바꾸면 현장 반발"],
                    nxt=["주간은 읽기/수정 토글 유지, 버튼만 맞춤"],
                )
            ],
            fri: [
                daily(
                    "내부 보고 자동화",
                    done=["주간 상세 버튼 모양만 일일과 동일하게 맞춤", "빈 DB 기본 관리자 시드"],
                    nxt=["테스트용 실제 시나리오 데이터 넣기"],
                )
            ],
        }
        for day, projects in doyun_days.items():
            insert_daily(conn, doyun, day, projects)
        if today not in doyun_days:
            insert_daily(
                conn,
                doyun,
                today,
                [
                    daily(
                        "내부 보고 자동화",
                        done=["기획·개발·운영 테스트 시나리오 초안 작성"],
                        nxt=["김서연/박민준/이하늘 계정으로 화면 점검"],
                    )
                ],
            )
        for day in this_week_so_far:
            if day == today or day in doyun_days:
                continue
            insert_daily(
                conn,
                doyun,
                day,
                [
                    daily(
                        "내부 보고 자동화",
                        done=[f"{day.month}/{day.day} 관리자 화면 클릭 점검"],
                        nxt=["빈 칸 문구 다듬기"],
                    )
                ],
            )
        insert_weekly(
            conn,
            doyun,
            "최도윤",
            "개발",
            last_week,
            {
                "notices": [
                    {
                        "title": "권한",
                        "body": ["일반 사용자는 자기 보고만 수정", "관리자만 타인 수정·사용자 추가"],
                    }
                ],
                "month_events": [],
                "next_month_events": [],
                "collab": {
                    "supports": ["TC"],
                    "done": ["기획과 설정 화면 범위 합의"],
                    "next": ["테스트 시나리오로 화면 점검"],
                },
                "done": [
                    {
                        "title": "내부 보고 자동화",
                        "items": [
                            "설정은 내 부서·프로젝트명만 남김",
                            "관리자 화면과 타인 수정 API",
                            "주간은 레이아웃 유지, 버튼만 일일과 같게",
                        ],
                    }
                ],
                "next": [
                    {
                        "title": "내부 보고 자동화",
                        "items": ["테스트용 실제 시나리오 데이터 넣기"],
                    }
                ],
            },
        )

        conn.commit()
        return {
            "today": today.isoformat(),
            "last_week": [day.isoformat() for day in last_week],
            "this_week": [day.isoformat() for day in this_week_so_far],
            "users": ids,
            "password": PASSWORD,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    result = seed()
    print("시나리오를 넣었습니다.")
    print(f"오늘: {result['today']}")
    print(f"지난주: {', '.join(result['last_week'])}")
    print("로그인 비밀번호: test1234")
    print("  김서연  기획  오늘 제출됨 · 지난주 주간보고 있음")
    print("  박민준  개발  오늘 초안만 · 지난주 주간보고 있음")
    print("  이하늘  운영  오늘 미제출 · 지난주 목요일 빠짐 · 주간 없음")
    print("  최도윤  개발  오늘 제출됨 · 지난주 주간보고 있음")
    print("  관리자  (기존) admin1234 로 타인 수정 확인")
