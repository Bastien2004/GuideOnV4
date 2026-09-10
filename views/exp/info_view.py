"""
views/exp/info_view.py — Vue explicative du système d'EXP et des paliers
(/exp info).

Vue purement informative (aucun callback bot-side) : simple LayoutView,
même raisonnement que views/exp/levelup_view.py / views/user/user_view.py
(le seul bouton est un ButtonStyle.link, sans callback côté bot).

Affiche les valeurs RÉELLEMENT configurées sur le serveur (gain par
message/vocal, rôle boost) plutôt qu'un texte générique statique — cohérent
avec /exp config qui affiche les mêmes chiffres côté admin.
"""
from __future__ import annotations

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.managers.exp_manager import LEVEL_TIERS, MAX_LEVEL
from utils.settings import settings


def _boost_role_label(role_id: int | None, guild: discord.Guild) -> str:
    if role_id is None:
        return "`Aucun`"
    role = guild.get_role(role_id)
    return role.mention if role is not None else "`Rôle supprimé`"


def build_exp_info_view(guild: discord.Guild, cfg: dict) -> LayoutView:
    """Construit la vue explicative de /exp info."""
    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay("# 🧮 Système d'Expérience"))
    container.add_item(TextDisplay(
        f"Chaque membre progresse à travers **{MAX_LEVEL} niveaux**, répartis en "
        f"**{len(LEVEL_TIERS)} paliers** personnalisés propres à GuideOn — plus tu "
        f"montes, plus il faut d'EXP pour passer au niveau suivant."
    ))
    container.add_item(Separator())

    # ── Comment gagner de l'EXP ────────────────────────────────
    per_message = cfg.get("exp_per_message", 10)
    per_voice = cfg.get("exp_per_voice_minute", 2)
    boost_role_id = cfg.get("boost_role_id")
    boost_percent = cfg.get("boost_percent", 0)

    gain_lines = [
        f"**💬 Message** — `+{per_message} EXP` (cooldown de 60 secondes entre deux gains).",
        f"**🎙️ Vocal** — `+{per_voice} EXP` par minute passée en salon vocal.",
    ]
    if boost_role_id and boost_percent > 0:
        gain_lines.append(
            f"**🚀 Rôle boost** — {_boost_role_label(boost_role_id, guild)} bénéficie de "
            f"**+{boost_percent}%** d'EXP sur tous ses gains."
        )
    container.add_item(TextDisplay(
        "### <:lister:1495445288364675192> Comment gagner de l'EXP ?\n" + "\n".join(gain_lines)
    ))
    container.add_item(Separator())

    # ── Paliers ──────────────────────────────────────────────────
    tier_lines = [f"**{tier['name']}** — Niveaux `{tier['range'][0]}` à `{tier['range'][1]}`" for tier in LEVEL_TIERS]
    container.add_item(TextDisplay("### 🏔️ Les paliers\n" + "\n".join(tier_lines)))
    container.add_item(Separator())

    container.add_item(TextDisplay(
        "-# `/exp level` pour voir ta progression • `/exp leaderboard` pour le classement "
        "du serveur.\n"
        "-# Un administrateur peut configurer une **annonce de montée de niveau** "
        "permanente via `/exp config`."
    ))

    doc_btn = Button(label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚")
    container.add_item(ActionRow(doc_btn))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view
