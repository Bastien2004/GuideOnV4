"""
Commande /ng convert — Convertit une quantité d'items en stacks, coffres ou double-coffres.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction
from discord.ui import LayoutView, Container, TextDisplay, Separator

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

STACK_SIZE = 64
CHEST_SIZE = 27 * STACK_SIZE
DOUBLE_CHEST_SIZE = 54 * STACK_SIZE


# ============================================================
# 🔢 Fonctions utilitaires
# ============================================================

def _compute_stacks(quantite: int) -> tuple[str, str]:
    """Calcule la conversion en stacks."""
    stacks = quantite // STACK_SIZE
    reste = quantite % STACK_SIZE

    result = (
        f"📦 **Stacks complets :** `{stacks}`\n"
        f"🔹 **Items restants :** `{reste}`"
    )

    return result, "Stacks"


def _compute_chests(quantite: int) -> tuple[str, str]:
    """Calcule la conversion en coffres."""
    coffres = quantite // CHEST_SIZE
    reste = quantite % CHEST_SIZE
    stacks_restants = reste // STACK_SIZE
    items_restants = reste % STACK_SIZE

    result = (
        f"🪵 **Coffres complets :** `{coffres}`\n"
        f"📦 **Stacks restants :** `{stacks_restants}`\n"
        f"🔹 **Items restants :** `{items_restants}`"
    )

    return result, "Coffres"


def _compute_double_chests(quantite: int) -> tuple[str, str]:
    """Calcule la conversion en double-coffres."""
    dc = quantite // DOUBLE_CHEST_SIZE
    reste = quantite % DOUBLE_CHEST_SIZE
    stacks_restants = reste // STACK_SIZE
    items_restants = reste % STACK_SIZE

    result = (
        f"🪵 **Double-coffres complets :** `{dc}`\n"
        f"📦 **Stacks restants :** `{stacks_restants}`\n"
        f"🔹 **Items restants :** `{items_restants}`"
    )

    return result, "Double Coffres"


def compute_conversion(quantite: int, type_conversion: str) -> tuple[str, str]:
    """Dispatch vers le bon calcul selon le type de conversion."""
    match type_conversion:
        case "stack":
            return _compute_stacks(quantite)
        case "chest":
            return _compute_chests(quantite)
        case "dc":
            return _compute_double_chests(quantite)
        case _:
            raise ValueError("Type de conversion invalide.")



# ============================================================
# 🧩 Construction view
# ============================================================

def build_convert_view(quantite: int, conversion_label: str, result: str) -> LayoutView:
    """Construit la view principale."""
    view = LayoutView(timeout=VIEW_TIMEOUT)
    container = Container()

    container.add_item(TextDisplay("# 🧮 Conversion d'items"))
    container.add_item(Separator())

    container.add_item(TextDisplay(
        f"## <:info_2:1490329536892637204> __Informations__\n"
        f"- **Quantité totale :** `{quantite:,}` items\n"
        f"- **Conversion :** `{conversion_label}`"
    ))
    container.add_item(Separator())

    container.add_item(TextDisplay(f"## __💎 Résultat__\n{result}"))
    container.add_item(Separator())

    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 🧭 Commande principale
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="convert", description="🧮 Convertis un nombre d'items en stacks, coffres ou double-coffres")
@app_commands.describe(quantite="Nombre d'items à convertir", type_conversion="Type de conversion souhaité")
@app_commands.choices(
    type_conversion=[
        app_commands.Choice(name="Stacks", value="stack"),
        app_commands.Choice(name="Coffres", value="chest"),
        app_commands.Choice(name="Double Coffres", value="dc"),
    ]
)
async def convert(interaction: Interaction, quantite: int, type_conversion: str):

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer()
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "ng_convert"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "ng_convert")

    # 🔎 Vérification quantité.
    if quantite <= 0:
        await interaction.followup.send(
            view=error_container("La __quantité__ doit être un nombre **positif** ❗"),
            ephemeral=True,
        )
        return

    # 🧮 Calcul + Construction view.
    try:
        result, conversion_label = compute_conversion(quantite, type_conversion)
        view = build_convert_view(quantite, conversion_label, result)

        await interaction.followup.send(view=view)

    except ValueError as e:
        await interaction.followup.send(
            view=error_container(str(e)),
            ephemeral=True,
        )

    except Exception:
        log.exception("Erreur commande /ng convert")

        await interaction.followup.send(view=error_container("Une erreur est survenue."), ephemeral=True)


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@convert.error
async def convert_error(interaction: Interaction, error: app_commands.AppCommandError):
    await handle_app_command_error(interaction, error)