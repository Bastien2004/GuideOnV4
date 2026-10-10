"""
views/eco/balance_view.py — Affichage /eco balance [membre].
"""

from __future__ import annotations

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.managers.eco_manager import format_amount


def build_balance_view(target: discord.abc.User, balance: dict) -> LayoutView:
    """Construit l'interface du /eco balance."""

    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay(
        f"# <:money:1558435137534959636> Solde de {target.mention}"
    ))
    container.add_item(Separator())

    container.add_item(TextDisplay(
        f"### 🧮 Solde actuel\n## **{format_amount(balance['balance'])}**"
    ))
    container.add_item(Separator())

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ======================================================
# ========== COMPAT COMMANDE : EcoBalanceView ==========
# ======================================================

class EcoBalanceView:
    @classmethod
    def create(cls, target: discord.abc.User, balance: dict) -> LayoutView:
        return build_balance_view(target, balance)