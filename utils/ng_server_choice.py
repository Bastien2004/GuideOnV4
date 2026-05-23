"""
Liste centralisée des serveurs NationsGlory.
"""

from __future__ import annotations

from discord import app_commands

# ============================================================
# 🌍 Serveurs NationsGlory
# ============================================================

SERVER_CHOICES_DATA: list[tuple[str, str]] = [
    ("💋 Alpha", "alpha"),
    ("🖤 Sigma", "sigma"),
    ("🩶 Omega", "omega"),
    ("💛 Delta", "delta"),
    ("💙 Epsilon", "epsilon"),
    ("🫧 Blue", "blue"),
    ("🍊 Orange", "orange"),
    ("🦺 Yellow", "yellow"),
    ("❄️ White", "white"),
    ("✒️ Black", "black"),
    ("🌀 Cyan", "cyan"),
    ("🥬 Lime", "lime"),
    ("🪸 Coral", "coral"),
    ("🍎 Red", "red"),
    ("🍄 Mocha", "mocha"),
    ("🍀 Jade", "jade"),
]


# ============================================================
# 📦 Choices Discord
# ============================================================

SERVER_CHOICES: list[app_commands.Choice[str]] = [
    app_commands.Choice(name=label, value=value)
    for label, value in SERVER_CHOICES_DATA
]