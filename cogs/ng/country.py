"""
Commande /ng country — Dashboard complet d'un pays NationsGlory.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import aiohttp
import discord
from discord import app_commands, Interaction
from discord.ui import LayoutView, Container, TextDisplay, Separator, Button

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

NG_URL    = "https://publicapi.nationsglory.fr"
NG_TOKEN  = "NGAPI_0zR4vZ99KXm4)7KiH3%TdDAy%vsM)hD(bfa546d38f3f69b3c5d05ecf64bc5618"
NG_HEADERS = {"Authorization": NG_TOKEN, "Accept": "application/json"}

NG_BASE_WEEK   = 2891
NG_BASE_DATE   = datetime(2025, 6, 9, tzinfo=timezone.utc)

SECTIONS = [
    ("🏠 Accueil",    "home"),
    ("👥 Membres",    "members"),
    ("⚔️ Relations",  "relations"),
    ("📊 Notations",  "notations"),
    ("🏛️ Note Archi", "archi"),
]

ARCHI_CRITERES = [
    ("📊 Activité récente",   "activite_recente",       4),
    ("🎨 Cohérence du style", "coherence_style",        2),
    ("💡 Lumières",           "coherence_lumieres",     1),
    ("⚒️ Terraforming",       "terraforming",           2),
    ("🧱 Catalogue",          "blocs_catalogue",        2),
    ("📏 Surface",            "surface_construite",     2),
    ("💥 Missiles",           "trou_missiles",         -4),
    ("🏠 Habitabilité",       "habitabilite_maison",    2),
    ("🏞️ Biome",              "biome_coherent",         1),
    ("🏚️ Abandonnés",         "batiments_abandonnes",   1),
    ("🌄 Réalisme",           "terraforming_realiste",  1),
    ("📐 Schematica",         "utilisation_schematica", -1),
    ("🧬 Roleplay",           "roleplay_pays",          1),
    ("🌳 Organiques",         "organics",               1),
    ("🌸 Beauté",             "beaute",                 4),
]

MEMBERS_PER_PAGE   = 10
RELATIONS_PER_PAGE = 10


# ============================================================
# 🌐 API NationsGlory
# ============================================================

async def api_get(endpoint: str) -> dict | None:
    """Requête GET sur l'API NG."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(NG_URL + endpoint, headers=NG_HEADERS) as r:
                return await r.json() if r.status == 200 else None
    except Exception:
        log.exception("Erreur API NG GET %s", endpoint)
        return None


async def api_get_notations(server: str, country: str, week: int) -> list | None:
    """Requête GET notations sur l'API NG."""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{NG_URL}/notations?week={week}&country={country}&server={server}"
            async with session.get(url, headers=NG_HEADERS) as r:
                return await r.json() if r.status == 200 else None
    except Exception:
        log.exception("Erreur API NG notations %s/%s", server, country)
        return None


# ============================================================
# 📆 Semaine NationsGlory
# ============================================================

def get_current_week_info() -> tuple[int, datetime.date, datetime.date]:
    """Retourne le numéro de semaine NG et ses dates de début/fin."""
    today  = datetime.now(timezone.utc)
    monday = today - timedelta(days=today.weekday())
    week   = NG_BASE_WEEK + ((monday - NG_BASE_DATE).days // 7)
    return week, monday.date(), (monday + timedelta(days=6)).date()


# ============================================================
# 🔑 Custom ID (format : ngc:{server}:{country}:{section}:{page}:{owner_id})
# ============================================================

def make_cid(server: str, country: str, section: str, page: int, owner_id: int) -> str:
    return f"ngc:{server}:{country}:{section}:{page}:{owner_id}"


def parse_cid(custom_id: str) -> tuple[str, str, str, int, int] | None:
    parts = custom_id.split(":")
    if len(parts) != 6 or parts[0] != "ngc":
        return None
    try:
        return parts[1], parts[2], parts[3], int(parts[4]), int(parts[5])
    except Exception:
        return None


# ============================================================
# 🧱 Blocs UI réutilisables
# ============================================================

def build_header(server: str, country: str) -> Container:
    c = Container()
    c.add_item(TextDisplay(f"# 🌍 {country.title()} — {server.capitalize()}"))
    c.add_item(Separator())
    return c


def build_footer() -> Container:
    c = Container()
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))
    return c


def build_nav(server: str, country: str, current: str, owner_id: int) -> Container:
    c = Container()
    for label, section in SECTIONS:
        style = discord.ButtonStyle.primary if section == current else discord.ButtonStyle.secondary
        c.add_item(Button(
            label=label,
            style=style,
            custom_id=make_cid(server, country, section, 0, owner_id),
        ))
    return c


def build_pagination(server: str, country: str, section: str, page: int, has_prev: bool, has_next: bool) -> Container:
    """Construit la rangée de pagination."""
    row = Container()
    if has_prev:
        row.add_item(Button(
            label="⬅️",
            style=discord.ButtonStyle.secondary,
            custom_id=make_cid(server, country, section, page - 1, 0),
        ))
    if has_next:
        row.add_item(Button(
            label="➡️",
            style=discord.ButtonStyle.secondary,
            custom_id=make_cid(server, country, section, page + 1, 0),
        ))
    return row


# ============================================================
# 🧩 Sections
# ============================================================

async def build_section_home(server: str, country: str) -> Container:
    data = await api_get(f"/country/{server}/{country}")
    c = Container()
    c.add_item(TextDisplay("## 🏠 Accueil"))
    c.add_item(Separator())

    if not data:
        c.add_item(TextDisplay("❌ Impossible de récupérer les informations du pays."))
        return c

    bank = data.get("bank", 0)
    c.add_item(TextDisplay(
        f"**👑 Leader :** {data.get('leader', 'Inconnu')}\n"
        f"**👥 Population :** {data.get('count_members', '?')}\n"
        f"**🏦 Banque :** {bank:,} $\n"
        f"**🛡️ Niveau :** {data.get('level', '?')}"
    ))

    desc = (data.get("description") or "").strip()
    if desc:
        c.add_item(Separator())
        c.add_item(TextDisplay(f"### 📝 Description\n{desc}"))

    return c


async def build_section_members(server: str, country: str, page: int) -> Container:
    data = await api_get(f"/country/{server}/{country}")
    c = Container()
    c.add_item(TextDisplay("## 👥 Membres"))
    c.add_item(Separator())

    if not data:
        c.add_item(TextDisplay("❌ Impossible de récupérer les membres."))
        return c

    members = [m for m in data.get("members", []) if m]
    total   = len(members)

    if not total:
        c.add_item(TextDisplay("*Aucun membre.*"))
        return c

    start = page * MEMBERS_PER_PAGE
    slc   = members[start:start + MEMBERS_PER_PAGE]

    c.add_item(TextDisplay(
        f"*Page {page + 1} — {total} membre(s)*\n"
        + "\n".join(f"• {m}" for m in slc)
    ))

    has_prev = page > 0
    has_next = start + MEMBERS_PER_PAGE < total

    if has_prev or has_next:
        c.add_item(Separator())
        c.add_item(build_pagination(server, country, "members", page, has_prev, has_next))

    return c


async def build_section_relations(server: str, country: str, page: int) -> Container:
    data = await api_get(f"/country/{server}/{country}")
    c = Container()
    c.add_item(TextDisplay("## ⚔️ Relations"))
    c.add_item(Separator())

    if not data:
        c.add_item(TextDisplay("❌ Impossible de récupérer les relations."))
        return c

    allies   = [(r, "🤝 Allié")   for r in data.get("allies",   []) if r]
    enemies  = [(r, "⚔️ Ennemi")  for r in data.get("enemies",  []) if r]
    colonies = [(r, "🏴 Colonie") for r in data.get("colonies", []) if r]
    all_rel  = allies + enemies + colonies
    total    = len(all_rel)

    if not total:
        c.add_item(TextDisplay("*Aucune relation.*"))
        return c

    start = page * RELATIONS_PER_PAGE
    slc   = all_rel[start:start + RELATIONS_PER_PAGE]

    c.add_item(TextDisplay(
        f"*Page {page + 1} — {total} relation(s)*\n"
        + "\n".join(f"{badge} {name}" for name, badge in slc)
    ))

    has_prev = page > 0
    has_next = start + RELATIONS_PER_PAGE < total

    if has_prev or has_next:
        c.add_item(Separator())
        c.add_item(build_pagination(server, country, "relations", page, has_prev, has_next))

    return c


async def build_section_notations(server: str, country: str) -> Container:
    week, start, end = get_current_week_info()
    data = await api_get_notations(server, country, week)
    c = Container()
    c.add_item(TextDisplay(f"## 📊 Notations — Semaine {week}"))
    c.add_item(TextDisplay(f"*Du {start.strftime('%d/%m/%Y')} au {end.strftime('%d/%m/%Y')}*"))
    c.add_item(Separator())

    if not data or not isinstance(data, list) or not data:
        c.add_item(TextDisplay("❌ Impossible de récupérer les notations."))
        return c

    s           = data[0]
    money_plus  = s.get("money_plus",  0) or 0
    money_minus = s.get("money_minus", 0) or 0

    c.add_item(TextDisplay(
        f"**🏆 Position :** {s.get('position', '?')}\n"
        f"**👥 Joueurs :** {s.get('nb_players', '?')} (+{s.get('nb_newplayers', 0)} nouveaux)\n"
        f"**💰 Banque :** {(s.get('money') or 0):,} $\n"
        f"**💸 Gains / Pertes :** +{money_plus:,} / -{money_minus:,} $\n"
        f"**🏦 CA :** {(s.get('turnover') or 0):,} $\n"
        f"**📈 PIB :** {(s.get('pib') or 0):,} $\n"
        f"**💹 Bourse :** {(s.get('bourse') or 0):,} $\n"
        f"**⚡ Power :** {s.get('power', '?')} / {s.get('power_max', '?')}\n"
    ))

    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"**🛠️ Activité :** {s.get('activity', '?')}/10\n"
        f"**🏛️ Gestion :** {s.get('gestion', '?')}/10\n"
        f"**🧠 Skills :** {s.get('skills', '?')}/10\n"
        f"**📊 Économie :** {s.get('econ', '?')}/10\n"
        f"**🛡️ Militaire :** {s.get('military', '?')}/10\n"
        f"**🏅 Score total :** {s.get('total', '?')}"
    ))

    return c


async def build_section_archi(server: str, country: str) -> Container:
    week, _, _ = get_current_week_info()
    data = await api_get_notations(server, country, week)
    c = Container()
    c.add_item(TextDisplay("## 🏛️ Note Architecturale"))
    c.add_item(Separator())

    if not data or not isinstance(data, list) or not data:
        c.add_item(TextDisplay("❌ Impossible de récupérer la note archi."))
        return c

    note  = data[0]
    lines = "\n".join(
        f"**{label} :** {note.get(key, 0)} / {maxv}"
        for label, key, maxv in ARCHI_CRITERES
    )
    c.add_item(TextDisplay(lines))
    return c


# ============================================================
# 🧩 Dispatch sections
# ============================================================

async def dispatch_section(server: str, country: str, section: str, page: int) -> Container:
    """Retourne le container de la section demandée."""
    match section:
        case "home":
            return await build_section_home(server, country)
        case "members":
            return await build_section_members(server, country, page)
        case "relations":
            return await build_section_relations(server, country, page)
        case "notations":
            return await build_section_notations(server, country)
        case "archi":
            return await build_section_archi(server, country)
        case _:
            c = Container()
            c.add_item(TextDisplay("❌ Section inconnue."))
            return c


# ============================================================
# 🔧 Correction owner_id dans la pagination
# ============================================================

def patch_owner_id(content: Container, owner_id: int) -> None:
    """Réinjecte l'owner_id dans les boutons de pagination générés sans lui."""
    for item in content.children:
        if isinstance(item, Button):
            parsed = parse_cid(item.custom_id)
            if parsed:
                s, ctry, sec, pg, _ = parsed
                item.custom_id = make_cid(s, ctry, sec, pg, owner_id)


# ============================================================
# 🧱 Builder principal
# ============================================================

async def build_country_view(server: str, country: str, section: str, page: int, owner_id: int) -> LayoutView:
    """Construit la LayoutView complète du dashboard pays."""
    view = LayoutView(timeout=VIEW_TIMEOUT)

    view.add_item(build_header(server, country))
    view.add_item(build_nav(server, country, section, owner_id))

    content = await dispatch_section(server, country, section, page)
    patch_owner_id(content, owner_id)
    view.add_item(content)

    view.add_item(build_footer())

    return view


# ============================================================
# 🔄 Callback interactions (boutons navigation / pagination)
# ============================================================

async def handle_country_interaction(interaction: discord.Interaction) -> None:
    cid    = (interaction.data or {}).get("custom_id")
    parsed = parse_cid(cid)

    if not parsed:
        return

    server, country, section, page, owner_id = parsed

    if interaction.user.id != owner_id:
        await interaction.response.send_message(
            view=error_container("Tu n'es pas l'auteur de cette commande."),
            ephemeral=True,
        )
        return

    try:
        view = await build_country_view(server, country, section, page, owner_id)
        await interaction.response.edit_message(view=view)
    except Exception:
        log.exception("Erreur callback country %s/%s section=%s", server, country, section)
        await interaction.response.send_message(
            view=error_container("Une erreur est survenue."),
            ephemeral=True,
        )


# ============================================================
# 🔗 Setup callbacks
# ============================================================

def setup_country_callbacks(bot: discord.Client) -> None:
    @bot.listen("on_interaction")
    async def _(interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            await handle_country_interaction(interaction)


# ============================================================
# 🧭 Commande principale
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="country", description="🌍 Information complète d'un pays NG")
@app_commands.describe(serveur="Nom du serveur", pays="Nom du pays")
async def country(interaction: Interaction, serveur: str, pays: str):

    # 🛡️ Vérification ban
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification activation
    if not await verifier_commande(interaction, "ng_country"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "ng_country")

    # 🧩 Construction view
    try:
        view = await build_country_view(
            serveur,
            pays.strip().lower(),
            "home",
            0,
            interaction.user.id,
        )
        await interaction.followup.send(view=view)

    except Exception:
        log.exception("Erreur commande /ng country")
        await interaction.followup.send(
            view=error_container("Une erreur est survenue."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@country.error
async def country_error(interaction: Interaction, error: app_commands.AppCommandError):
    await handle_app_command_error(interaction, error)