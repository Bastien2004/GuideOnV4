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

# Symboles non-ASCII fréquents classés "So" par Unicode mais qui ne sont
# PAS des emojis (typographie courante : degré, copyright, marque...).
# Ajoutés le 2026-10-01 suite à un faux positif signalé par Paul (voir
# note ASCII ci-dessous pour le cas principal — backticks).
_NON_EMOJI_SYMBOLS = {"\u00b0", "\u00a9", "\u00ae", "\u2122"}  # degré, copyright, R, TM


# Blocs Unicode entierement classes "So" mais qui ne sont QUE des caracteres
# de dessin/mise en forme ASCII-art -- jamais des emojis. Tres utilises dans
# les bannieres de recrutement/pub (lignes de separation, barres de
# progression). Ajoutes le 2026-11-22 suite a un faux positif signale par
# Paul : un message publicitaire sans vrai emoji en exces etait sanctionne
# a cause d'une simple ligne decorative de 18 caracteres "BOX DRAWINGS",
# comptes a eux seuls comme "18 emojis".
_NON_EMOJI_RANGES = (
    (0x2500, 0x257F),  # Box Drawing (traits de separation simples/doubles)
    (0x2580, 0x259F),  # Block Elements (blocs de remplissage/ombrage)
)


def _is_non_emoji_symbol(ch):
    if ch in _NON_EMOJI_SYMBOLS:
        return True
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _NON_EMOJI_RANGES)


def _count_unicode_emojis_fallback(text: str) -> int:
    """
    Compte les codepoints de catégorie Unicode "So" (Symbol, Other) ou "Sk"
    (Symbol, Modifier). Complémentaire de la regex : capture les cas rares
    manqués. Ne double-compte pas avec la regex (appelé sur texte déjà
    stripped de ce qu'elle a matché — voir detect()).

    ⚠️ Exclut les codepoints ASCII (< 0x80) : aucun emoji n'est encodé en
    ASCII, mais plusieurs signes de ponctuation ASCII très courants sont
    classés "Sk"/"So" par Unicode sans être des emojis — notamment le
    backtick (utilisé pour le code inline en Markdown, catégorie "Sk") et
    l'accent circonflexe isolé. Sans cette exclusion, un message citant
    plusieurs commandes entre backticks (ex: code /ngstaff config code)
    se faisait sanctionner par l'antispam emoji alors qu'il ne contient
    aucun emoji — bug remonté par Paul le 2026-10-01 (6 commandes citées
    entre backticks = 12 backticks = "12 emojis" détectés à tort).
    Exclut aussi quelques symboles non-ASCII fréquents et non-pictographiques
    (degré, copyright, marque déposée) qui partagent la même catégorie
    Unicode pour la même raison.
    """
    count = 0
    for ch in text:
        if ch in _IGNORE_CODEPOINTS or _is_non_emoji_symbol(ch):
            continue
        if ord(ch) < 0x80:
            continue
        cat = unicodedata.category(ch)
        if cat in ("So", "Sk"):
            count += 1
    return count


# Densité minimale (emojis / longueur du message) à partir de laquelle un
# dépassement du seuil absolu est considéré comme du VRAI spam visuel.
# Ajoutée le 2026-11-22 : les pubs de recrutement (longues, plusieurs
# centaines à quelques milliers de caractères) contiennent souvent une
# poignée de vrais emojis dispersés dans tout le texte (un par rubrique, un
# par serveur listé...) — ça dépasse facilement le seuil absolu de 10 sans
# être du spam d'emojis pour autant. Un vrai spam visuel ("🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉")
# est lui quasi exclusivement composé d'emojis : sa densité est très élevée.
# 0.08 = en moyenne un emoji tous les ~12 caractères ou plus dense. Un
# message de 2000 caractères doit donc contenir au moins 160 emojis pour
# être flaggé sur ce seul critère — largement au-dessus de ce que contient
# une pub avec quelques icônes dispersées, mais bien en dessous d'un mur
# d'emojis.
_MIN_DENSITY = 0.08

# Garde-fou absolu : au-delà de ce nombre d'emojis, le message est flaggé
# quelle que soit sa longueur (protège contre un message délibérément
# allongé — padding de texte ou d'espaces — pour diluer artificiellement la
# densité et passer sous le seuil ci-dessus).
_ABSOLUTE_CEILING = 40


def detect(
    message_content: str,
    *,
    max_emoji: int = 10,
) -> str | None:
    """Retourne "X emojis" si dépassement, None sinon.

    Le dépassement du seuil absolu (`max_emoji`) ne suffit plus seul à
    sanctionner : au-delà de ce seuil, il faut AUSSI que la densité
    d'emojis dans le message (emojis / longueur totale) dépasse
    `_MIN_DENSITY` — sauf si le nombre absolu d'emojis dépasse
    `_ABSOLUTE_CEILING`, qui sanctionne dans tous les cas. Voir
    `_MIN_DENSITY` ci-dessus pour le raisonnement complet.
    """
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
    length = len(message_content)
    density = total / length if length else 0.0

    log.debug(
        "[AUTOMOD emoji detect] custom=%d regex=%d fallback=%d total=%d max=%d "
        "len=%d density=%.3f",
        custom_count, regex_count, fallback_count, total, max_emoji, length, density,
    )

    if total <= max_emoji:
        return None

    if total > _ABSOLUTE_CEILING or density >= _MIN_DENSITY:
        return f"{total} emojis"
    return None