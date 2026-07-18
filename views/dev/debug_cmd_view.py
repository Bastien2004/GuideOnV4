"""
views/dev/debug_cmd_view.py — Vue de diagnostic d'une commande, extraite de
cogs/dev/debug_cmd.py — même traitement que views/dev/nota_debug_view.py.
"""

from __future__ import annotations

from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.command_debug import CommandDebugInfo

# ============================================================
# 🧩 Construction de la vue
# ============================================================

def build_debug_cmd_view(info: CommandDebugInfo) -> LayoutView:
    """Construction de la view."""
    view = LayoutView(timeout=None)
    c = Container()

    c.add_item(TextDisplay("# 🔍 Debug Commande"))
    c.add_item(Separator())
    c.add_item(TextDisplay(f"**Commande :** `{info.command_name}`"))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**Activée :** {'Oui' if info.enabled else 'Non'}\n"
        f"**Maintenance :** {'Non' if info.enabled else 'Oui'}\n"
        f"**Cooldown :** {info.cooldown_str}"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**Utilisations :**\n"
        f"• Total : {info.total}\n"
        f"• Aujourd'hui : {info.today}"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(f"**Dernière utilisation :**\n• {info.last_used_str}"))
    c.add_item(Separator())

    c.add_item(TextDisplay(f"**Permissions :**\n• {info.permission_str}"))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(c)
    return view