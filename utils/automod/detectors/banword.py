"""
utils/automod/detectors/banword.py — Détection de mots bannis avec anti-contournement.

Fonction pure (aucune dépendance à discord.py ou à la DB). Prend un message
et une liste de mots bannis, retourne le premier mot matché ou None.

Testable en isolation via pytest — c'est justement pourquoi cette logique
est extraite dans un module dédié.

Stratégie de matching ("mot entier avec normalisation") :
  1. Le message est NORMALISÉ (voir _normalize) :
       - lowercase
       - dépouillé de ses accents (NFD + strip marks combinantes)
       - leetspeak inversé : 0→o, 1→i, 3→e, 4→a, 5→s, 7→t, 8→b, @→a, $→s
       - caractères non-alphanumériques (points, tirets, underscores, etc.)
         RETIRÉS (pas remplacés par des espaces) — les vrais espaces du
         message sont préservés
       - espaces multiples compressés en un seul
  2. Le mot cherché est également normalisé, puis compilé en regex où
     chaque lettre est répétable (`c+o+n+`) et des espaces optionnels sont
     tolérés entre les lettres (pour contrer "c o n"). Le tout entouré de
     word boundaries `\\b` pour rester "mot entier".
  3. Résultat : matche "con", "CoN", "cón", "c0n", "c.o.n", "c o n",
     "coooon"… mais PAS "connard", "concert", "condition", "bonjour".
  4. Compilation cachée en LRU pour éviter de recompiler à chaque message.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

# Table de leetspeak inverse. Volontairement conservateur (pas de "6"→"g",
# trop rare en français et source de faux positifs).
LEET_MAP: dict[str, str] = {
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s",
    "7": "t", "8": "b", "@": "a", "$": "s",
}


def _strip_accents(text: str) -> str:
    """Décompose les caractères Unicode puis retire les marks combinantes."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _apply_leet(text: str) -> str:
    """Remplace les chiffres/symboles courants par la lettre correspondante."""
    return "".join(LEET_MAP.get(c, c) for c in text)


# Non-alphanumérique hors espace/tab/nl : à SUPPRIMER complètement (pas
# remplacer par espace) pour que "c.o.n" devienne "con" tout en gardant
# les vrais séparateurs de mots.
_NON_ALNUM_TO_STRIP = re.compile(r"[^a-z0-9\s]")


def _normalize(text: str) -> str:
    """Normalise le texte pour la comparaison symétrique message ↔ mot banni."""
    text = text.lower()
    text = _strip_accents(text)
    text = _apply_leet(text)
    text = _NON_ALNUM_TO_STRIP.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@lru_cache(maxsize=1024)
def _compile_pattern(normalized_word: str) -> re.Pattern:
    """
    Compile la regex de recherche pour un mot déjà normalisé.

    Chaque lettre est répétable via `+` (contre "cooon") et séparable par
    des espaces optionnels via `\\s*` (contre "c o n"). Les espaces internes
    des mots composés ("fils de pute") restent obligatoires via `\\s+`.
    Word boundaries `\\b` de part et d'autre garantissent le match sur mot
    entier.
    """
    parts: list[str] = []
    for i, ch in enumerate(normalized_word):
        if ch == " ":
            # Espace obligatoire (mot composé)
            parts.append(r"\s+")
            continue
        parts.append(re.escape(ch) + "+")
        # \s* seulement entre les lettres (pas avant un espace obligatoire)
        if i < len(normalized_word) - 1 and normalized_word[i + 1] != " ":
            parts.append(r"\s*")

    return re.compile(r"\b" + "".join(parts) + r"\b")


def detect(message_content: str, banned_words: list[str]) -> str | None:
    """
    Retourne le PREMIER mot banni matché dans le message, ou None si aucun.

    Le mot retourné est le mot d'origine (tel qu'enregistré par l'admin),
    pas la version normalisée. Utile pour le log staff.
    """
    if not message_content or not banned_words:
        return None

    normalized_msg = _normalize(message_content)
    if not normalized_msg:
        return None

    for word in banned_words:
        normalized_word = _normalize(word)
        if not normalized_word:
            continue
        pattern = _compile_pattern(normalized_word)
        if pattern.search(normalized_msg):
            return word

    return None