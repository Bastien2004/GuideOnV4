"""
utils/automod/detectors/antiflood.py — Détection de "mashkeyboard" (flood).

Fonction pure (aucune dépendance à discord.py ou à la DB) : un texte tapé
au hasard sur le clavier ("kjshdfkjqshdfkjh") contient très peu de voyelles
comparé à un texte écrit dans une vraie langue (français ~40-45% de voyelles
parmi les lettres). On calcule donc le ratio voyelles / lettres et on
déclenche en-dessous d'un seuil configurable.

Ne compte QUE les lettres (`str.isalpha()`, Unicode — inclut les accents) :
chiffres, ponctuation, espaces, emojis et mentions sont ignorés, pour ne
pas fausser le ratio avec du contenu non-alphabétique. Les accents sont
neutralisés avant comparaison (é/è/ê → e) pour reconnaître les voyelles
françaises accentuées comme des voyelles.

Limite connue (volontairement acceptée, cf. spec) : un flood composé
uniquement de voyelles répétées ("aaaaaaaaaaaa") n'est PAS détecté par ce
système — c'est le rôle du système Anti Spam Message / Anti Spam Emoji de
couvrir ce cas, Anti Flood cible spécifiquement le mashkeyboard.

Tests (exemples — à coller tels quels dans un fichier pytest si besoin) :

    assert detect("Bonjour tout le monde, comment allez-vous aujourd'hui ?") is None
    assert detect("kjshdfkjqshdfkjhqsdkfjhqsdkfjh") == "0% voyelles sur 30 lettres"
    assert detect("Régénération accélérée grâce à l'énergie électrique") is None
    assert detect("short text") is None                    # < 20 lettres, pas assez fiable
    assert detect("") is None
    assert detect(None) is None
    assert detect("azertyazertyazertyazerty") is None       # y compte comme voyelle
"""
from __future__ import annotations

import logging
import unicodedata

log = logging.getLogger(__name__)

_VOWELS = set("aeiouy")


def _strip_accent(ch: str) -> str:
    """Neutralise l'accent d'un caractère unique (é → e, ô → o, ...)."""
    decomposed = unicodedata.normalize("NFKD", ch)
    return decomposed[0] if decomposed else ch


def detect(
    message_content: str | None,
    *,
    min_length: int = 20,
    min_vowel_ratio: float = 0.2,
) -> str | None:
    """
    Retourne "X% voyelles sur Y lettres" si le message a au moins
    `min_length` lettres ET que le ratio de voyelles est en-dessous de
    `min_vowel_ratio`, None sinon (message trop court pour être fiable,
    ou ratio normal).
    """
    if not message_content:
        return None

    letters = [c for c in message_content if c.isalpha()]
    total = len(letters)
    if total < min_length:
        return None

    vowel_count = sum(1 for c in letters if _strip_accent(c.lower()) in _VOWELS)
    ratio = vowel_count / total

    if ratio < min_vowel_ratio:
        log.debug(
            "[AUTOMOD antiflood detect] ratio=%.2f total=%d vowels=%d",
            ratio, total, vowel_count,
        )
        return f"{ratio:.0%} voyelles sur {total} lettres"

    return None