"""Load the hand-written benchmark reports into the local application database.

The benchmark fixture remains the source of truth for the sample content. This
module only adapts its raw/gold records to the tables used by the report list,
activity grid, and project timeline screens.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_PATH = ROOT_DIR / "benchmark" / "dataset" / "gold_dataset.json"
DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent / "data" / "daily_reports.db"

PROJECT_ALIASES = {
    "MES": "A사 MES",
    "A사 MES 구축": "A사 MES",
    "A사 MES 시스템": "A사 MES",
    "여우비 앱": "여우비",
    "약맵": "Yak-Map",
    "약품 지도": "Yak-Map",
}


def load_dataset(dataset_path=DEFAULT_DATASET_PATH):
    """Read and validate the minimal shape required by the seed operation."""
    path = Path(dataset_path)
    try:
        with path.open(encoding="utf-8") as file:
            dataset = json.load(file)
    except FileNotFoundError as exc:
        raise ValueError(f"데이터셋 파일을 찾을 수 없습니다: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"데이터셋 JSON을 읽을 수 없습니다: {path}") from exc

    if not isinstance(dataset, dict) or not isinstance(dataset.get("cases"), list):
        raise ValueError("데이터셋에 cases 배열이 필요합니다.")
    if not isinstance(dataset.get("meta"), dict):
        raise ValueError("데이터셋에 meta 객체가 필요합니다.")

    for index, case in enumerate(dataset["cases"], start=1):
        required = {"date", "member", "raw", "gold"}
        if not isinstance(case, dict) or not required.issubset(case):
            raise ValueError(f"{index}번째 case에 필수 필드가 없습니다.")
        if not isinstance(case["gold"], dict) or not isinstance(
            case["gold"].get("projects"), list
        ):
            raise ValueError(f"{index}번째 case의 gold.projects가 올바르지 않습니다.")

    return dataset


def _ensure_schema(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS daily_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER NOT NULL,
            report_date DATE NOT NULL DEFAULT CURRENT_DATE,
            raw_text TEXT NOT NULL,
            parsed_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (member_id) REFERENCES members(id),
            UNIQUE(member_id, report_date)
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            completed_tasks TEXT,
            in_progress_tasks TEXT,
            issues TEXT,
            requests TEXT,
            next_plans TEXT,
            important_summary TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            report_date DATE,
            FOREIGN KEY (member_id) REFERENCES members(id)
        );

        CREATE TABLE IF NOT EXISTS known_projects (
            name TEXT PRIMARY KEY,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            keywords TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS project_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alias_name TEXT NOT NULL UNIQUE,
            canonical_name TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    project_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(projects)").fetchall()
    }
    if "report_date" not in project_columns:
        conn.execute("ALTER TABLE projects ADD COLUMN report_date DATE")


def _connect(database_path):
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _insert_project_rows(conn, member_id, report_date, projects):
    for project in projects:
        conn.execute(
            """
            INSERT INTO projects (
                member_id,
                name,
                completed_tasks,
                in_progress_tasks,
                issues,
                requests,
                next_plans,
                report_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                member_id,
                project.get("projectName") or "미분류 프로젝트",
                json.dumps(project.get("completedTasks", []), ensure_ascii=False),
                json.dumps(project.get("inProgressTasks", []), ensure_ascii=False),
                json.dumps(project.get("issues", []), ensure_ascii=False),
                json.dumps(project.get("requests", []), ensure_ascii=False),
                json.dumps(project.get("nextPlans", []), ensure_ascii=False),
                report_date,
            ),
        )


def seed_dataset(dataset_path=DEFAULT_DATASET_PATH, database_path=DEFAULT_DATABASE_PATH):
    """Upsert all fixture cases and return counts suitable for CLI/tests.

    A case replaces only the same member/date pair, matching the application's
    daily-report overwrite rule. Other users' reports and unrelated dates stay
    untouched.
    """
    dataset = load_dataset(dataset_path)
    members = dataset["meta"].get("members") or sorted(
        {case["member"] for case in dataset["cases"]}
    )
    projects = dataset["meta"].get("projects") or sorted(
        {
            project.get("projectName")
            for case in dataset["cases"]
            for project in case["gold"]["projects"]
            if project.get("projectName")
        }
    )

    with _connect(database_path) as conn:
        _ensure_schema(conn)

        for member_name in members:
            conn.execute(
                "INSERT OR IGNORE INTO members (name) VALUES (?)",
                (member_name,),
            )

        for project_name in projects:
            conn.execute(
                "INSERT OR IGNORE INTO known_projects (name) VALUES (?)",
                (project_name,),
            )

        for alias_name, canonical_name in PROJECT_ALIASES.items():
            if canonical_name in projects:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO project_aliases (alias_name, canonical_name)
                    VALUES (?, ?)
                    """,
                    (alias_name, canonical_name),
                )

        member_ids = {
            row[1]: row[0]
            for row in conn.execute(
                "SELECT id, name FROM members WHERE name IN ({})".format(
                    ",".join("?" for _ in members)
                ),
                members,
            ).fetchall()
        }

        for case in dataset["cases"]:
            member_id = member_ids[case["member"]]
            report_date = case["date"]
            conn.execute(
                "DELETE FROM projects WHERE member_id = ? AND report_date = ?",
                (member_id, report_date),
            )
            conn.execute(
                "DELETE FROM daily_reports WHERE member_id = ? AND report_date = ?",
                (member_id, report_date),
            )
            conn.execute(
                """
                INSERT INTO daily_reports (member_id, report_date, raw_text, parsed_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    member_id,
                    report_date,
                    case["raw"],
                    json.dumps(case["gold"], ensure_ascii=False),
                ),
            )
            _insert_project_rows(
                conn,
                member_id,
                report_date,
                case["gold"]["projects"],
            )

        conn.commit()

        report_count = conn.execute("SELECT COUNT(*) FROM daily_reports").fetchone()[0]
        project_count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]

    return {
        "members": len(members),
        "projects": len(projects),
        "reports": len(dataset["cases"]),
        "project_rows": project_count,
        "database_reports": report_count,
        "dates": len({case["date"] for case in dataset["cases"]}),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="벤치마크의 가상 일일보고를 로컬 SQLite에 적재합니다."
    )
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET_PATH),
        help="적재할 JSON 데이터셋 경로",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DATABASE_PATH),
        help="대상 SQLite 파일 경로",
    )
    args = parser.parse_args(argv)

    try:
        stats = seed_dataset(args.dataset, args.db)
    except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
        print(f"시드 실패: {exc}", file=sys.stderr)
        return 1

    print(
        "시드 완료: "
        f"보고서 {stats['reports']}건, "
        f"프로젝트 행 {stats['project_rows']}건, "
        f"사용자 {stats['members']}명, "
        f"기간 {stats['dates']}일"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
