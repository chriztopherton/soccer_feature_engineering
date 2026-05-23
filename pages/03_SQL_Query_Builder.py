"""Raw SQL query interface page."""
from pathlib import Path

import streamlit as st
from src.data.duckdb_loader import connect

DATA_ROOT = Path(__file__).resolve().parents[1] / "data"
DB_PATH = DATA_ROOT / "skillcorner.duckdb"


def main() -> None:
    st.title("🔧 SQL Query Builder")
    st.write(
        "Write custom SQL queries against `dynamic_events` and `phases_of_play` tables. "
        "Useful for data exploration and testing analytics ideas."
    )

    conn = connect(DB_PATH, read_only=True)

    with st.expander("📚 Schema Reference", expanded=False):
        st.subheader("dynamic_events")
        de_schema = conn.execute("DESCRIBE dynamic_events").df()
        st.dataframe(de_schema, use_container_width=True)

        st.subheader("phases_of_play")
        pop_schema = conn.execute("DESCRIBE phases_of_play").df()
        st.dataframe(pop_schema, use_container_width=True)

    st.subheader("Write your query")
    query = st.text_area(
        "SQL Query",
        value="SELECT match_id, team_id, event_type, COUNT(*) as count FROM dynamic_events GROUP BY match_id, team_id, event_type LIMIT 20",
        height=150,
        label_visibility="collapsed",
    )

    if st.button("▶️ Execute Query"):
        try:
            result = conn.execute(query).df()
            st.success(f"✅ Query returned {len(result)} rows")
            st.dataframe(result, use_container_width=True)

            # Option to download
            csv = result.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name="query_result.csv",
                mime="text/csv",
            )
        except Exception as e:
            st.error(f"❌ Query error: {e}")


if __name__ == "__main__":
    main()
