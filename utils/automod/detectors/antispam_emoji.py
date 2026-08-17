"""
utils/automod/detectors/antispam_emoji.py — Détection des messages avec
trop d'emojis (v2 — regex élargie + fallback catégorie Unicode).

v1 utilisait des plages spécifiques ; ratait certains emojis courants
(⌚, ✅, ✨, ❤️, ⚡, ▶️, ↩️, etc.) situés hors des plages BMP typiques.
v2 combine :
  1. Regex sur toutes les plages "emoji-like" connues (large)
  2. Fallback : itère les codepoints avec unicodedata.category() pour
     capturer les symbols "So" et "Sk" restants (émojis + drapeaux
     composés + skin tones etc.)

Comptage :
  - emojis custom Discord : <:name:id> et <a:name:id> (regex)
  - emojis Unicode : union de la regex + fallback (déduplication par
    position pour ne pas compter deux fois le même caractère)
"""
from __future__ import annotations

import logging
import re
import unicodedata

log = logging.getLogger(__name__)

# Emojis custom Discord.
_CUSTOM_EMOJI_RE = re.compile(r"<a?:\w+:\d+>")

# Plages Unicode "emoji-like". Volontairement large — mieux vaut compter un
# faux positif que rater un vrai emoji.
_UNICODE_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FFFF"   # tout le plan 1 (emojis + supplements)
    "\U00002600-\U000027BF"   # misc symbols + dingbats
    "\U00002300-\U000023FF"   # misc technical (⌚⌛)
    "\U00002B00-\U00002BFF"   # misc symbols and arrows
    "\U00002190-\U000021FF"   # arrows
    "\U000025A0-\U000025FF"   # geometric shapes
    "\U0001F1E6-\U0001F1FF"   # regional indicator (flags)
    "]",
    flags=re.UNICODE,
)

# Codepoints uniques à considérer aussi comme emojis (fallback catégorie).
# Émoji présentation, ZWJ, variation selectors sont IGNORÉS du comptage
# (ce ne sont pas des emojis à eux seuls — juste des modificateurs).
_IGNORE_CODEPOINTS = {"\ufe0f", "\u200d"}


def _count_unicode_emojis_fallback(text: str) -> int:
    """
    Compte les codepoints de catégorie Unicode "So" (Symbol, Other) ou "Sk"
    (Symbol, Modifier). Complémentaire de la regex : capture les cas rares
    manqués. Ne double-compte pas avec la regex (appelé sur texte déjà
    stripped de ce qu'elle a matché — voir detect()).
    """
    count = 0
    for ch in text:
        if ch in _IGNORE_CODEPOINTS:
            continue
        cat = unicodedata.category(ch)
        if cat in ("So", "Sk"):
            count += 1
    return count


def detect(
    message_content: str,
    *,
    max_emoji: int = 10,
) -> str | None:
    """Retourne "X emojis" si dépassement, None sinon."""
    if not message_content:
        return None

    # 1. Compte les customs Discord + retire-les du texte.
    custom_matches = _CUSTOM_EMOJI_RE.findall(message_content)
    custom_count = len(custom_matches)
    stripped = _CUSTOM_EMOJI_RE.sub("", message_content)

    # 2. Compte les emojis Unicode via regex + retire-les.
    unicode_matches = _UNICODE_EMOJI_RE.findall(stripped)
    regex_count = len(unicode_matches)
    stripped_further = _UNICODE_EMOJI_RE.sub("", stripped)

    # 3. Fallback pour les symboles restants (émojis atypiques hors regex).
    fallback_count = _count_unicode_emojis_fallback(stripped_further)

    total = custom_count + regex_count + fallback_count

    log.debug(
        "[AUTOMOD emoji detect] custom=%d regex=%d fallback=%d total=%d max=%d",
        custom_count, regex_count, fallback_count, total, max_emoji,
    )

    if total > max_emoji:
        return f"{total} emojis"
    return None