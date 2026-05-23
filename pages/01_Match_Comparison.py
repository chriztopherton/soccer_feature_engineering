"""Match comparison page."""
from pathlib import Path

import streamlit as st
from src.data.duckdb_loader import connect, list_match_ids

DATA_ROOT = Path(__file__).resolve().parents[1] / "data"
DB_PATH = DATA_ROOT / "skillcorner.duckdb"


def main() -> None:
    st.title("Match Comparison")
    st.write(
        "Compare statistics across multiple matches. Select matches and view aggregated event and phase counts."
    )

    conn = connect(DB_PATH, read_only=True)
    match_ids = list_match_ids(conn)

    if not match_ids:
        st.warning("No matches found in the database.")
        return

    selected_matches = st.multiselect("Select matches to compare", match_ids, default=match_ids[:2])

    if not selected_matches:
        st.info("Select at least one match to compare.")
        return

    # Summary stats per match
    st.subheader("Match Summary Statistics")
    matches_data = []
    for mid in selected_matches:
        result = conn.execute(
            "SELECT COUNT(*) as event_count, COUNT(DISTINCT team_id) as team_count FROM dynamic_events WHERE match_id = ?",
            [mid],
        ).fetchone()
        event_count, team_count = result
        matches_data.append({"match_id": mid, "events": event_count, "teams": team_count})

    import pandas as pd

    df_summary = pd.DataFrame(matches_data)
    st.dataframe(df_summary)

    # Event type distribution across matches
    st.subheader("Event type distribution")
    result_df = conn.execute(
        "SELECT match_id, event_type, COUNT(*) as count FROM dynamic_events WHERE match_id IN ({})".format(
            ",".join("?" * len(selected_matches))
        )
        + " GROUP BY match_id, event_type ORDER BY match_id, count DESC",
        selected_matches,
    ).df()
    st.dataframe(result_df)

    # Phase type distribution
    st.subheader("Phase type distribution")
    phases_df = conn.execute(
        "SELECT match_id, team_in_possession_phase_type, COUNT(*) as count FROM phases_of_play WHERE match_id IN ({})".format(
            ",".join("?" * len(selected_matches))
        )
        + " GROUP BY match_id, team_in_possession_phase_type ORDER BY match_id, count DESC",
        selected_matches,
    ).df()
    st.dataframe(phases_df)


if __name__ == "__main__":
    main()
