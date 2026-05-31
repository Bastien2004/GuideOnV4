"""
views/invite/user_view.py — Affichage /invite user [membre].

Vue non-interactive : juste un container avec les compteurs du membre,
plus l'info "invité par X" si le lien est connu (table invite_links).
"""
from __future__ import annotations

from typing import Optional

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay


def build_user_stats_view(
    target: discord.abc.User,
    stats: dict,
    link: Optional[dict],
    guild: discord.Guild,
) -> LayoutView:
    """
    Construit la vue d'affichage des stats d'un membre.

    Args:
        target: l'utilisateur ciblé (pour son mention/avatar).
        stats: dict renvoyé par get_user_stats() — clés regular/fake/bonus/left/total.
        link: dict renvoyé par get_link() (ou None si membre arrivé hors tracking).
        guild: la guild (pour résoudre l'inviteur en mention si présent en cache).
    """
    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay(
        f"# 📨 Invitations · {target.display_name}\n-# {target.mention}"
    ))
    container.add_item(Separator())

    container.add_item(TextDisplay(
        "### 📊 Compteurs\n"
        f"-# ✅ Régulières : **{stats['regular']}**\n"
        f"-# 🚫 Fausses : **{stats['fake']}**\n"
        f"-# 🎁 Bonus : **{stats['bonus']}**\n"
        f"-# 🚪 Parties : **{stats['left']}**"
    ))
    container.add_item(Separator())

    container.add_item(TextDisplay(
        f"### 🧮 Total effectif\n## **{stats['total']}** invitation"
        f"{'s' if stats['total'] != 1 and stats['total'] != -1 else ''}"
    ))
    container.add_item(Separator())

    # --- Bloc "invité par" ---
    if link is None:
        invited_by = "-# 🤷 Aucun suivi d'arrivée pour ce membre."
    else:
        inviter_id = link.get("inviter_id")
        if inviter_id is None:
            invited_by = "-# 🌐 Arrivé via un lien sans inviteur identifié (vanity ou externe)."
        else:
            inviter = guild.get_member(inviter_id)
            inviter_txt = inviter.mention if inviter else f"`utilisateur {inviter_id}`"
            extras = []
            if link.get("is_fake"):
                extras.append("compte considéré comme récent")
            if link.get("counted_left"):
                extras.append("a quitté le serveur")
            suffix = f" *( {', '.join(extras)} )*" if extras else ""
            invited_by = f"-# 👤 Invité par {inviter_txt}{suffix}"

    container.add_item(TextDisplay(f"### 🔗 Origine\n{invited_by}"))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ======================================================
# ========== COMPAT COMMANDE : InviteUserView ==========
# ======================================================

class InviteUserView:
    @classmethod
    def create(
        cls,
        target: discord.abc.User,
        stats: dict,
        link: Optional[dict],
        guild: discord.Guild,
    ) -> LayoutView:
        return build_user_stats_view(target, stats, link, guild)