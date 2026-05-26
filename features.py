import pandas as pd
import numpy as np
import os
import json
from scipy.stats import entropy

DATA_PATH = "opendata/data/matches"

with open("opendata/data/matches.json") as f:
    matches_meta = json.load(f)

def load_match(match_id):
    ef = f"{DATA_PATH}/{match_id}/{match_id}_dynamic_events.csv"
    pf = f"{DATA_PATH}/{match_id}/{match_id}_phases_of_play.csv"
    return pd.read_csv(ef, low_memory=False), pd.read_csv(pf, low_memory=False)

def run_diversity_index(runs):
    """Shannon entropy of off-ball run subtypes — higher = more unpredictable movement."""
    if len(runs) == 0:
        return 0.0
    counts = runs['event_subtype'].value_counts().values
    return round(float(entropy(counts, base=2)), 4)

def press_features_by_period(presses, period):
    p = presses[presses['period'] == period]
    total = len(p)
    high_speed = len(p[p['speed_avg_band'].isin(['hsr', 'sprinting'])])
    return total, high_speed

def build_features(match_id, team_id, events, phases):
    e = events[events['team_id'] == team_id].copy()
    p = phases[phases['team_in_possession_id'] == team_id].copy()

    presses = e[e['event_type'] == 'on_ball_engagement']
    runs = e[e['event_type'] == 'off_ball_run']
    poss = e[e['event_type'] == 'player_possession']

    total_presses = len(presses)
    press_disruptions = len(presses[presses['pressing_chain_end_type'] == 'disruption'])
    press_regains = len(presses[presses['pressing_chain_end_type'] == 'regain'])
    high_speed_presses = len(presses[presses['speed_avg_band'].isin(['hsr', 'sprinting'])])

    total_phases = len(p)
    phases_build_up = len(p[p['team_in_possession_phase_type'] == 'build_up'])
    phases_create = len(p[p['team_in_possession_phase_type'] == 'create'])
    phases_finish = len(p[p['team_in_possession_phase_type'] == 'finish'])
    phases_direct = len(p[p['team_in_possession_phase_type'] == 'direct'])
    phases_chaotic = len(p[p['team_in_possession_phase_type'] == 'chaotic'])
    phases_transition = len(p[p['team_in_possession_phase_type'] == 'transition'])
    phases_quick_break = len(p[p['team_in_possession_phase_type'] == 'quick_break'])
    phases_set_play = len(p[p['team_in_possession_phase_type'] == 'set_play'])
    phases_lead_to_shot = int(p['team_possession_lead_to_shot'].sum())
    phases_lead_to_goal = int(p['team_possession_lead_to_goal'].sum())
    phases_possession_loss = int(p['team_possession_loss_in_phase'].sum())

    # --- Ratio / derived features ---

    # How often pressing leads to a disruption (quality of press)
    press_disruption_rate = round(press_disruptions / total_presses, 4) if total_presses > 0 else 0.0

    # How often pressing directly wins the ball back
    press_regain_rate = round(press_regains / total_presses, 4) if total_presses > 0 else 0.0

    # What proportion of presses are high-intensity (hsr + sprint)
    high_speed_press_ratio = round(high_speed_presses / total_presses, 4) if total_presses > 0 else 0.0

    # How often build-up phases progress to a finish phase
    build_up_to_finish_rate = round(phases_finish / phases_build_up, 4) if phases_build_up > 0 else 0.0

    # Proportion of phases that lead to a shot
    shot_creation_rate = round(phases_lead_to_shot / total_phases, 4) if total_phases > 0 else 0.0

    # Proportion of phases that end in possession loss
    possession_loss_rate = round(phases_possession_loss / total_phases, 4) if total_phases > 0 else 0.0

    # Vertical tempo: direct + quick-break phases as share of all phases
    # High = team plays fast/direct; low = patient build-up
    vertical_tempo_score = round((phases_direct + phases_quick_break) / total_phases, 4) if total_phases > 0 else 0.0

    # Chaos index: chaotic phases as share of all phases
    chaos_index = round(phases_chaotic / total_phases, 4) if total_phases > 0 else 0.0

    # Average pitch territory where phases start (0=own goal, 100=opp goal)
    avg_phase_start_x = round(p['x_start'].mean(), 2) if len(p) > 0 else np.nan

    # Average phase width (how wide the team spreads during possession)
    avg_phase_width = round(p['team_in_possession_width_start'].mean(), 2) if 'team_in_possession_width_start' in p.columns and len(p) > 0 else np.nan

    # Shannon entropy of off-ball run types — unpredictability of movement
    run_diversity = run_diversity_index(runs)

    # --- Temporal features: H1 vs H2 pressing ---
    presses_h1_total, presses_h1_hs = press_features_by_period(presses, 1)
    presses_h2_total, presses_h2_hs = press_features_by_period(presses, 2)

    h1_press_intensity = round(presses_h1_hs / presses_h1_total, 4) if presses_h1_total > 0 else 0.0
    h2_press_intensity = round(presses_h2_hs / presses_h2_total, 4) if presses_h2_total > 0 else 0.0
    # Positive = team pressed harder in H2 (late-game urgency); negative = dropped intensity
    press_intensity_shift = round(h2_press_intensity - h1_press_intensity, 4)

    # H2 run volume uplift: did the team create more off-ball movement in H2?
    runs_h1 = len(runs[runs['period'] == 1])
    runs_h2 = len(runs[runs['period'] == 2])
    run_volume_shift = runs_h2 - runs_h1

    total_player_possessions = len(poss)
    one_touch_plays = int(poss['one_touch'].sum()) if 'one_touch' in poss.columns else 0
    quick_passes = int(poss['quick_pass'].sum()) if 'quick_pass' in poss.columns else 0
    forward_possessions = int(poss['forward_momentum'].sum()) if 'forward_momentum' in poss.columns else 0

    return {
        'match_id': match_id,
        'team_id': team_id,

        # Raw counts
        'total_presses': total_presses,
        'high_speed_presses': high_speed_presses,
        'press_disruptions': press_disruptions,
        'press_regains': press_regains,
        'recovery_press_count': len(presses[presses['event_subtype'] == 'recovery_press']),
        'total_off_ball_runs': len(runs),
        'runs_behind_defense': len(runs[runs['event_subtype'] == 'behind']),
        'runs_ahead_of_ball': len(runs[runs['event_subtype'] == 'run_ahead_of_the_ball']),
        'runs_pulling_wide': len(runs[runs['event_subtype'] == 'pulling_wide']),
        'runs_coming_short': len(runs[runs['event_subtype'] == 'coming_short']),
        'runs_overlap': len(runs[runs['event_subtype'] == 'overlap']),
        'runs_underlap': len(runs[runs['event_subtype'] == 'underlap']),
        'runs_cross_receiver': len(runs[runs['event_subtype'] == 'cross_receiver']),
        'runs_dropping_off': len(runs[runs['event_subtype'] == 'dropping_off']),
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
        'total_hsr_events': len(e[e['speed_avg_band'] == 'hsr']),
        'total_sprint_events': len(e[e['speed_avg_band'] == 'sprinting']),
        'total_player_possessions': total_player_possessions,
        'one_touch_plays': one_touch_plays,
        'quick_passes': quick_passes,
        'forward_possessions': forward_possessions,

        # Ratio / quality features
        'press_disruption_rate': press_disruption_rate,
        'press_regain_rate': press_regain_rate,
        'high_speed_press_ratio': high_speed_press_ratio,
        'build_up_to_finish_rate': build_up_to_finish_rate,
        'shot_creation_rate': shot_creation_rate,
        'possession_loss_rate': possession_loss_rate,
        'vertical_tempo_score': vertical_tempo_score,
        'chaos_index': chaos_index,
        'avg_phase_start_x': avg_phase_start_x,
        'avg_phase_width': avg_phase_width,
        'run_diversity_index': run_diversity,

        # Temporal / momentum features
        'h1_press_intensity': h1_press_intensity,
        'h2_press_intensity': h2_press_intensity,
        'press_intensity_shift': press_intensity_shift,
        'runs_h1': runs_h1,
        'runs_h2': runs_h2,
        'run_volume_shift': run_volume_shift,
    }

all_rows = []
for match in matches_meta:
    match_id = str(match['id'])
    try:
        events, phases = load_match(match_id)
        all_rows.append(build_features(match_id, match['home_team']['id'], events, phases))
        all_rows.append(build_features(match_id, match['away_team']['id'], events, phases))
        print(f"Done: {match_id}")
    except Exception as ex:
        print(f"Failed: {match_id}: {ex}")

df = pd.DataFrame(all_rows)
df.to_csv("features.csv", index=False)
print(f"\nfeatures.csv saved: {len(df)} rows, {len(df.columns)} columns")
