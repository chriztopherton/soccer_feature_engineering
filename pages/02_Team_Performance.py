"""Team performance analytics page."""
from pathlib import Path

import streamlit as st
from src.data.duckdb_loader import connect, list_match_ids

DATA_ROOT = Path(__file__).resolve().parents[1] / "data"
DB_PATH = DATA_ROOT / "skillcorner.duckdb"


def main() -> None:
    st.title("Team Performance Analytics")
    st.write("Analyze team performance across passes, possession, and defensive actions.")

    conn = connect(DB_PATH, read_only=True)
    match_ids = list_match_ids(conn)

    if not match_ids:
        st.warning("No matches found in the database.")
        return

    selected_match = st.selectbox("Select a match", match_ids, index=0)

    # Get teams in the match
    teams = conn.execute(
        "SELECT DISTINCT team_id FROM dynamic_events WHERE match_id = ? ORDER BY team_id",
        [selected_match],
    ).fetchall()
    team_ids = [t[0] for t in teams]

    if not team_ids:
        st.warning("No teams found for the selected match.")
        return

    st.subheader(f"Match {selected_match}")
    col1, col2 = st.columns(2)

    for idx, team_id in enumerate(team_ids):
        with (col1 if idx == 0 else col2):
            st.markdown(f"#### Team {team_id}")

            # Pass stats
            pass_stats = conn.execute(
                """
                SELECT 
                  COALESCE(SUM(CASE WHEN pass_outcome = 'successful' THEN 1 ELSE 0 END), 0) as successful,
                  COALESCE(SUM(CASE WHEN pass_outcome = 'unsuccessful' THEN 1 ELSE 0 END), 0) as unsuccessful,
                  COALESCE(SUM(CASE WHEN pass_direction = 'forward' THEN 1 ELSE 0 END), 0) as forward_passes,
                  COALESCE(SUM(CASE WHEN pass_direction IN ('sideway_left', 'sideway_right') THEN 1 ELSE 0 END), 0) as side_passes,
                  COALESCE(SUM(CASE WHEN pass_direction = 'backward' THEN 1 ELSE 0 END), 0) as backward_passes
                FROM dynamic_events
                WHERE match_id = ? AND team_id = ? AND event_type = 'player_possession'
                """,
                [selected_match, team_id],
            ).fetchone()

            if pass_stats and pass_stats[0] is not None:
                successful, unsuccessful, forward, side, backward = pass_stats
                st.metric("Successful passes", int(successful))
                st.metric("Pass accuracy", f"{100*successful/(successful+unsuccessful):.1f}%" if (successful + unsuccessful) > 0 else "N/A")
                st.write(f"Forward: {int(forward)} | Side: {int(side)} | Backward: {int(backward)}")

            # Possession phases
            phase_stats = conn.execute(
                "SELECT COUNT(*) as phases, SUM(duration) as total_duration FROM phases_of_play WHERE match_id = ? AND team_in_possession_id = ?",
                [selected_match, team_id],
            ).fetchone()

            if phase_stats:
                phases, duration = phase_stats
                st.metric("Possession phases", int(phases))
                if duration:
                    st.metric("Total possession time", f"{duration:.1f}s")

            # Defensive actions
            def_stats = conn.execute(
                """
                SELECT 
                  COALESCE(SUM(CASE WHEN event_type = 'on_ball_engagement' AND event_subtype = 'pressing' THEN 1 ELSE 0 END), 0) as pressings,
                  COALESCE(SUM(CASE WHEN pressing_chain = TRUE THEN 1 ELSE 0 END), 0) as pressing_chains
                FROM dynamic_events
                WHERE match_id = ? AND team_id = ?
                """,
                [selected_match, team_id],
            ).fetchone()

            if def_stats:
                pressings, chains = def_stats
                st.metric("Pressing events", int(pressings))
                st.metric("Pressing chains", int(chains))


if __name__ == "__main__":
    main()
