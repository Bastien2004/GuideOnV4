"""
Commande /ng classement — Affiche les classements des serveurs NationsGlory (niveau, MMR, claims).
"""
from __future__ import annotations

import asyncio
import logging
import urllib.parse
from datetime import UTC, datetime

import discord
import pandas as pd
from discord import app_commands, Interaction
from discord.ui import LayoutView, Container, TextDisplay, Separator, Button

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

CACHE_DURATION = 1800

SHEET_ID   = "1dlBhp3YOJ6H3O_OEldXbuN4M_9BB2Gdawwj65iJqFUc"
SHEET_NAME = "SOUS POWER"

CLASSEMENTS = {
    "niveau": ("Niveaux", "niv."),
    "mmr":    ("MMR",     "MMR"),
    "claims": ("Claims",  "claims"),
}


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
            log.exception("Erreur lors de la récupération des données de classement")

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
    df.columns    = df.columns.str.lower().str.strip()
    df["serveur"] = df["serveur"].astype(str).str.lower().str.strip()
    df["pays"]    = df["pays"].astype(str).str.lower().str.strip()
    return df


# ============================================================
# 🔑 Custom ID
# ============================================================

def make_cid(serveur: str, colonne: str, owner_id: int) -> str:
    return f"ngc_cls:{serveur}:{colonne}:{owner_id}"


def parse_cid(custom_id: str) -> tuple[str, str, int] | None:
    parts = custom_id.split(":")
    if len(parts) != 4 or parts[0] != "ngc_cls":
        return None
    try:
        return parts[1], parts[2], int(parts[3])
    except Exception:
        return None


# ============================================================
# 📊 Génération classement
# ============================================================

def generate_classement(df: pd.DataFrame, serveur: str, colonne: str, suffixe: str) -> dict | None:
    """Calcule le top 10 et les stats d'une colonne pour un serveur."""
    if colonne not in df.columns:
        return None

    df[colonne] = pd.to_numeric(df[colonne], errors="coerce")
    df_srv      = df[(df["serveur"] == serveur) & df[colonne].notna()]

    if df_srv.empty:
        return None

    df_srv = df_srv.groupby("pays", as_index=False)[colonne].sum()
    df_srv = df_srv.sort_values(by=colonne, ascending=False).reset_index(drop=True)
    top10  = df_srv.head(10)

    medals = ["🥇", "🥈", "🥉"]
    lines  = [
        f"**{medals[i] if i < 3 else f'{i + 1}.'} {row['pays'].title()}** "
        f"— {int(row[colonne]):,} {suffixe}".replace(",", " ")
        for i, row in top10.iterrows()
    ]

    return {
        "lines":   lines,
        "moyenne": round(df_srv[colonne].mean(), 2),
        "mediane": round(df_srv[colonne].median(), 2),
    }


# ============================================================
# 🧩 Construction views
# ============================================================

def build_accueil_view(serveur: str, owner_id: int) -> LayoutView:
    """Construit la view d'accueil avec les boutons de navigation."""
    view = LayoutView(timeout=600)

    header = Container()
    header.add_item(TextDisplay(f"# 📊 Classements — {serveur.capitalize()}"))
    header.add_item(Separator())
    header.add_item(TextDisplay("Choisissez un classement ci-dessous."))
    header.add_item(Separator())
    header.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(header)

    btns = Container()
    for colonne, (titre, _) in CLASSEMENTS.items():
        btns.add_item(Button(
            label=titre,
            style=discord.ButtonStyle.primary,
            custom_id=make_cid(serveur, colonne, owner_id),
        ))
    view.add_item(btns)

    return view


def build_classement_view(
    df: pd.DataFrame,
    serveur: str,
    colonne: str,
    titre: str,
    suffixe: str,
    owner_id: int,
) -> tuple[LayoutView, discord.File | None]:
    """Construit la view d'un classement."""
    result = generate_classement(df, serveur, colonne, suffixe)

    if result is None:
        view = LayoutView(timeout=600)
        view.add_item(error_container("Aucune donnée trouvée pour ce classement."))
        return view, None

    view = LayoutView(timeout=600)

    main = Container()
    main.add_item(TextDisplay(f"# 🏆 Classement — {titre} ({serveur.capitalize()})"))
    main.add_item(Separator())
    main.add_item(TextDisplay("## 🔝 Top 10\n" + "\n".join(result["lines"])))
    main.add_item(Separator())
    main.add_item(TextDisplay(
        f"## 📊 Statistiques\n"
        f"- Moyenne : `{result['moyenne']}`\n"
        f"- Médiane : `{result['mediane']}`"
    ))
    main.add_item(Separator())
    main.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(main)

    warning_container, file = build_ng_fiable_container()
    view.add_item(warning_container)

    back = Container()
    back.add_item(Button(
        label="⬅️ Retour",
        style=discord.ButtonStyle.secondary,
        custom_id=make_cid(serveur, "accueil", owner_id),
    ))
    view.add_item(back)

    return view, file


# ============================================================
# 🔄 Callback interactions
# ============================================================

async def handle_classement_interaction(interaction: Interaction, df: pd.DataFrame) -> None:
    cid    = (interaction.data or {}).get("custom_id")
    parsed = parse_cid(cid)

    if not parsed:
        return

    serveur, colonne, owner_id = parsed

    if interaction.user.id != owner_id:
        await interaction.response.send_message(
            view=error_container("Tu n'es pas l'auteur de cette commande."),
            ephemeral=True,
        )
        return

    try:
        if colonne == "accueil":
            view = build_accueil_view(serveur, owner_id)
            await interaction.response.edit_message(view=view, attachments=[])
            return

        titre, suffixe = CLASSEMENTS[colonne]
        view, file     = build_classement_view(df, serveur, colonne, titre, suffixe, owner_id)

        if file:
            await interaction.response.edit_message(view=view, attachments=[file])
        else:
            await interaction.response.edit_message(view=view)

    except Exception:
        log.exception("Erreur callback classement %s/%s", serveur, colonne)
        await interaction.response.send_message(
            view=error_container("Une erreur est survenue."),
            ephemeral=True,
        )


# ============================================================
# 🔗 Setup callbacks
# ============================================================

def setup_classement_callbacks(bot: discord.Client) -> None:
    @bot.listen("on_interaction")
    async def _(interaction: Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        df = getattr(interaction.client, "_ngclassement_df", None)
        if df is None:
            return
        await handle_classement_interaction(interaction, df)


# ============================================================
# 🧭 Commande principale
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="classement", description="📊 Classements serveurs NationsGlory")
@app_commands.choices(serveur=SERVER_CHOICES)
async def ngclassement(interaction: Interaction, serveur: str):

    # 🛡️ Vérification ban
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification activation
    if not await verifier_commande(interaction, "ng_classement"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "ng_classement")

    # 📦 Chargement et traitement des données
    try:
        df = await get_cached_sheet()
        df = clean_dataframe(df)

        interaction.client._ngclassement_df = df

        view = build_accueil_view(serveur.lower().strip(), interaction.user.id)
        await interaction.followup.send(view=view)

    except Exception:
        log.exception("Erreur commande /ng classement")
        await interaction.followup.send(
            view=error_container("Une erreur est survenue."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@ngclassement.error
async def ngclassement_error(interaction: Interaction, error: app_commands.AppCommandError):
    await handle_app_command_error(interaction, error)