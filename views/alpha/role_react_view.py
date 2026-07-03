"""
views/alpha/role_react_view.py — Message public du système Rôle Réaction Alpha.

build_role_react_view(entries) → LayoutView avec :
  - Description de chaque rôle
  - Boutons toggle (custom_id "role_react_{role_id}") gérés par le Cog on_interaction
"""
from __future__ import annotations

import re

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

# Marqueur visuel placé devant chaque rôle de la liste descriptive.
# Sans lui, deux entrées consécutives se confondent visuellement dès que
# l'une a une description (2 lignes) et l'autre non (1 ligne).
ROLE_SEPARATOR = "➤"

# Format emoji custom Discord : <:nom:id> ou <a:nom:id> (animé).
# NB: discord.PartialEmoji.from_str() ne lève JAMAIS d'exception — si le
# format ne matche pas, il retombe silencieusement sur une interprétation
# "emoji unicode" avec la chaîne entière comme name. Un try/except autour
# ne validait donc rien ; on matche nous-mêmes le format attendu.
_CUSTOM_EMOJI_RE = re.compile(r"^<a?:[A-Za-z0-9_]{2,32}:\d{15,21}>$")


def is_valid_emoji(s: str | None) -> bool:
    """
    Valide qu'une chaîne est un emoji exploitable par Discord : soit le
    format custom <:nom:id> / <a:nom:id>, soit un emoji unicode plausible.
    Rejette le texte brut — l'erreur la plus fréquente étant le nom et
    l'emoji inversés dans le modal d'ajout/édition (cf. label='📰' avec
    du texte dans le champ emoji -> 400 Invalid emoji côté Discord).
    """
    if not s:
        return True  # champ optionnel, vide = valide
    s = s.strip()
    if s.startswith("<"):
        return bool(_CUSTOM_EMOJI_RE.match(s))
    # Un vrai emoji unicode n'est jamais composé de lettres/chiffres ASCII
    # et reste toujours court (même les séquences ZWJ complexes du type
    # famille/drapeau tiennent en quelques codepoints).
    return not s.isascii() and len(s) <= 15


def parse_emoji(s: str | None) -> discord.PartialEmoji | str | None:
    """Convertit une chaîne emoji en objet Discord si c'est un emoji custom.
    Renvoie None si la valeur n'est pas exploitable (defense in depth :
    une entrée mal saisie ne doit jamais faire planter tout le rendu à
    cause d'une seule valeur invalide déjà persistée)."""
    if not s:
        return None
    s = s.strip()
    if not is_valid_emoji(s):
        return None
    if s.startswith("<"):
        return discord.PartialEmoji.from_str(s)
    return s


def build_role_react_view(entries: list[dict]) -> LayoutView:
    """
    entries : liste triée de dicts {role_id, label, emoji, description, position}
    """
    view = LayoutView(timeout=None)

    # ── Header ──────────────────────────────────────────────
    c_header = Container()
    c_header.add_item(TextDisplay("# 🔔 Rôles de Notification"))
    c_header.add_item(Separator())
    c_header.add_item(TextDisplay(
        "Personnalisez vos notifications en cliquant sur les boutons ci-dessous.\n"
        "Un **clic** active le rôle, un **second clic** le retire."
    ))
    c_header.add_item(Separator())
    view.add_item(c_header)

    if not entries:
        c_empty = Container()
        c_empty.add_item(TextDisplay("*Aucun rôle de notification configuré pour le moment.*"))
        c_empty.add_item(TextDisplay("-# GuideOn Studio"))
        view.add_item(c_empty)
        return view

    # ── Liste descriptive ────────────────────────────────────
    c_list = Container()
    lines = []
    for e in entries:
        emoji = f"{e['emoji']} " if e.get("emoji") else ""
        desc = f"\n-# {e['description']}" if e.get("description") else ""
        lines.append(f"{ROLE_SEPARATOR} {emoji}**{e['label']}**{desc}")

    c_list.add_item(TextDisplay("\n".join(lines)))
    c_list.add_item(Separator())
    view.add_item(c_list)

    # ── Boutons (rangées de 5) ───────────────────────────────
    c_btns = Container()
    chunk_size = 5
    for i in range(0, len(entries), chunk_size):
        chunk = entries[i : i + chunk_size]
        buttons = []
        for e in chunk:
            buttons.append(Button(
                label=e["label"],
                style=ButtonStyle.secondary,
                custom_id=f"role_react_{e['role_id']}",
                emoji=parse_emoji(e.get("emoji")),
            ))
        c_btns.add_item(ActionRow(*buttons))

    c_btns.add_item(Separator())
    c_btns.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c_btns)

    return view