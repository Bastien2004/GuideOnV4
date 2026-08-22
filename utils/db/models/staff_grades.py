"""
utils/db/models/alpha_staff.py — Constantes partagées du système de grades
staff (labels, emojis, ordre, statuts secondaires).
"""

from __future__ import annotations

GRADES_ORDER: list[str] = [
    "administrateur",
    "super_moderateur",
    "moderateur_plus",
    "moderateur_confirme",
    "moderateur_test",
    "guide",
]

GRADE_LABELS: dict[str, str] = {
    "administrateur":      "Administrateur",
    "super_moderateur":    "Super Modérateur",
    "moderateur_plus":     "Modérateur+",
    "moderateur_confirme": "Modérateur Confirmé",
    "moderateur_test":     "Modérateur (Test)",
    "guide":               "Guide",
}

GRADE_EMOJIS: dict[str, str] = {
    "administrateur":      "<:Administrateur:1493513024919568514>",
    "super_moderateur":    "<:SuperModerateur:1493513047778791446>",
    "moderateur_plus":     "<:Moderateur:1493513069039714335>",
    "moderateur_confirme": "<:Moderateur:1493513069039714335>",
    "moderateur_test":     "<:Moderateur:1493513069039714335>",
    "guide":               "<:Guide:1493513088610209822>",
}

GRADE_PREFIXES: dict[str, str] = {
    "administrateur":      "Admin",
    "super_moderateur":    "SM",
    "moderateur_plus":     "Modo+",
    "moderateur_confirme": "Modo",
    "moderateur_test":     "Modo",
    "guide":               "Guide",
}

GRADE_TO_ROLE_ATTR: dict[str, str] = {
    "administrateur":      "role_administrateur_id",
    "super_moderateur":    "role_super_moderateur_id",
    "moderateur_plus":     "role_moderateur_plus_id",
    "moderateur_confirme": "role_moderateur_confirme_id",
    "moderateur_test":     "role_moderateur_test_id",
    "guide":               "role_guide_id",
}

# 🔰 Grades couverts par le rôle "équipe" transverse (role_equipe_id).

STAFF_GENERAL_GRADES: set[str] = {"guide", "moderateur_test", "moderateur_confirme", "moderateur_plus"}
STATUTS_SECONDAIRES_ORDER: list[str] = ["journaliste", "affilie", "builder"]
STATUT_INCOMPATIBLE_GRADES: set[str] = {"administrateur", "super_moderateur"}

SECONDARY_STATUSES: dict[str, dict] = {
    "journaliste": {
        "label": "Journaliste",
        "badge": "📰",
        "role_attr": "role_journaliste_id",
        "has_second_pseudo": False,
    },
    "affilie": {
        "label": "Affilié",
        "badge": "🎥",
        "role_attr": "role_affilie_id",
        "has_second_pseudo": False,
    },
    "builder": {
        "label": "Builder",
        "badge": None,
        "role_attr": "role_builder_id",
        "has_second_pseudo": True,
    },
}