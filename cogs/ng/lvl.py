"""
Commande /ng lvl — Affiche le niveau d'un pays sur un serveur NationsGlory.
"""
from __future__ import annotations

import asyncio
import logging
import urllib.parse
from datetime import UTC, datetime

import discord
import pandas as pd
from discord import app_commands, Interaction
from discord.ui import LayoutView, Container, TextDisplay, Separator

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error

from utils.ng_server_choice import SERVER_CHOICES
from utils.ng_fiable import build_ng_fiable_container


# ============================================================
# 📁 Constantes
# ============================================================

log = logging.getLogger(__name__)

CACHE_DURATION = 1800 # 30 minutes en secondes

SHEET_ID   = "1dlBhp3YOJ6H3O_OEldXbuN4M_9BB2Gdawwj65iJqFUc"
SHEET_NAME = "SOUS POWER"


# ============================================================
# 🧊 Cache Google Sheets
# ============================================================

_cache_data      = None
_cache_timestamp = None
_cache_lock      = asyncio.Lock()


# ============================================================
# 🌐 URL Google Sheets
# ============================================================

def build_sheet_url() -> str:
    """Construit l'URL CSV Google Sheets."""
    sheet_name = urllib.parse.quote(SHEET_NAME)
    return (
        f"https://docs.google.com/spreadsheets/d/"
        f"{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    )


# ============================================================
# 📥 Chargement CSV
# ============================================================

async def fetch_sheet_dataframe() -> pd.DataFrame:
    """Télécharge le dataframe Google Sheets."""
    loop = asyncio.get_running_loop()
    url  = build_sheet_url()
    return await loop.run_in_executor(None, lambda: pd.read_csv(url))


# ============================================================
# 🧊 Cache sécurisé
# ============================================================

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
            df = await fetch_sheet_dataframe()
            _cache_data      = df
            _cache_timestamp = now
            return df

        except Exception:
            log.exception("Erreur lors de la récupération des données de niveau")

            if _cache_data is not None:
                return _cache_data

            raise


# ============================================================
# 🧹 Nettoyage dataframe
# ============================================================

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Nettoyage et normalisation."""
    df = df.loc[:, ~df.columns.str.match("^Unnamed")]
    df.columns = df.columns.str.lower().str.strip()

    required_columns = ["pays", "serveur", "niveau"]
    if any(col not in df.columns for col in required_columns):
        raise ValueError("Nous n'avons pas pu récupérer ces données.")

    df = df[required_columns]
    df["serveur"] = df["serveur"].astype(str).str.lower().str.strip()
    df["pays"]    = df["pays"].astype(str).str.lower().str.strip()
    df["niveau"]  = pd.to_numeric(df["niveau"], errors="coerce")

    return df


# ============================================================
# 📊 Filtrage serveur
# ============================================================

def filter_server_dataframe(df: pd.DataFrame, serveur: str) -> pd.DataFrame:
    """Filtre les données du serveur."""
    df_srv = df[(df["serveur"] == serveur) & df["niveau"].notna()]

    if df_srv.empty:
        raise ValueError(f"Aucune donnée trouvée pour `{serveur}`.")

    return df_srv.groupby("pays", as_index=False)["niveau"].sum()


# ============================================================
# 📈 Calcul statistiques
# ============================================================

def compute_level_stats(df_srv: pd.DataFrame, pays: str) -> dict:
    """Calcule les statistiques de niveau du pays."""
    df_srv = df_srv.sort_values(by="niveau", ascending=False).reset_index(drop=True)
    row    = df_srv[df_srv["pays"] == pays]

    if row.empty:
        raise ValueError("Pays introuvable.")

    level_value = int(row.iloc[0]["niveau"])
    position    = int(row.index[0] + 1)
    total       = len(df_srv)
    top3        = df_srv.head(3)

    return {
        "level_value": level_value,
        "position":    position,
        "total":       total,
        "top3":        top3,
    }


# ============================================================
# 🏆 Construction top 3
# ============================================================

def build_top3_text(df: pd.DataFrame) -> str:
    """Construit le texte du top 3."""
    return "\n".join(
        f"**#{i + 1}** {row['pays'].title()} — `{int(row['niveau'])}`"
        for i, row in df.iterrows()
    )


# ============================================================
# 🧩 Construction view
# ============================================================

def build_lvl_view(pays: str, serveur: str, stats: dict) -> tuple[LayoutView, discord.File | None]:
    """Construit la view principale."""
    view      = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay(f"# 📈 Niveau — {pays.title()} ({serveur.capitalize()})"))
    container.add_item(Separator())

    container.add_item(TextDisplay(
        "## 📊 Statistiques du pays\n\n"
        f"- **Niveau :** `{stats['level_value']}`\n"
        f"- **Classement :** `#{stats['position']}` sur `{stats['total']}` pays\n"
    ))

    container.add_item(Separator())
    container.add_item(TextDisplay(
        "## 🏆 Top 3 du serveur\n\n"
        + build_top3_text(stats["top3"])
    ))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    warning_container, file = build_ng_fiable_container()

    view.add_item(container)
    view.add_item(warning_container)

    return view, file


# ============================================================
# 📦 Chargement + traitement complet
# ============================================================

async def get_level_data(serveur: str, pays: str) -> dict:
    """Processus de chargement et traitement des données."""
    df     = await get_cached_sheet()
    df     = clean_dataframe(df)
    df_srv = filter_server_dataframe(df, serveur)

    if pays not in df_srv["pays"].values:
        raise ValueError(f"Pays `{pays}` introuvable sur le serveur `{serveur}`.")

    return compute_level_stats(df_srv, pays)


# ============================================================
# 🧭 Commande principale
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="lvl", description="📈 Affiche le niveau d'un pays")
@app_commands.describe(pays="Nom du pays")
@app_commands.choices(serveur=SERVER_CHOICES)
async def lvl(interaction: Interaction, serveur: str, pays: str):

    # 🛡️ Vérification ban
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification activation
    if not await verifier_commande(interaction, "ng_lvl"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "ng_lvl")

    # 📦 Chargement et traitement des données
    try:
        serveur = serveur.lower().strip()
        pays    = pays.lower().strip()
        stats   = await get_level_data(serveur, pays)

        view, file = build_lvl_view(pays, serveur, stats)
        await interaction.followup.send(view=view, file=file)

    except ValueError as e:
        await interaction.followup.send(
            view=error_container(str(e)),
            ephemeral=True,
        )

    except Exception:
        log.exception("Erreur commande /ng lvl")
        await interaction.followup.send(
            view=error_container("Une erreur est survenue."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@lvl.error
async def lvl_error(interaction: Interaction, error: app_commands.AppCommandError):
    await handle_app_command_error(interaction, error)