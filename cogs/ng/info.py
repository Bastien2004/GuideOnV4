"""
Commande /ng info — Informations NationsGlory.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction, SelectOption
from discord.ui import LayoutView, Container, TextDisplay, Separator, ActionRow, Select

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error


# ============================================================
# 📁 Constantes
# ============================================================

log = logging.getLogger(__name__)

VIEW_TIMEOUT = 600

CATEGORIES = {
    "discord": {
        "label": "💬 Discord NG",
        "content": (
            "**🌐 __Global__**\n"
            "- 🗺️ NationsGlory : https://discord.gg/nationsglory\n"
            "- 📻 NG-Radio : https://discord.gg/ngradio **(fermé)**\n"
            "- 🫖 NG US : https://discord.gg/QpA7XmEngG **(fermé)**\n\n"

            "**🎮 __Bedrock__**\n"
            "- 💓 Alpha : https://discord.gg/KxC9E2VPeX\n"
            "- 🖤 Sigma : https://discord.gg/RcJeepJB2V\n"
            "- 🩶 Oméga : https://discord.gg/cy48ux3Bk2\n"
            "- 💛 Delta : https://discord.gg/nationsglory-delta-948880111753625642\n"
            "- 💙 Epsilon : https://discord.gg/SAjHxuJTQY\n\n"

            "**💻 __Java__**\n"
            "- 🫧 Blue : https://discord.gg/wQgpfTzAwp\n"
            "- 🍊 Orange : https://discord.gg/HtET56bBQs\n"
            "- 🦺 Yellow : https://discord.gg/z8bBMnwTCW\n"
            "- ❄️ White : https://discord.gg/bf6bNkt2SM\n"
            "- ✒️ Black : https://discord.gg/Ck9s96FDCe\n"
            "- 🌀 Cyan : https://discord.gg/RxAjxtuE2U\n"
            "- 🥬 Lime : https://discord.gg/h54m7VqmWY\n"
            "- 🪸 Coral : https://discord.gg/mZx4CdqngA\n"
            "- 🦩 Pink : https://discord.gg/WXhRE2AN2Y **(fermé)**\n"
            "- 🫐 Purple : https://discord.gg/bbgqmJjQSB **(fermé)**\n"
            "- 🍋‍🟩 Green : https://discord.gg/kQHABDCF3W **(fermé)**\n"
            "- 🍎 Red : https://discord.gg/rYGPtgKkpt\n"
            "- 🍄 Mocha : https://discord.gg/zbTkjGFMZB\n"
            "- 🍀 Jade : https://discord.gg/fphbKQSrH9\n"
            "- ☎️ Ruby : https://discord.gg/W2qyJ8WNSs **(fermé)**"
        ),
    },
    "liens": {
        "label": "🔗 Liens NG",
        "content": (
            "- 🌐 **Site NG** : https://nationsglory.fr/\n"
            "- 💬 **Forum NG** : https://nationsglory.fr/forums\n"
            "- 📘 **Wiki NG** : https://wiki.nationsglory.fr/fr/\n"
            "- 📡 **Status NG** : https://status.nationsglory.fr/fr/\n"
            "- 🧭 **Site GuideON** : https://guideonbot.guideon.dev/"
        ),
    },
    "ip": {
        "label": "🌐 IP NGBE",
        "content": (
            "**✈️ HUB** : `bedrock.nationsglory.fr` | **19132**\n"
            "**⛏️ ISLAND** : `bedrock.nationsglory.fr` | **19112**\n\n"
            "**🔴 ALPHA** : `alpha.nationsglory.fr` | **19100**\n"
            "**⚫ SIGMA** : `sigma.nationsglory.fr` | **19102**\n"
            "**⚪ OMEGA** : `omega.nationsglory.fr` | **19103**\n"
            "**🟠 DELTA** : `delta.nationsglory.fr` | **19101**\n"
            "**🟣 EPSILON** : `epsilon.nationsglory.fr` | **19104**"
        ),
    },
    "niveau": {
        "label": "📈 Niveau de pays",
        "content": (
            "__Voici comment augmenter votre niveau de pays :__\n\n"
            "➡️ **Claim** : étendre son territoire.\n"
            "➡️ **T4 / T5** : posséder des missiles avancés.\n"
            "➡️ **Fusée** : posséder une fusée spatiale.\n"
            "➡️ **PIB** : développer son économie.\n"
            "➡️ **Power** : augmenter son power.\n"
            "➡️ **Skills** : monter ses métiers.\n"
            "➡️ **Recrutement** : recruter des joueurs.\n"
            "➡️ **Relations** : alliances & conquêtes."
        ),
    },
}


# ============================================================
# 🔑 Custom ID
# ============================================================

def make_select_cid(key: str, owner_id: int) -> str:
    return f"ng_info:{key}:{owner_id}"


def parse_select_value(value: str) -> tuple[str, int] | tuple[None, None]:
    if not value.startswith("ng_info:"):
        return None, None

    parts = value.split(":")
    if len(parts) != 3:
        return None, None

    _, key, owner = parts

    if key not in CATEGORIES:
        return None, None

    try:
        return key, int(owner)
    except ValueError:
        return None, None


# ============================================================
# 📦 Fonctions utilitaires
# ============================================================

def build_select(selected_key: str | None, owner_id: int) -> Select:
    """Construit le menu déroulant des catégories."""
    options = [
        SelectOption(
            label=cat["label"],
            value=make_select_cid(key, owner_id),
            default=(key == selected_key),
        )
        for key, cat in CATEGORIES.items()
    ]

    select = Select(
        placeholder="Choisis une catégorie 🌟",
        options=options,
        custom_id=f"ng_info_select:{owner_id}",
    )

    async def on_select(interaction: discord.Interaction):
        data   = interaction.data or {}
        values = data.get("values", [])

        if not values:
            await interaction.response.send_message(
                view=error_container("Interaction invalide."),
                ephemeral=True,
            )
            return

        key, owner = parse_select_value(values[0])

        if owner is None or interaction.user.id != owner:
            await interaction.response.send_message(
                view=error_container("Tu n'es pas l'auteur de cette commande."),
                ephemeral=True,
            )
            return

        try:
            view = build_info_view(key, owner)
            await interaction.response.edit_message(view=view)
        except Exception:
            log.exception("Erreur callback select /ng info")
            await interaction.response.send_message(
                view=error_container("Une erreur est survenue lors de l'interaction."),
                ephemeral=True,
            )

    select.callback = on_select
    return select


def build_info_view(selected_key: str | None = None, owner_id: int = 0) -> LayoutView:
    """Construit la LayoutView complète."""
    view = LayoutView(timeout=VIEW_TIMEOUT)

    header = Container()
    header.add_item(TextDisplay("# <:info_1:1490329502771839096> __Informations NationsGlory__"))
    header.add_item(Separator())
    view.add_item(header)

    row = ActionRow()
    row.add_item(build_select(selected_key, owner_id))
    view.add_item(row)

    if selected_key and selected_key in CATEGORIES:
        cat     = CATEGORIES[selected_key]
        content = Container()
        content.add_item(TextDisplay(f"## {cat['label']}"))
        content.add_item(Separator())
        content.add_item(TextDisplay(cat["content"]))
        content.add_item(Separator())
        content.add_item(TextDisplay("-# GuideOn Studio"))
        view.add_item(content)
    else:
        intro = Container()
        intro.add_item(TextDisplay("⬆️ Sélectionne une **catégorie** dans le menu ci-dessus."))
        intro.add_item(Separator())
        intro.add_item(TextDisplay("-# GuideOn Studio"))
        view.add_item(intro)

    return view


# ============================================================
# 🧭 Commande principale
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="info", description="📌 Informations NationsGlory")
async def info(interaction: Interaction):

    # 🛡️ Vérification ban
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification activation
    if not await verifier_commande(interaction, "ng_info"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "ng_info")

    # 🧩 Construction view
    view = build_info_view(owner_id=interaction.user.id)
    await interaction.followup.send(view=view)


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@info.error
async def info_error(interaction: Interaction, error: app_commands.AppCommandError):
    await handle_app_command_error(interaction, error)