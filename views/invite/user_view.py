"""
views/invite/user_view.py — Affichage /invite user [membre].
"""

from __future__ import annotations

from typing import Optional

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay


# ============================================================
#  Fonction principale de construction
# ============================================================

def build_user_stats_view(target: discord.abc.User, stats: dict, link: Optional[dict], guild: discord.Guild) -> LayoutView:
    """Construit l'interface de l'utilisateur."""

    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay(
        f"# <:Up:1547703175061180607> Invitations {target.display_name}"
    ))
    container.add_item(Separator())

    container.add_item(TextDisplay(
        "### <:Stat:1547703142466982039> Compteurs :\n"
        f"➤ Régulières : **{stats['regular']}**\n"
        f"➤ Fausses : **{stats['fake']}**\n"
        f"➤ Bonus : **{stats['bonus']}**\n"
        f"➤ Parties : **{stats['left']}**"
    ))
    container.add_item(Separator())

    container.add_item(TextDisplay(
        f"### <:AI:1547703102273093633> Score total :\n **{stats['total']}** invitation"
        f"{'s' if stats['total'] != 1 and stats['total'] != -1 else ''}"
    ))
    container.add_item(Separator())

    # --- Bloc "invité par" ---
    if link is None:
        if guild.me is not None and not guild.me.guild_permissions.manage_guild:
            invited_by = ("-# <:erreur:1495443907281031359> Suivi impossible (permission manquante).")
        else:
            invited_by = "-# <:annuler:1495444256754761979> Aucun suivi d'arrivée pour ce membre."

    else:
        inviter_id = link.get("inviter_id")
        if inviter_id is None:
            invited_by = "-# <:annuler:1495444256754761979> Inviteur inconnu ..."
        else:
            inviter = guild.get_member(inviter_id)
            inviter_txt = inviter.mention if inviter else f"`utilisateur {inviter_id}`"
            extras = []
            if link.get("is_fake"):
                extras.append("compte considéré comme récent")
            if link.get("counted_left"):
                extras.append("a quitté le serveur")
            suffix = f" *( {', '.join(extras)} )*" if extras else ""
            invited_by = f"-# <:valider:1495444292867723284> Invité par {inviter_txt}{suffix}"

    container.add_item(TextDisplay(f"### <:lien:1552027533032034394> Origine du membre :\n{invited_by}"))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 🧭 Class de commande
# ============================================================

class InviteUserView:
    @classmethod
    def create(cls, target: discord.abc.User, stats: dict, link: Optional[dict], guild: discord.Guild) -> LayoutView:
        return build_user_stats_view(target, stats, link, guild)