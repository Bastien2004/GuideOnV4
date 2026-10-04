"""
utils/invite_render.py — Rendu du message d'annonce "qui a invité qui" à
l'arrivée d'un membre.

2026-10-04 (Paul) : message brut (texte simple), plus de Container/LayoutView
Components V2. Avant, le rendu passait par un TextDisplay V2 — Discord ne
résout/affiche pas toujours de façon fiable une mention au premier rendu
d'un message Components V2 (c'est ce quirk qui avait motivé la ré-édition
de réparation différée dans InviteListener._repair_mention, retirée en
même temps que ce changement puisqu'un message en contenu texte brut ne
souffre pas de ce problème : une mention dans `content` est toujours
résolue/notifiée dès le premier envoi).
"""
from __future__ import annotations

import discord

FALLBACK_INVITER_TEXT = "un lien inconnu (invitation vanity/externe)"


def render_announce_template(
    template: str, *, member: discord.Member, inviter_id: int | None, guild: discord.Guild,
) -> str:
    """Remplace les variables du template d'annonce d'invitation.

    Reprend les variables communes de utils.bienvenue_render.render_template
    ({user}/{mention}/{server}/{member_count}...) et ajoute {inviter}, propre
    à cette annonce. `inviter_id` n'est jamais re-résolu ici via un nouvel
    appel API (pas de guild.invites()/fetch_member) : c'est celui déjà
    déterminé par InviteListener.on_member_join au moment du join, pour ne
    jamais ajouter de requête Discord supplémentaire sur cette voie chaude.
    """
    inviter_text = f"<@{inviter_id}>" if inviter_id is not None else FALLBACK_INVITER_TEXT

    return (
        (template or "")
        .replace("{user}", member.display_name)
        .replace("{display_name}", member.display_name)
        .replace("{mention}", member.mention)
        .replace("{id}", str(member.id))
        .replace("{server}", guild.name)
        .replace("{member_count}", str(guild.member_count or 0))
        .replace("{inviter}", inviter_text)
    )