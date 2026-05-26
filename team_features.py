import pandas as pd
import os

DATA_PATH = "opendata/data/matches"

all_events, all_phases = [], []
for match_id in os.listdir(DATA_PATH):
    ef = f"{DATA_PATH}/{match_id}/{match_id}_dynamic_events.csv"
    pf = f"{DATA_PATH}/{match_id}/{match_id}_phases_of_play.csv"
    if os.path.exists(ef):
        all_events.append(pd.read_csv(ef, low_memory=False))
    if os.path.exists(pf):
        all_phases.append(pd.read_csv(pf, low_memory=False))

events = pd.concat(all_events, ignore_index=True)
phases = pd.concat(all_phases, ignore_index=True)

# FEATURE 1: Press intensity per team
presses = events[events['event_type'] == 'on_ball_engagement']
press_counts = presses.groupby('team_shortname').size().reset_index(name='total_presses')
possessions = events[events['event_type'] == 'player_possession']
poss_counts = possessions.groupby('team_shortname').size().reset_index(name='total_possessions')
press_intensity = press_counts.merge(poss_counts, on='team_shortname')
press_intensity['press_intensity'] = (press_intensity['total_presses'] / press_intensity['total_possessions']).round(3)

# FEATURE 2: Off-ball run creativity
runs = events[events['event_type'] == 'off_ball_run']
run_types = runs.groupby(['team_shortname', 'event_subtype']).size().unstack(fill_value=0).reset_index()

# FEATURE 3: Phase progression - how often build_up leads to finish
team_phases = phases.groupby(['team_in_possession_shortname', 'team_in_possession_phase_type']).size().unstack(fill_value=0).reset_index()

print("=" * 50)
print("FEATURE 1: PRESS INTENSITY BY TEAM")
print("=" * 50)
print(press_intensity.sort_values('press_intensity', ascending=False).to_string(index=False))

print("\n" + "=" * 50)
print("FEATURE 2: OFF-BALL RUN TYPES BY TEAM")
print("=" * 50)
print(run_types.to_string(index=False))

print("\n" + "=" * 50)
print("FEATURE 3: PHASE TYPES BY TEAM")
print("=" * 50)
print(team_phases.to_string(index=False))
