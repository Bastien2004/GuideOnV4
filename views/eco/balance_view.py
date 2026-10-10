"""
views/eco/balance_view.py — Affichage /eco balance [membre].

Vue non-interactive : un container avec le solde du membre, plus un
indice sur la disponibilité de /eco daily (calculé à partir de
last_daily_at, déjà en base — zéro logique métier dupliquée ici).
"""
from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.managers.eco_manager import DAILY_COOLDOWN, format_amount


def _daily_hint(last_daily_at) -> str:
    if last_daily_at is None:
        return "-# 🎁 `/eco daily` n'a jamais été réclamé — disponible dès maintenant !"

    next_at = last_daily_at + DAILY_COOLDOWN
    if next_at.tzinfo is None:
        # Défense identique à eco_manager._as_aware_utc : certains backends
        # renvoient un datetime naïf même pour une colonne timezone=True.
        next_at = next_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) >= next_at:
        return "-# 🎁 `/eco daily` est disponible dès maintenant !"
    return f"-# 🎁 Prochain `/eco daily` disponible <t:{int(next_at.timestamp())}:R>"


def build_balance_view(target: discord.abc.User, balance: dict) -> LayoutView:
    """
    Construit la vue d'affichage du solde d'un membre.

    Args:
        target: l'utilisateur ciblé (pour son mention/pseudo).
        balance: dict renvoyé par eco_manager.get_balance() — clés
            guild_id/user_id/balance/last_daily_at.
    """
    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay(
        f"# 💰 Solde · {target.display_name}\n-# {target.mention}"
    ))
    container.add_item(Separator())

    container.add_item(TextDisplay(
        f"### 🧮 Solde actuel\n## **{format_amount(balance['balance'])}**"
    ))
    container.add_item(Separator())

    container.add_item(TextDisplay(_daily_hint(balance.get("last_daily_at"))))
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
