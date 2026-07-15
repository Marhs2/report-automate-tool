"""SQLite database manager for SQL Workbench."""

from __future__ import annotations

import csv
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    rowcount: int
    message: str
    is_select: bool
    affected: int = 0
    elapsed_ms: float = 0.0
    statements: int = 1


@dataclass
class TableSummary:
    name: str
    kind: str  # table | view
    row_count: Optional[int] = None


class DatabaseManager:
    def __init__(self) -> None:
        self.conn: Optional[sqlite3.Connection] = None
        self.db_path: Optional[Path] = None
        self._table_info_cache: dict[str, list[dict[str, Any]]] = {}

    @property
    def is_connected(self) -> bool:
        return self.conn is not None

    def connect(self, path: str | Path) -> None:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"DB 파일을 찾을 수 없습니다: {path}")

        self.close()
        self.conn = sqlite3.connect(str(path), timeout=30.0)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        # 읽기 성능
        try:
            self.conn.execute("PRAGMA journal_mode = WAL")
        except Exception:
            pass
        try:
            self.conn.execute("PRAGMA synchronous = NORMAL")
            self.conn.execute("PRAGMA cache_size = -8000")  # ~8MB
            self.conn.execute("PRAGMA temp_store = MEMORY")
        except Exception:
            pass
        self.db_path = path
        self._table_info_cache.clear()

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None
            self.db_path = None
            self._table_info_cache.clear()

    def _require(self) -> sqlite3.Connection:
        if self.conn is None:
            raise RuntimeError("DB에 연결되어 있지 않습니다.")
        return self.conn

    def list_tables(self) -> list[str]:
        conn = self._require()
        cur = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
        return [row[0] for row in cur.fetchall()]

    def list_views(self) -> list[str]:
        conn = self._require()
        cur = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='view'
            ORDER BY name
            """
        )
        return [row[0] for row in cur.fetchall()]

    def list_schema_objects(self) -> list[TableSummary]:
        """테이블/뷰 목록 (카운트 없이 빠르게)."""
        items = [TableSummary(n, "table") for n in self.list_tables()]
        items.extend(TableSummary(n, "view") for n in self.list_views())
        return items

    def get_table_info(self, table: str, *, use_cache: bool = True) -> list[dict[str, Any]]:
        self._validate_identifier(table)
        if use_cache and table in self._table_info_cache:
            return self._table_info_cache[table]

        conn = self._require()
        cur = conn.execute(f'PRAGMA table_info("{table}")')
        cols = []
        for row in cur.fetchall():
            cols.append(
                {
                    "cid": row[0],
                    "name": row[1],
                    "type": row[2] or "TEXT",
                    "notnull": bool(row[3]),
                    "default": row[4],
                    "pk": bool(row[5]),
                }
            )
        self._table_info_cache[table] = cols
        return cols

    def invalidate_cache(self, table: Optional[str] = None) -> None:
        if table is None:
            self._table_info_cache.clear()
        else:
            self._table_info_cache.pop(table, None)

    def get_create_sql(self, table: str) -> str:
        conn = self._require()
        self._validate_identifier(table)
        cur = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = ? AND type IN ('table','view')",
            (table,),
        )
        row = cur.fetchone()
        return row[0] if row and row[0] else ""

    def get_indexes(self, table: str) -> list[dict[str, Any]]:
        conn = self._require()
        self._validate_identifier(table)
        cur = conn.execute(f'PRAGMA index_list("{table}")')
        indexes = []
        for r in cur.fetchall():
            name = r[1]
            unique = bool(r[2])
            cols_cur = conn.execute(f'PRAGMA index_info("{name}")')
            col_names = [c[2] for c in cols_cur.fetchall()]
            indexes.append({"name": name, "unique": unique, "columns": col_names})
        return indexes

    def get_foreign_keys(self, table: str) -> list[dict[str, Any]]:
        conn = self._require()
        self._validate_identifier(table)
        cur = conn.execute(f'PRAGMA foreign_key_list("{table}")')
        return [
            {
                "id": r[0],
                "seq": r[1],
                "table": r[2],
                "from": r[3],
                "to": r[4],
                "on_update": r[5],
                "on_delete": r[6],
            }
            for r in cur.fetchall()
        ]

    def count_rows(self, table: str, where: Optional[str] = None) -> int:
        conn = self._require()
        self._validate_identifier(table)
        where_sql = f" WHERE {where}" if where else ""
        cur = conn.execute(f'SELECT COUNT(*) FROM "{table}"{where_sql}')
        return int(cur.fetchone()[0])

    def fetch_table(
        self,
        table: str,
        limit: int = 200,
        offset: int = 0,
        order_by: Optional[str] = None,
        order_desc: bool = False,
        where: Optional[str] = None,
        where_params: Optional[Iterable[Any]] = None,
    ) -> QueryResult:
        self._validate_identifier(table)
        cols = [c["name"] for c in self.get_table_info(table)]
        if not cols:
            return QueryResult([], [], 0, "컬럼 없음", True)

        order_sql = ""
        if order_by:
            self._validate_identifier(order_by)
            direction = "DESC" if order_desc else "ASC"
            order_sql = f' ORDER BY "{order_by}" {direction}'

        where_sql = f" WHERE {where}" if where else ""
        params = list(where_params or [])

        sql = f'SELECT * FROM "{table}"{where_sql}{order_sql} LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        return self.execute(sql, params)

    def execute(self, sql: str, params: Optional[Iterable[Any]] = None) -> QueryResult:
        conn = self._require()
        sql = sql.strip()
        if not sql:
            raise ValueError("SQL이 비어 있습니다.")

        params = list(params or [])
        statements = self._split_statements(sql)
        t0 = time.perf_counter()

        last_select: Optional[QueryResult] = None
        total_affected = 0
        messages: list[str] = []
        ran = 0

        for stmt in statements:
            if not stmt.strip():
                continue
            ran += 1
            # multi-statement 시 파라미터는 단일 문에만 바인딩
            cur = conn.execute(stmt, params if len(statements) == 1 else [])
            if self._is_select_like(stmt):
                rows = cur.fetchall()
                columns = [d[0] for d in cur.description] if cur.description else []
                plain_rows = [tuple(r) for r in rows]
                last_select = QueryResult(
                    columns=columns,
                    rows=plain_rows,
                    rowcount=len(plain_rows),
                    message=f"{len(plain_rows)}행 조회됨",
                    is_select=True,
                )
            else:
                total_affected += cur.rowcount if cur.rowcount >= 0 else 0
                messages.append(f"OK (영향 행: {cur.rowcount})")
                # DDL 후 캐시 무효화
                self.invalidate_cache()

        conn.commit()
        elapsed = (time.perf_counter() - t0) * 1000.0

        if last_select is not None:
            if messages:
                last_select.message = "; ".join(messages) + " | " + last_select.message
                last_select.affected = total_affected
            last_select.elapsed_ms = elapsed
            last_select.statements = ran
            last_select.message = f"{last_select.message}  ·  {elapsed:.1f}ms"
            return last_select

        return QueryResult(
            columns=[],
            rows=[],
            rowcount=0,
            message=(
                f"{'; '.join(messages) if messages else '실행 완료'}  ·  {elapsed:.1f}ms"
            ),
            is_select=False,
            affected=total_affected,
            elapsed_ms=elapsed,
            statements=ran,
        )

    def insert_row(self, table: str, data: dict[str, Any]) -> int:
        self._validate_identifier(table)
        if not data:
            raise ValueError("삽입할 데이터가 없습니다.")
        for key in data:
            self._validate_identifier(key)

        cols = ", ".join(f'"{k}"' for k in data)
        placeholders = ", ".join("?" for _ in data)
        sql = f'INSERT INTO "{table}" ({cols}) VALUES ({placeholders})'
        conn = self._require()
        cur = conn.execute(sql, list(data.values()))
        conn.commit()
        return int(cur.lastrowid or 0)

    def update_row(
        self,
        table: str,
        data: dict[str, Any],
        pk_columns: list[str],
        pk_values: list[Any],
    ) -> int:
        self._validate_identifier(table)
        if not data:
            raise ValueError("수정할 데이터가 없습니다.")
        if not pk_columns or len(pk_columns) != len(pk_values):
            raise ValueError("PK 정보가 올바르지 않습니다.")

        for key in list(data) + pk_columns:
            self._validate_identifier(key)

        set_clause = ", ".join(f'"{k}" = ?' for k in data)
        where_clause = " AND ".join(f'"{k}" = ?' for k in pk_columns)
        sql = f'UPDATE "{table}" SET {set_clause} WHERE {where_clause}'
        conn = self._require()
        cur = conn.execute(sql, list(data.values()) + list(pk_values))
        conn.commit()
        return int(cur.rowcount)

    def delete_row(self, table: str, pk_columns: list[str], pk_values: list[Any]) -> int:
        self._validate_identifier(table)
        if not pk_columns or len(pk_columns) != len(pk_values):
            raise ValueError("PK 정보가 올바르지 않습니다.")
        for key in pk_columns:
            self._validate_identifier(key)

        where_clause = " AND ".join(f'"{k}" = ?' for k in pk_columns)
        sql = f'DELETE FROM "{table}" WHERE {where_clause}'
        conn = self._require()
        cur = conn.execute(sql, list(pk_values))
        conn.commit()
        return int(cur.rowcount)

    def get_primary_keys(self, table: str) -> list[str]:
        info = self.get_table_info(table)
        return [c["name"] for c in info if c["pk"]]

    def export_csv(self, path: str | Path, columns: list[str], rows: list[tuple]) -> None:
        path = Path(path)
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)

    @staticmethod
    def _validate_identifier(name: str) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name or ""):
            raise ValueError(f"잘못된 식별자: {name!r}")

    @staticmethod
    def _is_select_like(sql: str) -> bool:
        first = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ""
        return first in {"SELECT", "WITH", "PRAGMA", "EXPLAIN", "VALUES"}

    @staticmethod
    def _split_statements(sql: str) -> list[str]:
        """Split SQL by semicolon, ignoring those inside strings."""
        parts: list[str] = []
        buf: list[str] = []
        in_single = False
        in_double = False
        i = 0
        while i < len(sql):
            ch = sql[i]
            if ch == "'" and not in_double:
                if in_single and i + 1 < len(sql) and sql[i + 1] == "'":
                    buf.append("''")
                    i += 2
                    continue
                in_single = not in_single
                buf.append(ch)
            elif ch == '"' and not in_single:
                in_double = not in_double
                buf.append(ch)
            elif ch == ";" and not in_single and not in_double:
                stmt = "".join(buf).strip()
                if stmt:
                    parts.append(stmt)
                buf = []
            else:
                buf.append(ch)
            i += 1
        tail = "".join(buf).strip()
        if tail:
            parts.append(tail)
        return parts or [sql]
