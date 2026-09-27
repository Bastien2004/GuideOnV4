"""
views/dev/command_visibility_view.py — Vue de diagnostic de visibilité de
commande, extraite de cogs/dev/command_visibility.py — même traitement que
views/dev/guild_info_view.py.

Reste en LayoutView simple, PAS BaseLayoutView : réponse éphémère one-shot
sans aucun composant interactif.
"""
from __future__ import annotations

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.discord_command_permissions import CommandVisibilityReport

_MAX_OVERWRITES_SHOWN = 8  # évite de dépasser la limite de caractères d'un TextDisplay sur un serveur très configuré


def _verdict_badge(visible: bool | None) -> str:
    if visible is True:
        return "✅"
    if visible is False:
        return "❌"
    return "❔"


def build_command_visibility_view(report: CommandVisibilityReport) -> LayoutView:
    """Construction de la view."""
    view = LayoutView(timeout=None)
    c = Container()

    guild = report.guild
    member = report.member

    c.add_item(TextDisplay("# 🔍 Visibilité des commandes"))
    c.add_item(TextDisplay(f"-# Diagnostic des permissions d'intégration Discord sur **{guild.name}** (`{guild.id}`)."))
    c.add_item(Separator())

    role_names = ", ".join(f"@{r.name}" for r in sorted(member.roles, key=lambda r: r.position, reverse=True) if not r.is_default()) or "*Aucun rôle*"
    admin_badge = "✓ Administrateur" if member.guild_permissions.administrator else "✗"
    owner_badge = "✓ Propriétaire du serveur" if member.id == guild.owner_id else "✗"
    c.add_item(TextDisplay(
        f"**Membre analysé :**\n{member.mention} (`{member.id}`)\n\n"
        f"**Rôles actuels :**\n{role_names}\n\n"
        f"**{admin_badge}** · **{owner_badge}**"
    ))
    c.add_item(Separator())

    if not report.guild_commands:
        c.add_item(TextDisplay(
            "*Aucune commande guild-scoped trouvée sur ce serveur — soit le bot n'a rien "
            "synchronisé ici, soit toutes les commandes de ce serveur sont globales.*"
        ))
    else:
        cmd_list = ", ".join(f"`/{name}`" for name in sorted(report.guild_commands.values()))
        c.add_item(TextDisplay(f"**Commandes guild-scoped synchronisées ici ({len(report.guild_commands)}) :**\n{cmd_list}"))
    c.add_item(Separator())

    # ── Verdicts ──────────────────────────────────────────────────────
    if not report.verdicts:
        c.add_item(TextDisplay("*Rien à diagnostiquer — aucune commande concernée trouvée sur ce serveur.*"))
    else:
        c.add_item(TextDisplay("## 🧾 Verdict par commande"))
        for v in report.verdicts:
            c.add_item(TextDisplay(f"**{_verdict_badge(v.visible)} {v.command_label}**\n-# {v.reason}"))
        c.add_item(Separator())

    # ── Détail brut des overwrites (pour vérification manuelle) ───────
    entries_with_overwrites = [e for e in report.entries if e.overwrites]
    if entries_with_overwrites:
        c.add_item(TextDisplay("## 📋 Détail des overwrites (page Intégrations)"))
        for entry in entries_with_overwrites:
            lines = []
            for ow in entry.overwrites[:_MAX_OVERWRITES_SHOWN]:
                badge = "✅" if ow.allow else "❌"
                lines.append(f"{badge} [{ow.kind}] {ow.label}")
            if len(entry.overwrites) > _MAX_OVERWRITES_SHOWN:
                lines.append(f"… et {len(entry.overwrites) - _MAX_OVERWRITES_SHOWN} de plus.")
            c.add_item(TextDisplay(f"**{entry.command_label}**\n-# " + "\n-# ".join(lines)))
    else:
        c.add_item(TextDisplay(
            "*Aucun overwrite de permission de commande configuré sur ce serveur (page "
            "Intégrations vide pour cette application).*"
        ))

    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(c)
    return view