"""
views/exp/levelup_view.py — Annonce de passage de niveau (Components V2).

BUG/COMPORTEMENT CHANGÉ (2026-09, demande Paul) : ce n'est plus un message
éphémère de 5-8s auto-supprimé dans le salon du message qui a déclenché le
gain d'EXP — c'est désormais une annonce PERMANENTE, envoyée dans le salon
dédié configuré via `/exp config` (cf. utils.managers.exp_manager, champs
`levelup_announce_enabled`/`levelup_channel_id`, et
cogs/events/exp_listener.py::_notify_level_up qui décide QUAND l'envoyer).
Ce fichier ne gère QUE le rendu du message, pas la décision de l'envoyer.

Vue purement informative (aucun callback bot-side) : LayoutView(timeout=None)
simple, pas de BaseLayoutView — même raisonnement que views/user/user_view.py
(rien à protéger, aucune interaction ne remonte au bot).
"""
from __future__ import annotations

import discord
from discord.ui import Container, LayoutView, Section, Separator, TextDisplay, Thumbnail


def _avatar_url(member: discord.Member) -> str:
    avatar = member.display_avatar
    return avatar.replace(size=256, format="gif" if avatar.is_animated() else "png").url


def build_levelup_view(
    member: discord.Member, new_level: int, tier: str, *, tier_changed: bool = False,
) -> LayoutView:
    """Construit l'annonce de level-up — désormais destinée à un salon
    d'annonce permanent (cf. docstring de module), plus au salon où le
    membre vient d'écrire/de quitter le vocal.

    `tier_changed` : True si ce level-up fait aussi franchir un nouveau
    palier (cf. utils.managers.exp_manager.tier_name_for_level) — dans ce
    cas l'annonce met en avant le nouveau rang plutôt que le simple niveau,
    pour que la notion de "palier" (§ /exp info) se voie aussi à l'usage,
    pas seulement dans la documentation.
    """
    view = LayoutView(timeout=None)
    container = Container()

    header = "## 🏔️ Nouveau palier atteint !" if tier_changed else "## 🎉 Level Up !"
    container.add_item(TextDisplay(header))
    container.add_item(Separator())

    if tier_changed:
        body = (
            f"{member.mention} passe au **niveau {new_level}** et rejoint "
            f"désormais le rang **{tier}** !"
        )
    else:
        body = f"{member.mention} passe au **niveau {new_level}** — {tier} !"

    container.add_item(Section(TextDisplay(body), accessory=Thumbnail(_avatar_url(member))))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view
