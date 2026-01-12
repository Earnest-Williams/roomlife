"""Shared constants for the RoomLife engine."""

from __future__ import annotations

# Time slices in a day
TIME_SLICES = ["morning", "afternoon", "evening", "night"]

# All skill names in the system
SKILL_NAMES = [
    "cooking",
    "bartending",
    "technical_literacy",
    "analysis",
    "creativity",
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
    "cooking": "body",
    "bartending": "social_grace",
    "technical_literacy": "logic_systems",
    "analysis": "logic_systems",
    "creativity": "logic_systems",
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
    {
        "habit": "fitness",
        "trait": "fitness",
        "message": "Your body feels stronger. Fitness is rising.",
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

# Job System
JOBS = {
    "bartender": {
        "name": "Bartender",
        "base_pay": 4200,
        "requirements": {
            "skills": [
                {"name": "bartending", "min": 20},
            ],
            "traits": [
                {"name": "charisma", "min": 50},
            ],
            "require_all": True,
        },
        "description": "Serve drinks and manage the bar. Requires bartending skills and charm.",
        "skill_gains": {
            "bartending": 1.0,
            "presence": 0.3,
        },
        "fatigue_cost": 12,
    },
    "recycling_collector": {
        "name": "Recycling Collector",
        "base_pay": 2400,  # Barely covers bills (2000p) with minimal saving
        "requirements": {},  # No requirements - starter job
        "description": "Collect and sort recyclables. It's honest work, but barely pays the bills.",
        "skill_gains": {
            "maintenance": 0.5,
            "fitness": 0.3,
        },
        "fatigue_cost": 18,  # Physically demanding
    },
    "warehouse_worker": {
        "name": "Warehouse Worker",
        "base_pay": 3800,
        "requirements": {
            "skills": [
                {"name": "reflexivity", "min": 15},  # Need decent reflexes
            ],
            "traits": [
                {"name": "fitness", "min": 20},  # Or basic fitness
            ],
            "require_all": False,  # Either skill OR trait is enough
        },
        "description": "Stock shelves and move inventory. Better pay but still demanding work.",
        "skill_gains": {
            "technical_literacy": 1.0,
            "maintenance": 0.8,
        },
        "fatigue_cost": 16,
    },
    "office_assistant": {
        "name": "Office Assistant",
        "base_pay": 5500,
        "requirements": {
            "skills": [
                {"name": "technical_literacy", "min": 30},
                {"name": "presence", "min": 20},
            ],
            "require_all": True,  # Need both skills
        },
        "description": "Answer calls, manage schedules, handle paperwork. Professional environment.",
        "skill_gains": {
            "technical_literacy": 1.5,
            "articulation": 1.0,
            "presence": 0.5,
        },
        "fatigue_cost": 14,
    },
    "junior_developer": {
        "name": "Junior Developer",
        "base_pay": 8000,
        "requirements": {
            "skills": [
                {"name": "technical_literacy", "min": 60},
                {"name": "focus", "min": 40},
            ],
            "items": [
                {"tag": "certification"},  # Need training/certification
            ],
            "require_all": True,
        },
        "description": "Write code and fix bugs. Requires certification and strong technical skills.",
        "skill_gains": {
            "technical_literacy": 2.5,
            "analysis": 1.5,
            "focus": 1.0,
        },
        "fatigue_cost": 15,
    },
    "senior_developer": {
        "name": "Senior Developer",
        "base_pay": 15000,
        "requirements": {
            "skills": [
                {"name": "technical_literacy", "min": 90},
                {"name": "analysis", "min": 70},
                {"name": "focus", "min": 60},
            ],
            "items": [
                {"tag": "certification"},
                {"tag": "laptop"},  # Need professional equipment
            ],
            "require_all": True,
        },
        "description": "Lead projects and mentor juniors. Excellent pay for experienced professionals.",
        "skill_gains": {
            "technical_literacy": 3.0,
            "analysis": 2.0,
            "articulation": 1.0,
        },
        "fatigue_cost": 16,  # Mental fatigue from responsibility
    },
}
