from pathlib import Path
from src.data.duckdb_loader import build_database, connect

DATA_ROOT = Path(__file__).resolve().parents[1] / "data"
DB_PATH = DATA_ROOT / "skillcorner.duckdb"

# Build the DuckDB database once. Uncomment if you need to rebuild.
# build_database(DB_PATH, overwrite=False)

conn = connect(DB_PATH)

# Example queries
# df_events = conn.execute("SELECT * FROM dynamic_events WHERE match_id = 1886347 LIMIT 50").df()
# df_phases = conn.execute("SELECT * FROM phases_of_play WHERE match_id = 1886347 LIMIT 50").df()
