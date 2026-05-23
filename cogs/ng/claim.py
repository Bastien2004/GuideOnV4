"""
Commande /ng claim — Affiche le nombre de claims d'un pays.
"""

from __future__ import annotations

import asyncio
import logging
import os
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
# 📦 Constantes
# ============================================================

CACHE_DURATION = 1800
DEAD_IMAGE_PATH = os.path.join("source", "dead.png")

SHEET_ID = "1dlBhp3YOJ6H3O_OEldXbuN4M_9BB2Gdawwj65iJqFUc"
SHEET_NAME = "SOUS POWER"

log = logging.getLogger(__name__)


# ============================================================
# 🧊 Cache Google Sheets
# ============================================================

_cache_data = None
_cache_timestamp = None
_cache_lock = asyncio.Lock()


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
    url = build_sheet_url()

    return await loop.run_in_executor(None, lambda: pd.read_csv(url),)


# ============================================================
# 🧊 Cache sécurisé
# ============================================================

async def get_cached_sheet() -> pd.DataFrame:
    """Retourne le CSV avec cache sécurisé."""

    global _cache_data
    global _cache_timestamp

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

            _cache_data = df
            _cache_timestamp = now

            return df

        except Exception:
            log.exception("Erreur lors de la récupération des données de claims")

            if _cache_data is not None:
                return _cache_data

            raise


# ============================================================
# 🧹 Nettoyage dataframe
# ============================================================

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Nettoyage et normalisation."""

    df = df.loc[:, ~df.columns.str.match("^Unnamed")]
    df = df.rename(columns={"nombre de claims": "claims"})
    df.columns = df.columns.str.lower().str.strip()
    required_columns = ["pays", "serveur", "claims"]

    if any(col not in df.columns for col in required_columns):
        raise ValueError("Colonnes manquantes")

    df = df[required_columns]

    df["serveur"] = (df["serveur"].astype(str).str.lower().str.strip())
    df["pays"] = (df["pays"].astype(str).str.lower().str.strip())
    df["claims"] = pd.to_numeric(df["claims"], errors="coerce",)

    return df


# ============================================================
# 📊 Filtrage serveur
# ============================================================

def filter_server_dataframe(df: pd.DataFrame, serveur: str,) -> pd.DataFrame:
    """Filtre les données du serveur."""

    df_srv = df[(df["serveur"] == serveur) & df["claims"].notna()]

    if df_srv.empty:
        raise ValueError(
            f"Aucune donnée trouvée pour `{serveur}`."
        )

    return (df_srv.groupby("pays", as_index=False)["claims"].sum())


# ============================================================
# 📈 Calcul statistiques
# ============================================================

def compute_claim_stats(df_srv: pd.DataFrame, pays: str,) -> dict:
    """Calcule les statistiques du pays."""

    df_srv = (df_srv.sort_values(by="claims", ascending=False).reset_index(drop=True))
    row = df_srv[df_srv["pays"] == pays]

    if row.empty:
        raise ValueError("Pays introuvable")

    claim_value = int(row.iloc[0]["claims"])
    position = int(row.index[0] + 1)

    total_countries = len(df_srv)
    total_claims = int(df_srv["claims"].sum())

    pourcentage = (
        round((claim_value / total_claims) * 100, 2)
        if total_claims > 0
        else 0
    )

    top3 = df_srv.head(3)

    return {
        "claim_value": claim_value,
        "position": position,
        "total_countries": total_countries,
        "pourcentage": pourcentage,
        "top3": top3,
    }


# ============================================================
# 🏆 Construction top 3
# ============================================================

def build_top3_text(df: pd.DataFrame) -> str:
    """Construit le texte du top 3."""

    return "\n".join([
        f"**#{i + 1}** {row['pays'].title()} — `{int(row['claims'])}`"
        for i, row in df.iterrows()
    ])


# ============================================================
# 🧩 Construction view
# ============================================================

def build_claim_view(pays: str, serveur: str, stats: dict,) -> tuple[LayoutView, discord.File | None]:
    """Construit la view principale."""

    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(
        TextDisplay(
            f"# 🗺️ Claims — "
            f"{pays.title()} "
            f"({serveur.capitalize()})"
        )
    )

    container.add_item(Separator())

    container.add_item(
        TextDisplay(
            "## 📊 Statistiques du pays\n\n"
            f"- **Nombre de claims :** "
            f"`{stats['claim_value']}`\n"

            f"- **Classement :** "
            f"`#{stats['position']}` "
            f"sur `{stats['total_countries']}` pays\n"

            f"- **Part du serveur :** "
            f"`{stats['pourcentage']}%`\n"
        )
    )

    container.add_item(Separator())

    container.add_item(
        TextDisplay(
            "## 🏆 Top 3 du serveur\n\n"
            + build_top3_text(stats["top3"])
        )
    )

    container.add_item(Separator())

    container.add_item(
        TextDisplay("-# GuideOn Studio")
    )

    warning_container, file = build_ng_fiable_container()

    view.add_item(container)
    view.add_item(warning_container)

    return view, file


# ============================================================
# 📦 Chargement + traitement complet
# ============================================================

async def get_claim_data(serveur: str, pays: str,) -> dict:
    """Processus de chargement et traitement des données."""

    df = await get_cached_sheet()
    df = clean_dataframe(df)
    df_srv = filter_server_dataframe(df, serveur)

    return compute_claim_stats(df_srv, pays)


# ============================================================
# 🧭 Commande principale : /ng claim
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="claim", description="🗺️ Affiche le nombre de claims d'un pays")
@app_commands.describe(pays="Nom du pays",)
@app_commands.choices(serveur=SERVER_CHOICES)
async def claim(interaction: Interaction, serveur: str, pays: str,):

    # 🛡️ Vérification ban
    if not await verifier_ban_utilisateur(interaction):
        return
    
    # 🕒 Defer
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification activation
    if not await verifier_commande(interaction, "ng_claim"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "ng_claim")

    # 📦 Chargement et traitement des données
    try:

        serveur = serveur.lower().strip()
        pays = pays.lower().strip()
        stats = await get_claim_data(serveur, pays)

        view, file = build_claim_view(pays, serveur, stats)

        await interaction.followup.send(view=view, file=file,)

    except ValueError as e:

        await interaction.followup.send(
            view=error_container(str(e)),
            ephemeral=True,
        )

    except Exception:

        log.exception("Erreur commande /ng claim")

        await interaction.followup.send(
            view=error_container("Une erreur est survenue."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@claim.error
async def claim_error(interaction: Interaction, error: app_commands.AppCommandError):
    await handle_app_command_error(interaction, error)