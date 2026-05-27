"""Phase Transition Flow — Sankey diagram of how a team flows through tactical phases."""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.data.duckdb_loader import connect, list_match_ids

DATA_ROOT = Path(__file__).resolve().parents[1] / "data"
DB_PATH = DATA_ROOT / "skillcorner.duckdb"

PHASE_COLORS = {
    "build_up": "#43A047",
    "create": "#1E88E5",
    "finish": "#E53935",
    "transition": "#FB8C00",
    "quick_break": "#D81B60",
    "direct": "#8E24AA",
    "chaotic": "#546E7A",
    "set_play": "#6D4C41",
    "defending_transition": "#F4511E",
    "defending_quick_break": "#F50057",
    "low_block": "#37474F",
    "medium_block": "#546E7A",
    "high_block": "#78909C",
}

PHASE_LABEL = {
    "build_up": "Build Up",
    "create": "Create",
    "finish": "Finish",
    "transition": "Transition",
    "quick_break": "Quick Break",
    "direct": "Direct",
    "chaotic": "Chaotic",
    "set_play": "Set Play",
}


def load_transitions(conn, match_id: int, team_id: int) -> pd.DataFrame:
    df = conn.execute(
        "SELECT team_in_possession_id, team_in_possession_phase_type, frame_start "
        "FROM phases_of_play WHERE match_id = ? ORDER BY frame_start",
        [match_id],
    ).df()

    df["next_phase"] = df["team_in_possession_phase_type"].shift(-1)
    df["next_team_id"] = df["team_in_possession_id"].shift(-1)

    team_df = df[df["team_in_possession_id"] == team_id].dropna(subset=["next_phase"])

    transitions = (
        team_df.groupby(["team_in_possession_phase_type", "next_phase", "next_team_id"])
        .size()
        .reset_index(name="count")
    )
    transitions["retained"] = transitions["next_team_id"] == team_id
    return transitions


def build_sankey(transitions: pd.DataFrame, team_name: str) -> go.Figure:
    from_phases = transitions["team_in_possession_phase_type"].unique().tolist()
    to_phases = transitions["next_phase"].unique().tolist()

    # Source nodes (left) and target nodes (right) are separate so the same
    # phase can appear on both sides without Plotly collapsing them.
    source_nodes = sorted(set(from_phases))
    target_nodes = sorted(set(to_phases))

    # Label: "Phase" for sources, "Phase " (trailing space) for targets so
    # Plotly treats them as distinct nodes.
    node_labels = source_nodes + [f"{p} " for p in target_nodes]
    src_idx = {p: i for i, p in enumerate(source_nodes)}
    tgt_idx = {p: len(source_nodes) + i for i, p in enumerate(target_nodes)}

    node_colors = [
        PHASE_COLORS.get(p.strip(), "#9E9E9E") for p in node_labels
    ]

    sources, targets, values, link_colors, hover = [], [], [], [], []
    for _, row in transitions.iterrows():
        sources.append(src_idx[row["team_in_possession_phase_type"]])
        targets.append(tgt_idx[row["next_phase"]])
        values.append(row["count"])
        link_colors.append(
            "rgba(67,160,71,0.45)" if row["retained"] else "rgba(229,57,53,0.30)"
        )
        label = PHASE_LABEL.get(row["team_in_possession_phase_type"], row["team_in_possession_phase_type"])
        next_label = PHASE_LABEL.get(row["next_phase"], row["next_phase"])
        result = "✅ Retained" if row["retained"] else "❌ Turnover"
        hover.append(f"{label} → {next_label} | n={int(row['count'])} | {result}")

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=dict(
                pad=18,
                thickness=22,
                line=dict(color="rgba(0,0,0,0.3)", width=0.8),
                label=[PHASE_LABEL.get(l.strip(), l.strip()) for l in node_labels],
                color=node_colors,
                hovertemplate="%{label}<extra></extra>",
            ),
            link=dict(
                source=sources,
                target=targets,
                value=values,
                color=link_colors,
                customdata=hover,
                hovertemplate="%{customdata}<extra></extra>",
            ),
        )
    )
    fig.update_layout(
        title=dict(
            text=f"<b>{team_name}</b> — Tactical Phase Flow",
            font=dict(size=16),
        ),
        font=dict(size=13),
        height=560,
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def main() -> None:
    st.title("🌊 Phase Transition Flow")
    st.write(
        "Visualise how a team flows between tactical phases across a match. "
        "**Green links** = possession retained · **Red links** = turnover."
    )

    conn = connect(DB_PATH, read_only=True)
    match_ids = list_match_ids(conn)
    if not match_ids:
        st.warning("No matches found. Build the database first.")
        return

    col_m, col_t = st.columns(2)
    with col_m:
        selected_match = st.selectbox("Match", match_ids)
    teams = conn.execute(
        "SELECT DISTINCT team_in_possession_id, team_in_possession_shortname "
        "FROM phases_of_play WHERE match_id = ? ORDER BY team_in_possession_shortname",
        [selected_match],
    ).fetchall()
    team_map = {t[1]: t[0] for t in teams}
    with col_t:
        selected_team_name = st.selectbox("Team", list(team_map.keys()))

    selected_team_id = team_map[selected_team_name]
    transitions = load_transitions(conn, selected_match, selected_team_id)

    if transitions.empty:
        st.warning("No phase data for this selection.")
        return

    st.plotly_chart(build_sankey(transitions, selected_team_name), use_container_width=True)

    # Summary table
    st.subheader("Transition breakdown")
    col_ret, col_turn = st.columns(2)

    retained_df = (
        transitions[transitions["retained"]]
        .sort_values("count", ascending=False)
        [["team_in_possession_phase_type", "next_phase", "count"]]
        .rename(columns={"team_in_possession_phase_type": "From", "next_phase": "To", "count": "Count"})
    )
    turnover_df = (
        transitions[~transitions["retained"]]
        .sort_values("count", ascending=False)
        [["team_in_possession_phase_type", "next_phase", "count"]]
        .rename(columns={"team_in_possession_phase_type": "From", "next_phase": "To", "count": "Count"})
    )

    with col_ret:
        st.markdown("**✅ Retained possession**")
        st.dataframe(retained_df, use_container_width=True, hide_index=True)
    with col_turn:
        st.markdown("**❌ Turnovers**")
        st.dataframe(turnover_df, use_container_width=True, hide_index=True)

    total = transitions["count"].sum()
    retained_total = transitions[transitions["retained"]]["count"].sum()
    col1, col2, col3 = st.columns(3)
    col1.metric("Total phase exits", int(total))
    col2.metric("Retained possession", int(retained_total))
    col3.metric("Retention rate", f"{100*retained_total/total:.1f}%" if total else "—")


if __name__ == "__main__":
    main()
