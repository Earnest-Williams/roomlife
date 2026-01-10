"""Shared constants for the RoomLife engine."""

from __future__ import annotations

# Time slices in a day
TIME_SLICES = ["morning", "afternoon", "evening", "night"]

# All skill names in the system
SKILL_NAMES = [
    "technical_literacy",
    "analysis",
    "resource_management",
    "presence",
    "articulation",
    "persuasion",
    "nutrition",
    "maintenance",
    "ergonomics",
    "reflexivity",
    "introspection",
    "focus",
]

# Mapping of skills to their governing aptitudes
SKILL_TO_APTITUDE = {
    "technical_literacy": "logic_systems",
    "analysis": "logic_systems",
    "resource_management": "logic_systems",
    "presence": "social_grace",
    "articulation": "social_grace",
    "persuasion": "social_grace",
    "nutrition": "domesticity",
    "maintenance": "domesticity",
    "ergonomics": "domesticity",
    "reflexivity": "vitality",
    "introspection": "vitality",
    "focus": "vitality",
}

# Trait drift configuration
TRAIT_DRIFT_THRESHOLD = 80
TRAIT_DRIFT_CONFIGS = [
    {
        "habit": "discipline",
        "trait": "discipline",
        "message": "Your surroundings feel more orderly. Discipline is rising.",
    },
    {
        "habit": "confidence",
        "trait": "confidence",
        "message": "You feel more self-assured. Confidence is rising.",
    },
    {
        "habit": "frugality",
        "trait": "frugality",
        "message": "You're becoming more mindful of spending. Frugality is rising.",
    },
]

# Maximum event log entries to keep (prevents unbounded growth)
MAX_EVENT_LOG = 100

# Health system constants
HEALTH_EXTREME_NEED_THRESHOLD = 80  # Needs above this cause health degradation
HEALTH_DEGRADATION_PER_EXTREME_NEED = 2  # Health lost per extreme need per turn
ILLNESS_RECOVERY_PER_TURN = 1  # Natural illness recovery per turn
INJURY_RECOVERY_PER_TURN = 0.5  # Natural injury recovery per turn (slower than illness)
HEALTH_PENALTY_THRESHOLD = 50  # Below this health, actions have penalties
DOCTOR_VISIT_COST = 5000  # Cost of doctor visit in pence
DOCTOR_ILLNESS_RECOVERY = 40  # Illness recovered from doctor visit
DOCTOR_INJURY_RECOVERY = 20  # Injury recovered from doctor visit
REST_ILLNESS_RECOVERY = 10  # Illness recovered from rest action
REST_INJURY_RECOVERY = 5  # Injury recovered from rest action
