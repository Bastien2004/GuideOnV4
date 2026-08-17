"""
utils/automod/detectors/antispam_emoji.py — Détection des messages avec
trop d'emojis.

Compte :
  - les emojis custom Discord : <:name:id> et <a:name:id> (regex)
  - les emojis Unicode : détectés via la propriété Unicode "Emoji" (utilise
    le module `emoji` s'il est présent, sinon un fallback regex sur les
    plages Unicode courantes)

Fonction pure (accepte le contenu texte, pas le Message discord.py).
"""
from __future__ import annotations

import re

# Emojis custom Discord — statiques et animés.
_CUSTOM_EMOJI_RE = re.compile(r"<a?:\w+:\d+>")

# Fallback pour les emojis Unicode : plages BMP courantes + supplementary
# planes. Approximation suffisante pour la détection de spam (on n'a pas
# besoin d'une reconnaissance parfaite pédante d'un tag ZWJ multi-parties
# — un cluster complexe compte pour ~2-3 codepoints, ce qui va DANS le
# sens de la détection de spam).
_UNICODE_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F5FF"   # symbols & pictographs
    "\U0001F600-\U0001F64F"   # emoticons
    "\U0001F680-\U0001F6FF"   # transport & map
    "\U0001F700-\U0001F77F"   # alchemical
    "\U0001F780-\U0001F7FF"   # geometric shapes ext
    "\U0001F800-\U0001F8FF"   # supplemental arrows-c
    "\U0001F900-\U0001F9FF"   # supplemental symbols
    "\U0001FA00-\U0001FA6F"   # chess, symbols
    "\U0001FA70-\U0001FAFF"   # symbols & pictographs ext-a
    "\U00002600-\U000026FF"   # misc symbols
    "\U00002700-\U000027BF"   # dingbats
    "\U0001F1E6-\U0001F1FF"   # regional indicator (flags)
    "]",
    flags=re.UNICODE,
)


def detect(
    message_content: str,
    *,
    max_emoji: int = 10,
) -> str | None:
    """Retourne "X emojis" si dépassement, None sinon."""
    if not message_content:
        return None

    custom_count = len(_CUSTOM_EMOJI_RE.findall(message_content))
    # On retire d'abord les customs pour ne pas compter leur contenu
    # (au cas où l'emoji `name` contiendrait des chars matchés).
    stripped = _CUSTOM_EMOJI_RE.sub("", message_content)
    unicode_count = len(_UNICODE_EMOJI_RE.findall(stripped))

    total = custom_count + unicode_count
    if total > max_emoji:
        return f"{total} emojis"
    return None