"""AI-Powered Scouting Report — Claude writes a professional scouting report from SkillCorner tracking data."""
from pathlib import Path

import anthropic
import pandas as pd
import streamlit as st

from src.data.duckdb_loader import connect, list_match_ids

DATA_ROOT = Path(__file__).resolve().parents[1] / "data"
DB_PATH = DATA_ROOT / "skillcorner.duckdb"

GK_POSITIONS = {"GK"}

POSITION_ROLES = {
    "CB": "Centre-Back", "LB": "Left-Back", "RB": "Right-Back",
    "LWB": "Left Wing-Back", "RWB": "Right Wing-Back",
    "CDM": "Defensive Midfielder", "CM": "Central Midfielder",
    "CAM": "Attacking Midfielder", "LM": "Left Midfielder", "RM": "Right Midfielder",
    "LW": "Left Winger", "RW": "Right Winger",
    "CF": "Centre-Forward", "ST": "Striker", "SS": "Second Striker",
}


def _placeholders(n: int) -> str:
    return ",".join(["?"] * n)


def load_player_stats(conn, player_id: int, match_ids: list) -> dict:
    ph = _placeholders(len(match_ids))
    params = match_ids + [player_id]

    run_row = conn.execute(
        f"""
        SELECT
            COUNT(*) AS total_runs,
            SUM(CASE WHEN targeted = TRUE THEN 1 ELSE 0 END) AS targeted,
            SUM(CASE WHEN targeted = TRUE AND received = TRUE THEN 1 ELSE 0 END) AS received,
            SUM(CASE WHEN targeted AND received AND dangerous = TRUE THEN 1 ELSE 0 END) AS dangerous,
            COALESCE(SUM(TRY_CAST(xthreat AS DOUBLE)), 0) AS total_xthreat,
            COALESCE(AVG(TRY_CAST(speed_avg AS DOUBLE)), 0) AS avg_run_speed
        FROM dynamic_events
        WHERE match_id IN ({ph}) AND player_id = ? AND event_type = 'off_ball_run'
        """, params,
    ).fetchone()

    poss_row = conn.execute(
        f"""
        SELECT
            COUNT(*) AS total_possessions,
            SUM(CASE WHEN carry = TRUE THEN 1 ELSE 0 END) AS carries,
            SUM(CASE WHEN carry = TRUE AND TRY_CAST(distance_covered AS DOUBLE) >= 8 THEN 1 ELSE 0 END) AS long_carries,
            SUM(CASE WHEN forward_momentum = TRUE THEN 1 ELSE 0 END) AS fwd_momentum,
            SUM(CASE WHEN pass_outcome = 'successful' THEN 1 ELSE 0 END) AS passes_successful,
            SUM(CASE WHEN pass_outcome IS NOT NULL AND pass_outcome != '' THEN 1 ELSE 0 END) AS passes_attempted,
            SUM(CASE WHEN one_touch = TRUE AND end_type = 'pass' THEN 1 ELSE 0 END) AS one_touch_passes,
            COALESCE(AVG(TRY_CAST(speed_avg AS DOUBLE)), 0) AS avg_carry_speed,
            COALESCE(AVG(TRY_CAST(separation_start AS DOUBLE)), 0) AS avg_separation
        FROM dynamic_events
        WHERE match_id IN ({ph}) AND player_id = ? AND event_type = 'player_possession'
        """, params,
    ).fetchone()

    def_row = conn.execute(
        f"""
        SELECT
            COUNT(*) AS total_engagements,
            SUM(CASE WHEN event_subtype = 'pressing' THEN 1 ELSE 0 END) AS pressings,
            SUM(CASE WHEN end_type = 'direct_disruption' THEN 1 ELSE 0 END) AS disruptions,
            SUM(CASE WHEN end_type = 'direct_regain' THEN 1 ELSE 0 END) AS regains,
            COALESCE(AVG(TRY_CAST(speed_avg AS DOUBLE)), 0) AS avg_press_speed
        FROM dynamic_events
        WHERE match_id IN ({ph}) AND player_id = ? AND event_type = 'on_ball_engagement'
        """, params,
    ).fetchone()

    misc_row = conn.execute(
        f"""
        SELECT
            SUM(CASE WHEN stop_possession_danger = TRUE THEN 1 ELSE 0 END) AS stop_dangers,
            SUM(CASE WHEN force_backward = TRUE THEN 1 ELSE 0 END) AS force_backwards,
            SUM(CASE WHEN pressing_chain = TRUE THEN 1 ELSE 0 END) AS chain_involvements
        FROM dynamic_events
        WHERE match_id IN ({ph}) AND player_id = ?
        """, params,
    ).fetchone()

    phase_row = conn.execute(
        f"""
        SELECT team_in_possession_phase_type, COUNT(*) AS n
        FROM dynamic_events
        WHERE match_id IN ({ph}) AND player_id = ?
          AND team_in_possession_phase_type IS NOT NULL
        GROUP BY team_in_possession_phase_type ORDER BY n DESC LIMIT 3
        """, params,
    ).fetchall()

    return {
        "runs": {
            "total": int(run_row[0] or 0),
            "targeted": int(run_row[1] or 0),
            "received": int(run_row[2] or 0),
            "dangerous": int(run_row[3] or 0),
            "total_xthreat": round(float(run_row[4] or 0), 4),
            "avg_speed": round(float(run_row[5] or 0), 1),
            "targeting_rate": round(100 * (run_row[1] or 0) / max(run_row[0], 1), 1),
            "reception_rate": round(100 * (run_row[2] or 0) / max(run_row[1], 1), 1),
        },
        "possession": {
            "total": int(poss_row[0] or 0),
            "carries": int(poss_row[1] or 0),
            "long_carries": int(poss_row[2] or 0),
            "fwd_momentum": int(poss_row[3] or 0),
            "passes_successful": int(poss_row[4] or 0),
            "passes_attempted": int(poss_row[5] or 0),
            "one_touch_passes": int(poss_row[6] or 0),
            "avg_carry_speed": round(float(poss_row[7] or 0), 1),
            "avg_separation": round(float(poss_row[8] or 0), 1),
            "pass_accuracy": round(100 * (poss_row[4] or 0) / max(poss_row[5], 1), 1),
        },
        "defense": {
            "total_engagements": int(def_row[0] or 0),
            "pressings": int(def_row[1] or 0),
            "disruptions": int(def_row[2] or 0),
            "regains": int(def_row[3] or 0),
            "avg_press_speed": round(float(def_row[4] or 0), 1),
        },
        "misc": {
            "stop_dangers": int(misc_row[0] or 0),
            "force_backwards": int(misc_row[1] or 0),
            "chain_involvements": int(misc_row[2] or 0),
        },
        "top_phases": [row[0] for row in phase_row],
    }


def load_player_dna_percentiles(conn, player_id: int, match_ids: list) -> dict:
    ph = _placeholders(len(match_ids))
    df = conn.execute(
        f"SELECT * FROM dynamic_events WHERE match_id IN ({ph})", match_ids,
    ).df()

    bool_cols = [
        "targeted", "received", "dangerous", "forward_momentum", "carry",
        "one_touch", "pressing_chain", "stop_possession_danger", "force_backward",
    ]
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.lower().map(
                {"true": True, "false": False, "1": True, "0": False}
            )

    records = []
    for (pid,), g in df.groupby(["player_id"]):
        if g["player_position"].iloc[0] in GK_POSITIONS:
            continue
        runs = g[g["event_type"] == "off_ball_run"]
        poss = g[g["event_type"] == "player_possession"]
        eng = g[g["event_type"] == "on_ball_engagement"]

        run_xthreat = pd.to_numeric(runs["xthreat"], errors="coerce").sum()
        targeted_rate = (runs["targeted"] == True).mean() if len(runs) > 0 else 0
        run_threat = float(run_xthreat * (1.0 + targeted_rate))

        sep_start = pd.to_numeric(poss["separation_start"], errors="coerce")
        space_creation = float((sep_start >= 6).sum() + (poss["forward_momentum"] == True).sum() * 0.6)

        direct_disruptions = int((eng["end_type"] == "direct_disruption").sum())
        direct_regains = int((eng["end_type"] == "direct_regain").sum())
        stop_danger = int((g["stop_possession_danger"] == True).sum())
        force_bwd = int((g["force_backward"] == True).sum())
        def_disruption = float(direct_disruptions * 2 + direct_regains + stop_danger + force_bwd * 0.5)

        carries = poss[poss["carry"] == True]
        dist = pd.to_numeric(carries["distance_covered"], errors="coerce")
        speed = pd.to_numeric(carries["speed_avg"], errors="coerce")
        long_carries = int((dist >= 8).sum())
        fast_long = int(((dist >= 8) & (speed >= 15)).sum())
        ball_carrying = float(long_carries + fast_long * 1.5)

        all_passes = poss[poss["pass_outcome"].notna() & (poss["pass_outcome"] != "")]
        n_passes = len(all_passes)
        accuracy = int((all_passes["pass_outcome"] == "successful").sum()) / n_passes if n_passes > 0 else 0
        one_touch = int(((poss["one_touch"] == True) & (poss["end_type"] == "pass")).sum())
        dangerous_comp = int(
            ((runs["targeted"] == True) & (runs["received"] == True) & (runs["dangerous"] == True)).sum()
        )
        passing_quality = float(accuracy * n_passes * 0.25 + one_touch + dangerous_comp * 2)

        pressing = eng[eng["event_subtype"] == "pressing"]
        chain = int((g["pressing_chain"] == True).sum())
        high_speed_press = int((pd.to_numeric(pressing["speed_avg"], errors="coerce") >= 20).sum())
        press_intensity = float(len(pressing) + chain * 0.4 + high_speed_press * 1.5)

        records.append({
            "player_id": pid,
            "run_threat": run_threat, "space_creation": space_creation,
            "def_disruption": def_disruption, "ball_carrying": ball_carrying,
            "passing_quality": passing_quality, "press_intensity": press_intensity,
        })

    result = pd.DataFrame(records)
    if result.empty or player_id not in result["player_id"].values:
        return {}

    dims = ["run_threat", "space_creation", "def_disruption", "ball_carrying", "passing_quality", "press_intensity"]
    for d in dims:
        result[f"{d}_pct"] = result[d].rank(pct=True) * 100

    row = result[result["player_id"] == player_id].iloc[0]
    return {
        "Run Threat": round(row["run_threat_pct"], 1),
        "Space Creation": round(row["space_creation_pct"], 1),
        "Defensive Disruption": round(row["def_disruption_pct"], 1),
        "Ball Carrying": round(row["ball_carrying_pct"], 1),
        "Passing Quality": round(row["passing_quality_pct"], 1),
        "Press Intensity": round(row["press_intensity_pct"], 1),
    }


def build_prompt(
    player_name: str, position: str, team: str,
    match_ids: list, stats: dict, percentiles: dict,
    scout_focus: str, comparison_context: str,
) -> str:
    role = POSITION_ROLES.get(position, position)
    lines = [
        f"You are a professional football scout writing a confidential scouting report for {player_name}, "
        f"a {role} ({position}) playing for {team}.",
        f"The analysis is based on {len(match_ids)} match(es) of SkillCorner tracking data.",
        "",
        "## Tactical DNA Percentiles (vs. all players in dataset)",
    ]
    for dim, pct in percentiles.items():
        tier = "Elite" if pct >= 85 else "Above avg" if pct >= 60 else "Average" if pct >= 40 else "Below avg"
        lines.append(f"  - {dim}: {pct:.0f}th percentile ({tier})")

    lines += [
        "", "## Off-Ball Movement",
        f"  - Total runs: {stats['runs']['total']}",
        f"  - Targeting rate: {stats['runs']['targeting_rate']}%",
        f"  - Reception rate: {stats['runs']['reception_rate']}%",
        f"  - Dangerous receptions: {stats['runs']['dangerous']}",
        f"  - Total xThreat generated: {stats['runs']['total_xthreat']}",
        f"  - Average run speed: {stats['runs']['avg_speed']} km/h",
        "", "## Ball Progression & Carrying",
        f"  - Total possessions: {stats['possession']['total']}",
        f"  - Carries: {stats['possession']['carries']} ({stats['possession']['long_carries']} long ≥8m)",
        f"  - Forward momentum plays: {stats['possession']['fwd_momentum']}",
        f"  - Average separation from defenders: {stats['possession']['avg_separation']}m",
        "", "## Passing",
        f"  - Pass accuracy: {stats['possession']['pass_accuracy']}% ({stats['possession']['passes_successful']}/{stats['possession']['passes_attempted']})",
        f"  - One-touch passes: {stats['possession']['one_touch_passes']}",
        "", "## Defensive Contribution",
        f"  - Pressings: {stats['defense']['pressings']} (avg speed: {stats['defense']['avg_press_speed']} km/h)",
        f"  - Direct disruptions: {stats['defense']['disruptions']}",
        f"  - Ball regains: {stats['defense']['regains']}",
        f"  - Stopped possession dangers: {stats['misc']['stop_dangers']}",
        f"  - Forced backward passes: {stats['misc']['force_backwards']}",
        f"  - Pressing chain involvements: {stats['misc']['chain_involvements']}",
        "", f"## Most Active Phases: {', '.join(stats['top_phases']) if stats['top_phases'] else 'N/A'}",
    ]
    if scout_focus:
        lines += ["", "## Scout Focus Area", f"  {scout_focus}"]
    if comparison_context:
        lines += ["", "## Comparison Context", f"  {comparison_context}"]
    lines += [
        "", "---", "",
        "Write a professional scouting report in flowing prose (not bullet points). Structure it as:",
        "1. **Executive Summary** — 2-3 sentence overview",
        "2. **Attacking Contribution** — off-ball movement, runs, space creation, carries",
        "3. **Technical Quality** — passing, ball control, decision-making",
        "4. **Defensive Work Rate** — pressing, disruptions, positioning",
        "5. **Tactical Fit** — systems/formations; positional versatility",
        "6. **Strengths & Weaknesses** — honest and data-driven",
        "7. **Scouting Verdict** — recommendation (sign / monitor / pass) with reasoning",
        "",
        "Use precise, professional language. Reference specific numbers. "
        "The report should read like it comes from an elite scout at a top European club.",
    ]
    return "\n".join(lines)


def stream_report(client: anthropic.Anthropic, prompt: str) -> None:
    placeholder = st.empty()
    full_text = ""
    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=2000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            full_text += text
            placeholder.markdown(full_text + "▌")
    placeholder.markdown(full_text)


def main() -> None:
    st.title("🕵️ AI Scouting Report")
    st.write(
        "Select a player and let Claude write a professional scouting report "
        "based on their SkillCorner tracking data."
    )

    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"]
    except (KeyError, Exception):
        st.error("**Anthropic API key not found.** Add `ANTHROPIC_API_KEY = \"sk-ant-...\"` to `.streamlit/secrets.toml`.")
        with st.expander("Setup instructions"):
            st.code('ANTHROPIC_API_KEY = "sk-ant-your-key-here"', language="toml")
        return

    conn = connect(DB_PATH, read_only=True)
    all_match_ids = list_match_ids(conn)
    if not all_match_ids:
        st.warning("No matches found. Build the database first.")
        return

    col_scope, col_match = st.columns([1, 2])
    with col_scope:
        scope = st.radio("Data scope", ["Single match", "All matches"])
    with col_match:
        if scope == "Single match":
            selected_match = st.selectbox("Match", all_match_ids)
            match_ids = [selected_match]
        else:
            selected_match = st.selectbox("Browse match (for player list)", all_match_ids)
            match_ids = all_match_ids
            st.caption(f"Stats aggregated across all {len(all_match_ids)} matches")

    teams = conn.execute(
        "SELECT DISTINCT team_id, team_shortname FROM dynamic_events "
        "WHERE match_id = ? ORDER BY team_shortname",
        [selected_match],
    ).fetchall()
    team_map = {t[1]: t[0] for t in teams}

    col_t, col_p = st.columns(2)
    with col_t:
        selected_team_name = st.selectbox("Team", list(team_map.keys()))
    selected_team_id = team_map[selected_team_name]

    players = conn.execute(
        "SELECT DISTINCT player_id, player_name, player_position "
        "FROM dynamic_events "
        "WHERE match_id = ? AND team_id = ? AND player_position NOT IN ('GK') "
        "ORDER BY player_name",
        [selected_match, selected_team_id],
    ).fetchall()
    player_map = {f"{p[1]} ({p[2]})": (p[0], p[1], p[2]) for p in players}

    with col_p:
        selected_player_label = st.selectbox("Player", list(player_map.keys()))

    player_id, player_name, player_position = player_map[selected_player_label]

    with st.expander("Scout options (optional)"):
        scout_focus = st.text_area(
            "Focus area",
            placeholder="e.g. 'Evaluate fit as a box-to-box midfielder in a 4-3-3'",
            height=80,
        )
        comparison_context = st.text_area(
            "Comparison context",
            placeholder="e.g. 'Compare to a deep-lying playmaker role'",
            height=80,
        )

    if st.button("Generate Scouting Report", type="primary", use_container_width=True):
        with st.spinner("Collecting player data…"):
            stats = load_player_stats(conn, player_id, match_ids)
        with st.spinner("Computing tactical DNA percentiles…"):
            percentiles = load_player_dna_percentiles(conn, player_id, match_ids)

        if not percentiles:
            st.warning("Insufficient data to compute percentiles for this player.")
            return

        prompt = build_prompt(
            player_name, player_position, selected_team_name,
            match_ids, stats, percentiles, scout_focus, comparison_context,
        )

        st.divider()
        st.subheader(f"Scouting Report: {player_name}")
        st.caption(
            f"{POSITION_ROLES.get(player_position, player_position)} · "
            f"{selected_team_name} · {len(match_ids)} match(es)"
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Runs", stats["runs"]["total"])
        c2.metric("Targeting Rate", f"{stats['runs']['targeting_rate']}%")
        c3.metric("Pass Accuracy", f"{stats['possession']['pass_accuracy']}%")
        c4.metric("Pressings", stats["defense"]["pressings"])

        dna_df = pd.DataFrame([{"Dimension": k, "Percentile": v} for k, v in percentiles.items()])
        st.dataframe(
            dna_df.set_index("Dimension"), use_container_width=True,
            column_config={"Percentile": st.column_config.ProgressColumn(
                "Percentile", min_value=0, max_value=100, format="%.0f"
            )},
        )

        st.divider()
        st.markdown("### Scout Analysis")
        client = anthropic.Anthropic(api_key=api_key)
        stream_report(client, prompt)

        with st.expander("View raw prompt"):
            st.text(prompt)


if __name__ == "__main__":
    main()
