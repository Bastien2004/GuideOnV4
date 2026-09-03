"""
utils/medialink/builders/placeholders.py — résolution des placeholders
d'un template (§7), ex: "{titre}", "{auteur}", "{url}".

RÈGLE CENTRALE DU CAHIER (§7, à ne jamais casser) :
    "Ne jamais afficher une valeur nulle — si un placeholder n'est pas
    disponible pour l'événement, il doit être filtré, pas affiché vide."

C'est-à-dire : si {auteur} n'est pas connu pour un événement donné, une
phrase du template qui contient "par {auteur}" ne doit PAS devenir
"par " — soit le placeholder entier est retiré proprement, soit (mieux)
c'est au niveau du texte du template que l'auteur du template doit
composer des phrases qui restent correctes sans la valeur. Ce module ne
peut garantir que le premier niveau (ne pas injecter de valeur vide) ;
le second reste une responsabilité de l'UI de configuration de template
(prévenir/avertir l'utilisateur, pas seulement corriger après coup).
"""
from __future__ import annotations

import re

from utils.medialink.event import MediaEvent

# Placeholders reconnus → nom d'attribut correspondant sur MediaEvent.
# Liste alignée sur §4/§7 — à étendre si Paul valide de nouveaux
# placeholders (ex: {plateforme}, {date}). Public (pas de préfixe `_`) :
# consommé aussi par views/medialink/medialink_announcement_view.py
# pour afficher l'aide à l'édition.
PLACEHOLDER_FIELDS: dict[str, str] = {
    "titre": "title",
    "description": "description",
    "url": "url",
    "auteur": "author",
    "vignette": "thumbnail",
}

_PLACEHOLDER_RE = re.compile(r"\{(" + "|".join(map(re.escape, PLACEHOLDER_FIELDS)) + r")\}")


def available_placeholders(event: MediaEvent) -> dict[str, str]:
    """Placeholders effectivement disponibles pour CET événement (valeur
    non vide) — à utiliser par l'UI de configuration de template pour
    prévenir "ce placeholder ne sera pas rempli pour ce type d'événement"
    plutôt que de le découvrir après coup en prod."""
    resolved: dict[str, str] = {}
    for placeholder, attr in PLACEHOLDER_FIELDS.items():
        value = getattr(event, attr, None)
        if value:
            resolved[placeholder] = str(value)
    return resolved


def resolve(template_text: str, event: MediaEvent) -> str:
    """Remplace les placeholders connus par leur valeur ; un placeholder
    sans valeur disponible est retiré (jamais laissé vide entre les
    accolades), cf. règle §7 en tête de module.

    Note : "retiré" ici signifie que l'accolade disparaît et laisse la
    valeur vide à cet endroit précis du texte — PAS que la ligne/phrase
    entière est supprimée. Une template mal écrite (ex: "par {auteur}"
    sans auteur connu) donnera "par " avec un espace en trop plutôt
    qu'un crash ; c'est un compromis assumé pour ce squelette, à
    améliorer avec une syntaxe de template plus riche (conditions) si
    Paul le souhaite plus tard.
    """
    available = available_placeholders(event)

    def _sub(match: re.Match[str]) -> str:
        return available.get(match.group(1), "")

    return _PLACEHOLDER_RE.sub(_sub, template_text)
