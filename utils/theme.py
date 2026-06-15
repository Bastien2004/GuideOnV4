"""
Thème visuel centralisé.

Toute couleur d'embed et tout emoji utilisé dans plusieurs endroits DOIT venir d'ici.
Si tu changes la charte du bot, tu changes ce fichier, point.

Usage :
    from utils.theme import Colors, Emoji
    embed = discord.Embed(color=Colors.PRIMARY)
"""
import discord


class Colors:
    """Palette officielle GuideON."""

    PRIMARY = discord.Color.from_rgb(255, 181, 71)      # ambre
    SUCCESS = discord.Color.from_rgb(74, 222, 128)      # vert
    DANGER = discord.Color.from_rgb(248, 113, 113)      # rouge
    WARNING = discord.Color.from_rgb(251, 191, 36)      # jaune
    INFO = discord.Color.from_rgb(96, 165, 250)         # bleu
    NEUTRAL = discord.Color.from_rgb(138, 150, 167)     # gris


class Emoji:
    """Emojis utilisés dans plusieurs systèmes."""

    # Génériques
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    LOADING = "⏳"

    # Navigation
    PREV = "◀"
    NEXT = "▶"
    REFRESH = "🔄"
    BACK = "🔙"

    # Domaines
    TICKET = "🎫"
    GIVEAWAY = "🎁"
    EXP = "🧩"
    INVITE = "✉️"
    MOD = "🛡️"
    NG = "🌍"
    ANNIV = "🎂"
    BOUTIQUE = "🛒"