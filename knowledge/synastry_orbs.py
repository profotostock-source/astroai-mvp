# Orbs in degrees for synastry aspects
SYNASTRY_ORBS = {
    "conjunction": 8,
    "opposition": 8,
    "trine": 7,
    "square": 7,
    "sextile": 5,
}

# Aspect angles in degrees
ASPECT_ANGLES = {
    "conjunction": 0,
    "opposition": 180,
    "trine": 120,
    "square": 90,
    "sextile": 60,
}

# Aspect weights for evidence ranking (higher = more important)
ASPECT_WEIGHTS = {
    ("sun", "moon"): 10,
    ("moon", "moon"): 10,
    ("venus", "mars"): 9,
    ("sun", "venus"): 8,
    ("moon", "venus"): 8,
    ("venus", "venus"): 8,
    ("mercury", "mercury"): 7,
    ("moon", "saturn"): 7,
    ("sun", "saturn"): 7,
    ("venus", "saturn"): 6,
    ("mars", "saturn"): 6,
    ("sun", "sun"): 6,
    ("mars", "mars"): 5,
    ("jupiter", "sun"): 5,
    ("jupiter", "moon"): 5,
}

# Type weight modifiers
TYPE_WEIGHTS = {
    "conjunction": 1.0,
    "opposition": 0.9,
    "trine": 0.85,
    "square": 0.85,
    "sextile": 0.7,
}
