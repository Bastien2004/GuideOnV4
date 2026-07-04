"""
Container universel a utiliser dans les views/commandes.
"""
from __future__ import annotations

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay


# ============================================================
# 📤 Envoi éphémère universel
# ============================================================

async def send_ephemeral(interaction: discord.Interaction, view: LayoutView) -> None:
    """
    Envoie `view` en éphémère, via followup si l'interaction a déjà
    répondu (ex: defer() déjà appelé), sinon via response.send_message.

    Centralise un pattern auparavant dupliqué dans perm_admin.py,
    perm_dev.py, perm_staff.py, perm_alpha.py et error_handler.py.
    """
    if interaction.response.is_done():
        await interaction.followup.send(view=view, ephemeral=True)
    else:
        await interaction.response.send_message(view=view, ephemeral=True)


# ============================================================
# 🧱 Container de base
# ============================================================

def _base_container(title: str, message: str) -> LayoutView:
    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay(title))
    container.add_item(Separator())
    container.add_item(TextDisplay(message))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# ❌ Container erreur
# ============================================================

def error_container(message: str) -> LayoutView:
    return _base_container("# <:erreur_cad:1495446243957018684> Erreur", message)


# ============================================================
# ✅ Container succès
# ============================================================

def success_container(message: str) -> LayoutView:
    return _base_container("# <:valider:1495444292867723284> Succès", message)


# ============================================================
# ℹ️ Container info
# ============================================================

def info_container(message: str) -> LayoutView:
    return _base_container("# <:information:1495446355395612794> Information", message)


# ============================================================
# ⚠️ Container warning (bonus — utile si besoin)
# ============================================================

def warning_container(message: str) -> LayoutView:
    return _base_container("# <:erreur:1495443907281031359> Attention", message)