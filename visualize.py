"""
Soccer Feature Engineering — Visualizations
Run after features.py to generate charts in the charts/ directory.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
import os

os.makedirs("charts", exist_ok=True)

df = pd.read_csv("features.csv")

# Attach team shortnames from events for readable labels
import json, os as _os

with open("opendata/data/matches.json") as f:
    matches_meta = json.load(f)

id_to_name = {}
for m in matches_meta:
    for side in ('home_team', 'away_team'):
        t = m[side]
        id_to_name[t['id']] = t.get('short_name') or t.get('name', str(t['id']))

df['team_name'] = df['team_id'].map(id_to_name).fillna(df['team_id'].astype(str))

# Aggregate across all matches per team
agg = df.groupby('team_name').mean(numeric_only=True).reset_index()


# ── 1. RADAR CHART ──────────────────────────────────────────────────────────
RADAR_FEATURES = [
    ('press_disruption_rate',   'Press\nDisruption Rate'),
    ('high_speed_press_ratio',  'High-Speed\nPress Ratio'),
    ('build_up_to_finish_rate', 'Build-up→\nFinish Rate'),
    ('shot_creation_rate',      'Shot\nCreation Rate'),
    ('run_diversity_index',     'Run\nDiversity'),
    ('vertical_tempo_score',    'Vertical\nTempo'),
    ('possession_loss_rate',    'Possession\nLoss Rate'),
    ('chaos_index',             'Chaos\nIndex'),
]

keys = [f[0] for f in RADAR_FEATURES]
labels = [f[1] for f in RADAR_FEATURES]
N = len(keys)
angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
angles += angles[:1]  # close the polygon

# Normalise each feature 0–1 across all teams
norm = agg[keys].copy()
for col in keys:
    mn, mx = norm[col].min(), norm[col].max()
    norm[col] = (norm[col] - mn) / (mx - mn) if mx > mn else 0.0

teams = agg['team_name'].tolist()
colors = plt.cm.tab10(np.linspace(0, 1, len(teams)))

fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

for i, team in enumerate(teams):
    vals = norm.loc[agg['team_name'] == team, keys].values.flatten().tolist()
    vals += vals[:1]
    ax.plot(angles, vals, color=colors[i], linewidth=1.8, label=team)
    ax.fill(angles, vals, color=colors[i], alpha=0.08)

ax.set_xticks(angles[:-1])
ax.set_xticklabels(labels, size=9)
ax.set_yticks([0.25, 0.5, 0.75, 1.0])
ax.set_yticklabels(['25%', '50%', '75%', '100%'], size=7, color='grey')
ax.set_title("Team Tactical Profiles (normalised)", size=13, pad=20)
ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.15), fontsize=8, framealpha=0.7)
plt.tight_layout()
plt.savefig("charts/radar_team_profiles.png", dpi=150, bbox_inches='tight')
plt.close()
print("Saved: charts/radar_team_profiles.png")


# ── 2. TACTICAL QUADRANT SCATTER ────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 7))

x = agg['press_disruption_rate']
y = agg['build_up_to_finish_rate']

ax.scatter(x, y, s=120, c=colors[:len(agg)], zorder=3, edgecolors='white', linewidths=0.8)

for _, row in agg.iterrows():
    ax.annotate(row['team_name'],
                xy=(row['press_disruption_rate'], row['build_up_to_finish_rate']),
                xytext=(5, 5), textcoords='offset points', fontsize=8)

xm, ym = x.mean(), y.mean()
ax.axvline(xm, color='grey', linewidth=0.8, linestyle='--', alpha=0.6)
ax.axhline(ym, color='grey', linewidth=0.8, linestyle='--', alpha=0.6)

ax.text(x.max(), y.max(), "Elite\n(press well + convert)", fontsize=7.5,
        ha='right', va='top', color='green', alpha=0.7)
ax.text(x.min(), y.max(), "Patient builders\n(convert without pressing)", fontsize=7.5,
        ha='left', va='top', color='blue', alpha=0.7)
ax.text(x.max(), y.min(), "High-press, low\nconversion", fontsize=7.5,
        ha='right', va='bottom', color='orange', alpha=0.7)
ax.text(x.min(), y.min(), "Passive & inefficient", fontsize=7.5,
        ha='left', va='bottom', color='red', alpha=0.7)

ax.set_xlabel("Press Disruption Rate", fontsize=11)
ax.set_ylabel("Build-up → Finish Rate", fontsize=11)
ax.set_title("Tactical Quadrant: Pressing Quality vs Attacking Progression", fontsize=12)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("charts/tactical_quadrant.png", dpi=150)
plt.close()
print("Saved: charts/tactical_quadrant.png")


# ── 3. H1 vs H2 PRESS INTENSITY SHIFT ───────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 5))

agg_sorted = agg.sort_values('press_intensity_shift', ascending=True)
bar_colors = ['#e74c3c' if v < 0 else '#2ecc71' for v in agg_sorted['press_intensity_shift']]

bars = ax.barh(agg_sorted['team_name'], agg_sorted['press_intensity_shift'],
               color=bar_colors, edgecolor='white', height=0.6)
ax.axvline(0, color='black', linewidth=0.8)
ax.set_xlabel("H2 High-Speed Press Intensity − H1 (higher = more pressing in 2nd half)", fontsize=10)
ax.set_title("Late-Game Pressing Momentum Shift", fontsize=12)
ax.grid(axis='x', alpha=0.3)

green_patch = mpatches.Patch(color='#2ecc71', label='Pressed harder in H2')
red_patch = mpatches.Patch(color='#e74c3c', label='Dropped intensity in H2')
ax.legend(handles=[green_patch, red_patch], fontsize=9)

plt.tight_layout()
plt.savefig("charts/press_intensity_shift.png", dpi=150)
plt.close()
print("Saved: charts/press_intensity_shift.png")


# ── 4. RUN DIVERSITY vs SHOT CREATION RATE ───────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 6))

ax.scatter(agg['run_diversity_index'], agg['shot_creation_rate'],
           s=agg['total_off_ball_runs'] * 1.5,  # bubble size = run volume
           c=colors[:len(agg)], zorder=3, edgecolors='white', linewidths=0.8, alpha=0.85)

for _, row in agg.iterrows():
    ax.annotate(row['team_name'],
                xy=(row['run_diversity_index'], row['shot_creation_rate']),
                xytext=(6, 4), textcoords='offset points', fontsize=8)

ax.set_xlabel("Run Diversity Index (Shannon entropy of run types)", fontsize=11)
ax.set_ylabel("Shot Creation Rate (phases leading to shot / total phases)", fontsize=11)
ax.set_title("Off-ball Movement Diversity vs Shot Creation\n(bubble size = total off-ball runs)", fontsize=11)
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("charts/run_diversity_vs_shots.png", dpi=150)
plt.close()
print("Saved: charts/run_diversity_vs_shots.png")


# ── 5. STACKED BAR: PHASE TYPE DISTRIBUTION ──────────────────────────────────
phase_cols = ['phases_build_up', 'phases_create', 'phases_finish',
              'phases_direct', 'phases_quick_break', 'phases_chaotic',
              'phases_transition', 'phases_set_play']
phase_labels = ['Build-up', 'Create', 'Finish', 'Direct',
                'Quick Break', 'Chaotic', 'Transition', 'Set Play']
phase_colors = ['#3498db', '#2ecc71', '#e74c3c', '#f39c12',
                '#9b59b6', '#e67e22', '#1abc9c', '#95a5a6']

phase_data = agg[['team_name'] + phase_cols].set_index('team_name')
# Normalise to 100% per team
phase_pct = phase_data.div(phase_data.sum(axis=1), axis=0) * 100

fig, ax = plt.subplots(figsize=(12, 6))
bottom = np.zeros(len(phase_pct))
for col, label, color in zip(phase_cols, phase_labels, phase_colors):
    ax.bar(phase_pct.index, phase_pct[col], bottom=bottom, label=label,
           color=color, edgecolor='white', linewidth=0.4)
    bottom += phase_pct[col].values

ax.set_ylabel("Phase Distribution (%)", fontsize=11)
ax.set_title("Possession Phase Profile by Team", fontsize=12)
ax.legend(loc='upper right', bbox_to_anchor=(1.15, 1), fontsize=9)
plt.xticks(rotation=30, ha='right', fontsize=9)
ax.set_ylim(0, 105)
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig("charts/phase_distribution.png", dpi=150, bbox_inches='tight')
plt.close()
print("Saved: charts/phase_distribution.png")

print("\nAll charts saved to charts/")
