from pathlib import Path

import streamlit as st
from src.data.duckdb_loader import (
    build_database,
    connect,
    has_tables,
    list_match_ids,
    query_dynamic_events,
    query_phases_of_play,
)

DATA_ROOT = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_ROOT / "skillcorner.duckdb"


def get_motherduck_token() -> str | None:
    """Get MotherDuck token from Streamlit secrets."""
    try:
        return st.secrets.get("motherduck_token")
    except Exception:
        return None


def ensure_database(motherduck_token: str | None = None) -> bool:
    if motherduck_token:
        try:
            conn = connect(motherduck_token=motherduck_token)
            if has_tables(conn):
                return True
        except Exception:
            pass
        # Build on MotherDuck
        build_database(motherduck_token=motherduck_token)
        return True
    
    # Local mode
    if DB_PATH.exists():
        try:
            conn = connect(DB_PATH)
            if has_tables(conn):
                return True
        except Exception:
            pass

    build_database(DB_PATH, overwrite=False)
    return True


def get_overview(conn):
    total_matches = conn.execute("SELECT COUNT(DISTINCT match_id) FROM dynamic_events").fetchone()[0]
    total_events = conn.execute("SELECT COUNT(*) FROM dynamic_events").fetchone()[0]
    total_phases = conn.execute("SELECT COUNT(*) FROM phases_of_play").fetchone()[0]
    return total_matches, total_events, total_phases


def main() -> None:
    st.set_page_config(page_title="SkillCorner DuckDB Explorer", layout="wide", initial_sidebar_state="expanded")

    motherduck_token = get_motherduck_token()
    is_motherduck = motherduck_token is not None

    st.title("⚽ SkillCorner Data Explorer")
    status_badge = "☁️ MotherDuck" if is_motherduck else "💾 Local DuckDB"
    st.write(
        f"Explore `dynamic_events` and `phases_of_play` without loading all files into memory. "
        f"**Status:** {status_badge}"
    )

    with st.sidebar:
        st.header("Database Management")
        if st.button("🔄 Build / Rebuild Database"):
            with st.spinner("Building database from CSV files..."):
                ensure_database(motherduck_token)
            st.success("✅ Database built successfully")

        st.divider()
        
        if is_motherduck:
            st.info("✅ Connected to **MotherDuck**\n\nNo local files needed!")
        else:
            st.info(f"💾 Using **Local DuckDB**\n\nDatabase: `{DB_PATH}`")
        
        st.divider()
        st.markdown(
            """
            ### About this app
            - **Fast queries**: DuckDB loads only requested rows  
            - **No RAM bloat**: Avoids loading all matches at once  
            - **SQL-powered**: All queries use efficient DuckDB SQL  
            """
        )

    conn = connect(motherduck_token=motherduck_token) if is_motherduck else connect(DB_PATH)

    if not has_tables(conn):
        st.error("❌ The database does not contain the expected tables. Rebuild the database from the sidebar.")
        return

    total_matches, total_events, total_phases = get_overview(conn)
    col1, col2, col3 = st.columns(3)
    col1.metric("📊 Matches", total_matches)
    col2.metric("🎯 Dynamic Events", f"{total_events:,}")
    col3.metric("🏀 Possession Phases", f"{total_phases:,}")

    st.divider()
    st.subheader("🔍 Browse Data")

    match_ids = list_match_ids(conn)
    if not match_ids:
        st.warning("No matches found in the database. Please build the database first.")
        return

    selected_match = st.selectbox("Select match_id", match_ids, index=0)
    team_ids = sorted(
        query_dynamic_events(conn, match_id=selected_match, limit=1000)["team_id"].dropna().unique().tolist()
    )
    selected_team = st.selectbox("Select team_id", team_ids, index=0 if team_ids else None)

    if selected_team is None:
        st.warning("No team_id values are available for the selected match.")
        return

    col_events, col_phases = st.columns(2)

    with col_events:
        st.subheader("📋 Dynamic Events")
        df_events = query_dynamic_events(conn, match_id=selected_match, team_id=selected_team, limit=500)
        st.write(f"Showing {len(df_events)} of up to 500 events (limited to first 500 rows)")
        st.dataframe(df_events, use_container_width=True)

        st.caption("Event type breakdown")
        event_counts = conn.execute(
            "SELECT event_type, COUNT(*) AS count FROM dynamic_events WHERE match_id = ? AND team_id = ? GROUP BY event_type ORDER BY count DESC",
            [selected_match, selected_team],
        ).df()
        st.bar_chart(event_counts.set_index("event_type")["count"])

    with col_phases:
        st.subheader("🏆 Phases of Play")
        df_phases = query_phases_of_play(conn, match_id=selected_match, team_id=selected_team, limit=200)
        st.write(f"Showing {len(df_phases)} of up to 200 phases")
        st.dataframe(df_phases, use_container_width=True)

        st.caption("Phase type breakdown")
        phase_counts = conn.execute(
            "SELECT team_in_possession_phase_type, COUNT(*) AS count FROM phases_of_play "
            "WHERE match_id = ? AND team_in_possession_id = ? GROUP BY team_in_possession_phase_type ORDER BY count DESC",
            [selected_match, selected_team],
        ).df()
        st.bar_chart(phase_counts.set_index("team_in_possession_phase_type")["count"])

    with st.expander("ℹ️ Query Details"):
        st.write(f"**Connection mode:** {'MotherDuck ☁️' if is_motherduck else 'Local DuckDB 💾'}")
        st.write(f"**Selected match_id:** {selected_match}")
        st.write(f"**Selected team_id:** {selected_team}")
        st.markdown(
            "This app uses **DuckDB SQL queries** behind the scenes to efficiently read only the requested data. "
            "No CSV files are fully loaded into memory."
        )


if __name__ == "__main__":
    main()
