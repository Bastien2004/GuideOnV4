"""
utils/automod/detectors/antispam_msg.py — Décision Anti Spam Message.

Fonction pure : ne fait AUCUN accès à un buffer ni à discord.py — elle reçoit
juste le nombre d'occurrences déjà comptées par
utils.automod.antispam_msg_buffer.register_and_count() (le comptage stateful
vit dans ce module dédié, cf. sa docstring) et décide si ça dépasse le seuil
configuré.

Extraite en fonction pure séparée pour rester testable en isolation, comme
tous les autres détecteurs automod, même si la partie "stateful" (le
comptage réel du contenu répété) vit ailleurs pour ce système précis — un
comptage cross-salons ne peut, par nature, pas être une fonction pure sur un
seul message.

Tests (exemples — à coller tels quels dans un fichier pytest si besoin) :

    assert detect(occurrences=1, max_messages=3) is None
    assert detect(occurrences=2, max_messages=3) is None
    assert detect(occurrences=3, max_messages=3) == "3 messages identiques"
    assert detect(occurrences=5, max_messages=3) == "5 messages identiques"
    assert detect(occurrences=0, max_messages=3) is None   # contenu vide, rien à compter
"""
from __future__ import annotations


def detect(occurrences: int, max_messages: int) -> str | None:
    """Retourne "N messages identiques" si le seuil est atteint/dépassé, None sinon."""
    if occurrences <= 0:
        return None
    if occurrences >= max_messages:
        return f"{occurrences} messages identiques"
    return None