from __future__ import annotations

import duckdb
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
MATCHES_DIR = DATA_ROOT / "matches"
DEFAULT_DB_FILE = DATA_ROOT / "skillcorner.duckdb"


def default_database_path(database_path: Optional[Path | str] = None) -> Path:
    if database_path is None:
        return DEFAULT_DB_FILE
    database_path = Path(database_path)
    if database_path.is_dir():
        return database_path / "skillcorner.duckdb"
    return database_path


def connect(
    database_path: Optional[Path | str] = None,
    read_only: bool = False,
    motherduck_token: Optional[str] = None,
    motherduck_database: Optional[str] = None,
    attach_mode: Optional[str] = None,
) -> duckdb.DuckDBPyConnection:
    """
    Connect to DuckDB.
    
    Args:
        database_path: Local database file path. Ignored if motherduck_token is provided.
        read_only: Open in read-only mode (local only).
        motherduck_token: MotherDuck token. If provided, connects to MotherDuck instead of local DB.
        motherduck_database: Optional MotherDuck database name to connect to.
        attach_mode: Optional attach mode for MotherDuck connections.
    
    Returns:
        DuckDB connection object.
    """
    if motherduck_token:
        token = quote_plus(motherduck_token)
        if motherduck_database:
            uri = f"md:{motherduck_database}?motherduck_token={token}"
        else:
            uri = f"md:?motherduck_token={token}"
        if attach_mode:
            uri += f"&attach_mode={quote_plus(attach_mode)}"
        return duckdb.connect(uri)

    db_path = default_database_path(database_path)
    return duckdb.connect(str(db_path), read_only=read_only)


def build_database(
    database_path: Optional[Path | str] = None, overwrite: bool = False, motherduck_token: Optional[str] = None
) -> duckdb.DuckDBPyConnection:
    """
    Build DuckDB database from CSV files.
    
    Args:
        database_path: Local database file path (ignored for MotherDuck).
        overwrite: Delete and rebuild local database file.
        motherduck_token: MotherDuck token. If provided, uses MotherDuck instead of local.
    
    Returns:
        DuckDB connection object.
    """
    conn = connect(database_path, motherduck_token=motherduck_token)
    conn.execute("PRAGMA threads=4")

    conn.execute("DROP TABLE IF EXISTS dynamic_events")
    conn.execute("DROP TABLE IF EXISTS phases_of_play")

    dynamic_events_path = str(MATCHES_DIR / "*" / "*_dynamic_events.csv")
    phases_of_play_path = str(MATCHES_DIR / "*" / "*_phases_of_play.csv")

    conn.execute(
        f"CREATE TABLE dynamic_events AS SELECT * FROM read_csv_auto('{dynamic_events_path}', HEADER=True)"
    )
    conn.execute(
        f"CREATE TABLE phases_of_play AS SELECT * FROM read_csv_auto('{phases_of_play_path}', HEADER=True)"
    )

    conn.execute("CREATE INDEX IF NOT EXISTS idx_dynamic_events_match_team ON dynamic_events(match_id, team_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_phases_of_play_match_team ON phases_of_play(match_id, team_in_possession_id)"
    )

    return conn


def _build_where_clause(filters: list[str]) -> str:
    return " WHERE " + " AND ".join(filters) if filters else ""


def query_dynamic_events(
    conn: duckdb.DuckDBPyConnection,
    match_id: Optional[int] = None,
    team_id: Optional[int] = None,
    limit: int = 100,
):
    conditions: list[str] = []
    params: list[object] = []

    if match_id is not None:
        conditions.append("match_id = ?")
        params.append(match_id)
    if team_id is not None:
        conditions.append("team_id = ?")
        params.append(team_id)

    sql = f"SELECT * FROM dynamic_events{_build_where_clause(conditions)} LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).df()


def query_phases_of_play(
    conn: duckdb.DuckDBPyConnection,
    match_id: Optional[int] = None,
    team_id: Optional[int] = None,
    limit: int = 100,
):
    conditions: list[str] = []
    params: list[object] = []

    if match_id is not None:
        conditions.append("match_id = ?")
        params.append(match_id)
    if team_id is not None:
        conditions.append("team_in_possession_id = ?")
        params.append(team_id)

    sql = f"SELECT * FROM phases_of_play{_build_where_clause(conditions)} LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).df()


def list_match_ids(conn: duckdb.DuckDBPyConnection) -> list[int]:
    rows = conn.execute("SELECT DISTINCT match_id FROM dynamic_events ORDER BY match_id").fetchall()
    return [int(row[0]) for row in rows]


def has_tables(conn: duckdb.DuckDBPyConnection) -> bool:
    rows = conn.execute("SHOW TABLES").fetchall()
    return bool(rows)


def create_csv_views(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("CREATE OR REPLACE VIEW dynamic_events AS SELECT * FROM read_csv_auto('{}', HEADER=True)".format(
        str(MATCHES_DIR / "*" / "*_dynamic_events.csv")
    ))
    conn.execute("CREATE OR REPLACE VIEW phases_of_play AS SELECT * FROM read_csv_auto('{}', HEADER=True)".format(
        str(MATCHES_DIR / "*" / "*_phases_of_play.csv")
    ))
