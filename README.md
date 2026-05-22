# Soccer Feature Engineering Hackathon

## Goal
Design and implement novel, interpretable soccer attributes (features) from play-by-play event data that describe team behavior, tactics, and performance beyond traditional box-score metrics. Think creatively.

## Objective
This is a creative feature engineering competition focused on soccer analytics. Rather than predicting outcomes, submissions are evaluated on:
- Original soccer insights
- Scientific reasoning and clarity
- Proper documentation
- Reproducible implementation

## Approach
- **Data Source**: SkillCorner Open Data (10 match samples with dynamic events and phases of play)
- **Feature Scope**: Match-level, team-level, or phase-of-play attributes that capture whole-game patterns
- **Implementation**: Dynamically read event data without hardcoding match IDs
- **Examples**: Passes to final third, territorial dominance, tempo/transition intensity, build-up progression, pressure proxies, set-piece indicators

## Data Structure
```
opendata/data/matches/[matchid]/[matchid]_dynamic_events.csv
opendata/data/matches/[matchid]/[matchid]_phases_of_play.csv
```

## Key Requirements
- Solutions must work with the data directory structure dynamically
- No hardcoded match IDs
- No external proprietary datasets
- Focus on feature design, not large-scale modeling