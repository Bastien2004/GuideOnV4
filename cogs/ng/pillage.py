"""
Commande /ng pillage — Pays vulnérables sur un serveur NationsGlory.
"""
from __future__ import annotations

import asyncio
import logging
import urllib.parse
from datetime import UTC, datetime

import discord
import pandas as pd
from discord import app_commands, Interaction
from discord.ui import LayoutView, Container, TextDisplay, Separator, Button, ActionRow

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error

from utils.ng_server_choice import SERVER_CHOICES


# ============================================================
# 📁 Constantes
# ============================================================

log = logging.getLogger(__name__)

PER_PAGE       = 5
CACHE_DURATION = 1800

SHEET_ID   = "1dlBhp3YOJ6H3O_OEldXbuN4M_9BB2Gdawwj65iJqFUc"
SHEET_NAME = "SOUS POWER"
SHEET_URL  = (
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
    f"/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(SHEET_NAME)}"
)

REQUIRED_COLUMNS = ["nom", "serveur", "power", "nombre_de_claims"]


# ============================================================
# 🧊 Cache Google Sheets
# ============================================================

_cache_data      = None
_cache_timestamp = None
_cache_lock      = asyncio.Lock()


async def get_cached_sheet() -> pd.DataFrame:
    """Retourne le CSV avec cache sécurisé."""
    global _cache_data, _cache_timestamp

    now = datetime.now(UTC)

    async with _cache_lock:
        if (
            _cache_data is not None
            and _cache_timestamp is not None
            and (now - _cache_timestamp).total_seconds() < CACHE_DURATION
        ):
            return _cache_data

        try:
            loop = asyncio.get_running_loop()
            df   = await loop.run_in_executor(None, lambda: pd.read_csv(SHEET_URL))
            _cache_data      = df
            _cache_timestamp = now
            return df

        except Exception:
            log.exception("Erreur lors de la récupération des données de pillage")
            if _cache_data is not None:
                return _cache_data
            raise


# ============================================================
# 🧹 Préparation dataframe
# ============================================================

def prepare_df(raw_df: pd.DataFrame, serveur: str) -> pd.DataFrame | None:
    """Filtre et enrichit le dataframe pour un serveur."""
    df = raw_df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    if missing := [c for c in REQUIRED_COLUMNS if c not in df.columns]:
        raise ValueError(f"Colonnes manquantes dans la source : {missing}")

    df = df[df["serveur"].astype(str).str.lower().str.strip() == serveur].copy()

    df["power"]            = pd.to_numeric(df["power"],            errors="coerce").fillna(0)
    df["nombre_de_claims"] = pd.to_numeric(df["nombre_de_claims"], errors="coerce").fillna(0)
    df["sous_power"]       = df["power"] - df["nombre_de_claims"]

    df = df[df["power"] > 0].sort_values("sous_power").reset_index(drop=True)

    return df if not df.empty else None


# ============================================================
# 🔑 Custom ID
# ============================================================

def make_cid(serveur: str, page: int, owner_id: int) -> str:
    return f"ngp:{serveur}:{page}:{owner_id}"


def parse_cid(cid: str) -> tuple[str, int, int] | None:
    parts = cid.split(":")
    if len(parts) != 4 or parts[0] != "ngp":
        return None
    try:
        return parts[1], int(parts[2]), int(parts[3])
    except ValueError:
        return None


# ============================================================
# 🧱 Builder de page
# ============================================================

def build_page_view(df: pd.DataFrame, serveur: str, page: int, owner_id: int) -> LayoutView:
    """Construit la view d'une page du classement."""
    total_pages = max(1, (len(df) + PER_PAGE - 1) // PER_PAGE)
    page        = max(0, min(page, total_pages - 1))
    start       = page * PER_PAGE
    chunk       = df.iloc[start:start + PER_PAGE]

    view = LayoutView(timeout=1000)

    header = Container()
    header.add_item(TextDisplay(f"# <:lister:1495445288364675192> Pays vulnérables — {serveur.capitalize()}"))
    header.add_item(Separator())
    header.add_item(TextDisplay(f"Page **{page + 1} / {total_pages}** — {len(df)} pays trouvés"))
    header.add_item(Separator())
    view.add_item(header)

    content = Container()
    for _, row in chunk.iterrows():
        content.add_item(TextDisplay(
            f"### 🏳️ {row['nom']}\n"
            f"- **Power :** `{int(row['power'])}`\n"
            f"- **Claims :** `{int(row['nombre_de_claims'])}`\n"
            f"- **Sous-power :** `{int(row['sous_power'])}`"
        ))
        content.add_item(Separator())
    view.add_item(content)

    if total_pages > 1:
        nav      = Container()
        row_btns = ActionRow()

        if page > 0:
            row_btns.add_item(Button(
                label="⬅️ Précédent",
                style=discord.ButtonStyle.secondary,
                custom_id=make_cid(serveur, page - 1, owner_id),
            ))
        if page < total_pages - 1:
            row_btns.add_item(Button(
                label="Suivant ➡️",
                style=discord.ButtonStyle.secondary,
                custom_id=make_cid(serveur, page + 1, owner_id),
            ))

        nav.add_item(row_btns)
        view.add_item(nav)

    footer = Container()
    footer.add_item(Separator())
    footer.add_item(TextDisplay(
        "⚠️ Les données proviennent de **l'API officielle de NationsGlory** et peuvent être légèrement inexactes."
    ))
    footer.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(footer)

    return view


# ============================================================
# 🔄 Callbacks pagination
# ============================================================

def make_page_callback(serveur: str, page: int, owner_id: int):
    """Génère le callback pour un bouton de pagination."""
    async def callback(interaction: Interaction) -> None:
        if interaction.user.id != owner_id:
            await interaction.response.send_message(
                view=error_container("Tu n'es pas l'auteur de cette commande."),
                ephemeral=True,
            )
            return

        try:
            raw_df = await get_cached_sheet()
            df     = prepare_df(raw_df, serveur)
        except Exception:
            log.exception("Erreur rechargement cache pagination pillage")
            await interaction.response.send_message(
                view=error_container("Erreur lors du rechargement des données."),
                ephemeral=True,
            )
            return

        if df is None:
            await interaction.response.send_message(
                view=error_container("Aucun pays trouvé. Les données ont peut-être changé."),
                ephemeral=True,
            )
            return

        new_view = build_page_view(df, serveur, page, owner_id)
        attach_callbacks(new_view, df, serveur, page, owner_id)
        await interaction.response.edit_message(view=new_view)

    return callback


def attach_callbacks(view: LayoutView, df: pd.DataFrame, serveur: str, page: int, owner_id: int) -> None:
    """Injecte les callbacks sur les boutons de pagination."""
    for container in view.children:
        if not hasattr(container, "children"):
            continue
        for child in container.children:
            if hasattr(child, "children"):
                for btn in child.children:
                    if not hasattr(btn, "custom_id") or not btn.custom_id:
                        continue
                    parsed = parse_cid(btn.custom_id)
                    if not parsed:
                        continue
                    _, target_page, _ = parsed
                    btn.callback = make_page_callback(serveur, target_page, owner_id)


# ============================================================
# 🧭 Commande principale
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="pillage", description="🔫 Affiche les pays pillables sur un serveur")
@app_commands.choices(serveur=SERVER_CHOICES)
async def pillage(interaction: Interaction, serveur: str):

    # 🛡️ Vérification ban
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification activation
    if not await verifier_commande(interaction, "ng_pillage"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "ng_pillage")

    # 📦 Chargement et traitement des données
    try:
        serveur  = serveur.lower().strip()
        owner_id = interaction.user.id

        raw_df = await get_cached_sheet()
        df     = prepare_df(raw_df, serveur)

        if df is None:
            await interaction.followup.send(
                view=error_container(f"Aucun pays trouvé pour le serveur **{serveur.capitalize()}**."),
                ephemeral=True,
            )
            return

        view = build_page_view(df, serveur, 0, owner_id)
        attach_callbacks(view, df, serveur, 0, owner_id)

        await interaction.followup.send(view=view)

    except ValueError as e:
        await interaction.followup.send(
            view=error_container(str(e)),
            ephemeral=True,
        )

    except Exception:
        log.exception("Erreur commande /ng pillage")
        await interaction.followup.send(
            view=error_container("Une erreur est survenue."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@pillage.error
async def pillage_error(interaction: Interaction, error: app_commands.AppCommandError):
    await handle_app_command_error(interaction, error)