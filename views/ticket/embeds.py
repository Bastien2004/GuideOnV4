"""
Builders d'embeds pour les tickets.

Pattern : 1 fonction = 1 embed. Pas de logique métier, juste de la mise en forme.
"""
import discord

from cogs.ticket._state import TicketPanelDraft
from utils.theme import Colors, Emoji


def build_setup_embed(draft: TicketPanelDraft) -> discord.Embed:
    """Embed du wizard de configuration d'un panel."""
    embed = discord.Embed(
        title=f"{Emoji.TICKET} Configuration d'un panel de tickets",
        description="Renseigne tous les champs obligatoires pour pouvoir publier le panel.",
        color=Colors.PRIMARY,
    )

    def fmt(value, prefix: str = "") -> str:
        if not value:
            return "*non défini*"
        return f"{prefix}{value}"

    embed.add_field(
        name="📝 Titre",
        value=fmt(draft.title),
        inline=False,
    )
    embed.add_field(
        name="📄 Description",
        value=fmt(draft.description[:200] + "..." if draft.description and len(draft.description) > 200 else draft.description),
        inline=False,
    )
    embed.add_field(
        name="📁 Catégorie d'ouverture",
        value=f"<#{draft.category_open_id}>" if draft.category_open_id else "*non défini*",
        inline=True,
    )
    embed.add_field(
        name="📜 Salon transcript",
        value=f"<#{draft.transcript_channel_id}>" if draft.transcript_channel_id else "*non défini*",
        inline=True,
    )
    embed.add_field(
        name="👮 Rôles staff",
        value=", ".join(f"<@&{r}>" for r in draft.staff_role_ids) or "*aucun*",
        inline=False,
    )

    if not draft.is_valid():
        embed.set_footer(text=f"⚠ Manque : {', '.join(draft.missing_fields())}")
    else:
        embed.set_footer(text="✅ Prêt à publier — clique sur Publier")

    return embed


def build_public_panel_embed(title: str, description: str) -> discord.Embed:
    """Embed du panel posé publiquement dans le salon."""
    embed = discord.Embed(
        title=title,
        description=description,
        color=Colors.PRIMARY,
    )
    embed.set_footer(text="Clique sur le bouton ci-dessous pour ouvrir un ticket")
    return embed
