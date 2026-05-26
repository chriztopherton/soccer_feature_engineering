import pandas as pd
import os
import json

DATA_PATH = "opendata/data/matches"

with open("opendata/data/matches.json") as f:
    matches_meta = json.load(f)

def load_match(match_id):
    ef = f"{DATA_PATH}/{match_id}/{match_id}_dynamic_events.csv"
    pf = f"{DATA_PATH}/{match_id}/{match_id}_phases_of_play.csv"
    return pd.read_csv(ef, low_memory=False), pd.read_csv(pf, low_memory=False)

def build_features(match_id, team_id, events, phases):
    e = events[events['team_id'] == team_id]
    p = phases[phases['team_in_possession_id'] == team_id]
    presses = e[e['event_type'] == 'on_ball_engagement']
    runs = e[e['event_type'] == 'off_ball_run']
    poss = e[e['event_type'] == 'player_possession']

    # ── PRESSING FEATURES ──────────────────────────────────────────────
    # Total pressing actions by this team
    total_presses = len(presses)

    # Presses performed at high speed (hsr/sprinting) — measures press intensity
    high_speed_presses = len(presses[presses['speed_avg_band'].isin(['hsr', 'sprinting'])])

    # Presses that ended in disrupting the opponent — measures press effectiveness
    press_disruptions = len(presses[presses['pressing_chain_end_type'] == 'disruption'])

    # Recovery presses (pressing immediately after losing ball) — counter-press measure
    recovery_press_count = len(presses[presses['event_subtype'] == 'recovery_press'])

    # Presses in the opponent's attacking third — measures how high up the team presses
    high_press_count = len(presses[presses['third_start'] == 'attacking_third'])

    # Coordinated press chains (2+ players pressing together)
    coordinated_press_chains = len(presses[presses['pressing_chain_length'] >= 2]) if 'pressing_chain_length' in presses.columns else 0

    # Presses that forced the opponent backward
    press_force_backward = int(presses['force_backward'].sum()) if 'force_backward' in presses.columns else 0

    # ── OFF-BALL RUN FEATURES ───────────────────────────────────────────
    total_off_ball_runs = len(runs)

    # Runs that try to get behind the defense — most dangerous run type
    runs_behind_defense = len(runs[runs['event_subtype'] == 'behind'])

    # Runs ahead of the ball to create space
    runs_ahead_of_ball = len(runs[runs['event_subtype'] == 'run_ahead_of_the_ball'])

    # Width-creating runs — stretches opposition
    runs_pulling_wide = len(runs[runs['event_subtype'] == 'pulling_wide'])

    # Short support runs — maintains possession
    runs_coming_short = len(runs[runs['event_subtype'] == 'coming_short'])

    # Overlap runs — full backs joining attack
    runs_overlap = len(runs[runs['event_subtype'] == 'overlap'])

    # Underlap runs — inside attacking runs
    runs_underlap = len(runs[runs['event_subtype'] == 'underlap'])

    # Cross receiver positioning runs
    runs_cross_receiver = len(runs[runs['event_subtype'] == 'cross_receiver'])

    # Dropping off to receive (false 9 / dropping striker)
    runs_dropping_off = len(runs[runs['event_subtype'] == 'dropping_off'])

    # Runs that successfully broke the defensive line — elite attacking movement
    line_breaking_runs = int(runs['break_defensive_line'].sum()) if 'break_defensive_line' in runs.columns else 0

    # Simultaneous runs (2+ runs at same time) — coordinated attacking movement
    simultaneous_runs = int(runs['n_simultaneous_runs'].sum()) if 'n_simultaneous_runs' in runs.columns else 0

    # ── PHASE OF PLAY FEATURES ──────────────────────────────────────────
    phases_build_up     = len(p[p['team_in_possession_phase_type'] == 'build_up'])
    phases_create       = len(p[p['team_in_possession_phase_type'] == 'create'])
    phases_finish       = len(p[p['team_in_possession_phase_type'] == 'finish'])
    phases_direct       = len(p[p['team_in_possession_phase_type'] == 'direct'])
    phases_chaotic      = len(p[p['team_in_possession_phase_type'] == 'chaotic'])
    phases_transition   = len(p[p['team_in_possession_phase_type'] == 'transition'])
    phases_quick_break  = len(p[p['team_in_possession_phase_type'] == 'quick_break'])
    phases_set_play     = len(p[p['team_in_possession_phase_type'] == 'set_play'])

    # Phases that led to a shot — attacking threat
    phases_lead_to_shot = int(p['team_possession_lead_to_shot'].sum())

    # Phases that led to a goal — finishing efficiency
    phases_lead_to_goal = int(p['team_possession_lead_to_goal'].sum())

    # Phases where possession was lost — turnover volume
    phases_possession_loss = int(p['team_possession_loss_in_phase'].sum())

    # NOVEL: Phases that skipped create and went directly build_up → finish
    # Measures vertical/direct play style
    direct_buildup_to_finish = len(p[
        (p['team_in_possession_phase_type'] == 'finish') &
        (p['team_in_possession_previous_phase_type'] == 'build_up')
    ]) if 'team_in_possession_previous_phase_type' in p.columns else 0

    # NOVEL: Set play phases that led to a shot — dead ball threat
    set_play_shots = len(p[
        (p['team_in_possession_phase_type'] == 'set_play') &
        (p['team_possession_lead_to_shot'] == True)
    ])

    # NOVEL: Quick break phases that led to shots — counter-attack danger
    quick_break_shots = len(p[
        (p['team_in_possession_phase_type'] == 'quick_break') &
        (p['team_possession_lead_to_shot'] == True)
    ])

    # ── SPEED & POSSESSION FEATURES ────────────────────────────────────
    # High speed running events — physical intensity
    total_hsr_events = len(e[e['speed_avg_band'] == 'hsr'])

    # Sprinting events — explosive effort count
    total_sprint_events = len(e[e['speed_avg_band'] == 'sprinting'])

    # Total player possessions
    total_player_possessions = len(poss)

    # One-touch plays — quick combination play
    one_touch_plays = int(poss['one_touch'].sum()) if 'one_touch' in poss.columns else 0

    # Quick passes — tempo of play
    quick_passes = int(poss['quick_pass'].sum()) if 'quick_pass' in poss.columns else 0

    # Forward momentum possessions — progressive play
    forward_possessions = int(poss['forward_momentum'].sum()) if 'forward_momentum' in poss.columns else 0

    # NOVEL: Possessions in attacking third — territorial dominance
    poss_in_attacking_third = len(poss[poss['third_start'] == 'attacking_third']) if 'third_start' in poss.columns else 0

    # NOVEL: Possessions that led to shots — shot-creating possessions
    possessions_lead_to_shot = int(poss['lead_to_shot'].sum()) if 'lead_to_shot' in poss.columns else 0

    # NOVEL: Dangerous passes attempted — quality of passing options chosen
    dangerous_passes = int(poss['dangerous'].sum()) if 'dangerous' in poss.columns else 0

    return {
        'match_id': match_id,
        'team_id': team_id,
        # Pressing
        'total_presses': total_presses,
        'high_speed_presses': high_speed_presses,
        'press_disruptions': press_disruptions,
        'recovery_press_count': recovery_press_count,
        'high_press_count': high_press_count,
        'coordinated_press_chains': coordinated_press_chains,
        'press_force_backward': press_force_backward,
        # Off-ball runs
        'total_off_ball_runs': total_off_ball_runs,
        'runs_behind_defense': runs_behind_defense,
        'runs_ahead_of_ball': runs_ahead_of_ball,
        'runs_pulling_wide': runs_pulling_wide,
        'runs_coming_short': runs_coming_short,
        'runs_overlap': runs_overlap,
        'runs_underlap': runs_underlap,
        'runs_cross_receiver': runs_cross_receiver,
        'runs_dropping_off': runs_dropping_off,
        'line_breaking_runs': line_breaking_runs,
        'simultaneous_runs': simultaneous_runs,
        # Phases
        'phases_build_up': phases_build_up,
        'phases_create': phases_create,
        'phases_finish': phases_finish,
        'phases_direct': phases_direct,
        'phases_chaotic': phases_chaotic,
        'phases_transition': phases_transition,
        'phases_quick_break': phases_quick_break,
        'phases_set_play': phases_set_play,
        'phases_lead_to_shot': phases_lead_to_shot,
        'phases_lead_to_goal': phases_lead_to_goal,
        'phases_possession_loss': phases_possession_loss,
        'direct_buildup_to_finish': direct_buildup_to_finish,
        'set_play_shots': set_play_shots,
        'quick_break_shots': quick_break_shots,
        # Speed & possession
        'total_hsr_events': total_hsr_events,
        'total_sprint_events': total_sprint_events,
        'total_player_possessions': total_player_possessions,
        'one_touch_plays': one_touch_plays,
        'quick_passes': quick_passes,
        'forward_possessions': forward_possessions,
        'poss_in_attacking_third': poss_in_attacking_third,
        'possessions_lead_to_shot': possessions_lead_to_shot,
        'dangerous_passes': dangerous_passes,
    }

all_rows = []
for match in matches_meta:
    match_id = str(match['id'])
    try:
        events, phases = load_match(match_id)
        all_rows.append(build_features(match_id, match['home_team']['id'], events, phases))
        all_rows.append(build_features(match_id, match['away_team']['id'], events, phases))
        print(f"✅ {match_id}")
    except Exception as ex:
        print(f"❌ {match_id}: {ex}")

df = pd.DataFrame(all_rows)
df.to_csv("features.csv", index=False)
print(f"\n✅ features.csv: {len(df)} rows, {len(df.columns)} columns")
print(df.head(2).to_string())