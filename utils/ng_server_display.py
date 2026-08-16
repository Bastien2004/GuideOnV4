"""
utils/ng_server_display.py — Constantes d'affichage par serveur NationsGlory.
"""

from __future__ import annotations

SERVER_EMOJIS: dict[str, str] = {
    "alpha": "<:Alpha:1500414179650048070>",
    "delta": "<:Delta:1500414247098650725>",
    "sigma": "<:Sigma:1500414355773329548>",
    "omega": "<:Omega:1500414132560723978>",
    "epsilon": "<:Epsilon:1500414274999418970>",
}

DEFAULT_SERVER_EMOJI = "🌐"


def get_server_emoji(server_name: str) -> str:
    """Emoji d'affichage pour un serveur NG."""
    return SERVER_EMOJIS.get(server_name, DEFAULT_SERVER_EMOJI)