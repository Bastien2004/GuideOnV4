"""
utils/ng_server_choice.py - Liste centralisée des serveurs NationsGlory.
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
    ("🫐 Iris", "iris"),
    ("🫧 Blue", "blue"),
    ("❄️ White", "white"),
    ("✒️ Black", "black"),
    ("🌀 Cyan", "cyan"),
    ("🥬 Lime", "lime"),
    ("🪸 Coral", "coral"),
    ("🍄 Mocha", "mocha"),
    ("🍀 Jade", "jade"),
    ("🫘 Ruby", "ruby")
]

SERVER_CHOICES_BEDROCK : list[tuple[str, str]] = [
    ("💋 Alpha", "alpha"),
    ("🖤 Sigma", "sigma"),
    ("🩶 Omega", "omega"),
    ("💛 Delta", "delta"),
    ("💙 Epsilon", "epsilon"),
    ("🫐 Iris", "iris"),
]

SERVER_CHOICES_JAVA : list[tuple[str, str]] = [
    ("🫧 Blue", "blue"),
    ("❄️ White", "white"),
    ("✒️ Black", "black"),
    ("🌀 Cyan", "cyan"),
    ("🥬 Lime", "lime"),
    ("🪸 Coral", "coral"),
    ("🍄 Mocha", "mocha"),
    ("🍀 Jade", "jade"),
    ("🫘 Ruby", "ruby")
]


# ============================================================
# 📦 Choices Discord
# ============================================================

SERVER_CHOICES: list[app_commands.Choice[str]] = [
    app_commands.Choice(name=label, value=value)
    for label, value in SERVER_CHOICES_DATA
]

SERVER_CHOICES_BEDROCK: list[app_commands.Choice[str]] = [
    app_commands.Choice(name=label, value=value)
    for label, value in SERVER_CHOICES_BEDROCK
]

SERVER_CHOICES_JAVA: list[app_commands.Choice[str]] = [
    app_commands.Choice(name=label, value=value)
    for label, value in SERVER_CHOICES_JAVA
]