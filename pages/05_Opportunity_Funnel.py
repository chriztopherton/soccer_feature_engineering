"""Opportunity-to-Execution Funnel — where does the attacking chain break?"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.data.duckdb_loader import connect, list_match_ids

DATA_ROOT = Path(__file__).resolve().parents[1] / "data"
DB_PATH = DATA_ROOT / "skillcorner.duckdb"

PHASE_ORDER = ["build_up", "create", "finish", "transition", "quick_break", "direct", "chaotic", "set_play"]


def _placeholders(n: int) -> str:
    return ",".join(["?"] * n)


def load_run_chain(conn, match_ids: list, team_id: int, phase: str | None) -> tuple:
    phase_clause = "AND team_in_possession_phase_type = ?" if phase else ""
    params = match_ids + [team_id]
    if phase:
        params.append(phase)

    row = conn.execute(
        f"""
        SELECT
            COUNT(*)                                                                     AS runs_made,
            SUM(CASE WHEN targeted = TRUE THEN 1 ELSE 0 END)                            AS targeted,
            SUM(CASE WHEN targeted = TRUE AND received = TRUE THEN 1 ELSE 0 END)         AS received,
            SUM(CASE WHEN targeted AND received AND dangerous = TRUE THEN 1 ELSE 0 END)  AS dangerous_received,
            SUM(CASE WHEN targeted AND received AND xthreat > 0.05 THEN 1 ELSE 0 END)   AS high_xthreat
        FROM dynamic_events
        WHERE match_id IN ({_placeholders(len(match_ids))})
          AND team_id = ?
          AND event_type = 'off_ball_run'
          {phase_clause}
        """,
        params,
    ).fetchone()
    return row or (0, 0, 0, 0, 0)


def load_pass_chain(conn, match_ids: list, team_id: int, phase: str | None) -> tuple:
    phase_clause = "AND team_in_possession_phase_type = ?" if phase else ""
    params = match_ids + [team_id]
    if phase:
        params.append(phase)

    row = conn.execute(
        f"""
        SELECT
            COUNT(*)                                                                     AS options_available,
            SUM(CASE WHEN targeted = TRUE THEN 1 ELSE 0 END)                            AS attempted,
            SUM(CASE WHEN targeted = TRUE AND received = TRUE THEN 1 ELSE 0 END)         AS completed,
            SUM(CASE WHEN targeted AND received AND dangerous = TRUE THEN 1 ELSE 0 END)  AS dangerous_completed
        FROM dynamic_events
        WHERE match_id IN ({_placeholders(len(match_ids))})
          AND team_id = ?
          AND event_type = 'passing_option'
          {phase_clause}
        """,
        params,
    ).fetchone()
    return row or (0, 0, 0, 0)


def make_funnel(labels: list, values: list, colors: list, title: str) -> go.Figure:
    fig = go.Figure(
        go.Funnel(
            y=labels,
            x=values,
            textposition="inside",
            textinfo="value+percent initial",
            marker=dict(color=colors, line=dict(width=1, color="rgba(255,255,255,0.4)")),
            connector=dict(line=dict(color="rgba(80,80,80,0.4)", dash="dot", width=2)),
        )
    )
    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", font=dict(size=14)),
        height=380,
        margin=dict(l=10, r=10, t=45, b=10),
    )
    return fig


def rate(num, denom) -> str:
    return f"{100*num/denom:.1f}%" if denom else "—"


def main() -> None:
    st.title("🎯 Opportunity-to-Execution Funnel")
    st.write(
        "Follow the attacking chain from run created → targeted → received → dangerous outcome. "
        "Reveals whether a team's problem is *creating* chances or *converting* them."
    )

    conn = connect(DB_PATH, read_only=True)
    all_match_ids = list_match_ids(conn)
    if not all_match_ids:
        st.warning("No matches found. Build the database first.")
        return

    col_scope, col_match, col_team = st.columns(3)
    with col_scope:
        scope = st.radio("Scope", ["Single match", "All matches"], horizontal=True)
    with col_match:
        if scope == "Single match":
            selected_matches = [st.selectbox("Match", all_match_ids)]
        else:
            selected_matches = all_match_ids
            st.caption(f"Aggregating {len(all_match_ids)} matches")

    teams = conn.execute(
        f"SELECT DISTINCT team_id, team_shortname FROM dynamic_events "
        f"WHERE match_id IN ({_placeholders(len(selected_matches))}) ORDER BY team_shortname",
        selected_matches,
    ).fetchall()
    team_map = {t[1]: t[0] for t in teams}
    with col_team:
        selected_team_name = st.selectbox("Team", list(team_map.keys()))
    selected_team_id = team_map[selected_team_name]

    phase_filter = st.selectbox("Filter by phase (optional)", ["All phases"] + PHASE_ORDER)
    phase_arg = None if phase_filter == "All phases" else phase_filter

    run_data = load_run_chain(conn, selected_matches, selected_team_id, phase_arg)
    pass_data = load_pass_chain(conn, selected_matches, selected_team_id, phase_arg)

    col_runs, col_passes = st.columns(2)

    with col_runs:
        st.subheader("🏃 Off-Ball Run Chain")
        run_labels = [
            "Runs Made",
            "Targeted by Passer",
            "Pass Received",
            "Received in Danger Zone",
            "High-xT Received (>0.05)",
        ]
        run_values = list(run_data)
        run_colors = ["#1565C0", "#42A5F5", "#2E7D32", "#F9A825", "#C62828"]

        if run_values[0] > 0:
            st.plotly_chart(
                make_funnel(run_labels, run_values, run_colors, f"{selected_team_name} — Run Chain"),
                use_container_width=True,
            )
            m1, m2, m3 = st.columns(3)
            m1.metric("Targeting rate", rate(run_values[1], run_values[0]))
            m2.metric("Reception rate", rate(run_values[2], run_values[1]))
            m3.metric("Danger rate", rate(run_values[3], run_values[2]))
        else:
            st.info("No off-ball run data for this selection.")

    with col_passes:
        st.subheader("⚡ Passing Option Chain")
        pass_labels = [
            "Options Available",
            "Pass Attempted",
            "Pass Completed",
            "Dangerous & Completed",
        ]
        pass_values = list(pass_data)
        pass_colors = ["#4A148C", "#AB47BC", "#2E7D32", "#C62828"]

        if pass_values[0] > 0:
            st.plotly_chart(
                make_funnel(pass_labels, pass_values, pass_colors, f"{selected_team_name} — Pass Chain"),
                use_container_width=True,
            )
            m1, m2, m3 = st.columns(3)
            m1.metric("Attempt rate", rate(pass_values[1], pass_values[0]))
            m2.metric("Completion rate", rate(pass_values[2], pass_values[1]))
            m3.metric("Danger rate", rate(pass_values[3], pass_values[2]))
        else:
            st.info("No passing option data for this selection.")

    # Phase-by-phase breakdown table
    st.divider()
    st.subheader("Phase-by-phase breakdown")

    rows = []
    for phase in PHASE_ORDER:
        r = load_run_chain(conn, selected_matches, selected_team_id, phase)
        p = load_pass_chain(conn, selected_matches, selected_team_id, phase)
        if r[0] > 0 or p[0] > 0:
            rows.append(
                {
                    "Phase": phase.replace("_", " ").title(),
                    "Runs": r[0],
                    "Targeted": r[1],
                    "Received": r[2],
                    "Target %": rate(r[1], r[0]),
                    "Receive %": rate(r[2], r[1]),
                    "Pass Options": p[0],
                    "Attempted": p[1],
                    "Completed": p[2],
                    "Attempt %": rate(p[1], p[0]),
                    "Complete %": rate(p[2], p[1]),
                }
            )

    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No phase data available.")


if __name__ == "__main__":
    main()
