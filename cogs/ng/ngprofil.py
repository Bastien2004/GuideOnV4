"""
Commande /ng profil — Affiche le profil d'un joueur NationsGlory.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

import aiohttp
import discord
from discord import app_commands, Interaction, SelectOption
from discord.ui import LayoutView, Container, TextDisplay, Separator, ActionRow, Button, Select

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

VIEW_TIMEOUT = 600

NG_URL    = "https://publicapi.nationsglory.fr"
NG_TOKEN  = "NGAPI_0zR4vZ99KXm4)7KiH3%TdDAy%vsM)hD(bfa546d38f3f69b3c5d05ecf64bc5618"
NG_HEADERS = {"Authorization": NG_TOKEN, "Accept": "application/json"}

BEDROCK_SERVERS = {"alpha", "sigma", "omega", "epsilon", "delta"}

SKILL_TRANSLATIONS = {
    "Miner": "Mineur", "Lumberjack": "Bûcheron", "Farmer": "Fermier",
    "Builder": "Constructeur", "Hunter": "Chasseur", "Engineer": "Ingénieur",
}

SKILL_SEUILS_BE   = [10000, 25000, 90000, 150000, 200000]
SKILL_SEUILS_JAVA = {
    "Mineur":       [5000, 20000, 75000, 150000, 400000],
    "Bûcheron":     [5000, 20000, 50000, 100000, 200000],
    "Fermier":      [5000, 20000, 50000, 100000, 200000],
    "Constructeur": [5000, 20000, 50000, 100000, 200000],
    "Chasseur":     [5000, 20000, 50000, 100000, 200000],
    "Ingénieur":    [2500, 15000, 35000,  70000, 200000],
}

GRADE_PRIORITE = [
    "Fondateur", "Co-Fonda", "RespGameplay", "RespComm", "Dev", "RespAdmin", "Admin",
    "Supermodo", "Moderateur_Plus", "Moderateur", "Moderateur_Test", "Guide",
    "Affiliate", "Youtuber", "premium", "Legende", "Heros",
]


# ============================================================
# 🌐 API NationsGlory
# ============================================================

async def fetch_profil(pseudo: str) -> dict | None:
    """Récupère le profil d'un joueur via l'API NG. Retourne None si 404."""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            NG_URL.format(pseudo),
            headers=NG_HEADERS,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            if r.status == 200:
                return await r.json()
            if r.status == 404:
                return None
            r.raise_for_status()


# ============================================================
# 🔧 Helpers métier
# ============================================================

def format_playtime(seconds_total: int) -> str:
    """Formate un temps en secondes en chaîne lisible."""
    minutes = (seconds_total + 59) // 60
    months  = minutes // (30 * 24 * 60)
    days    = (minutes // (24 * 60)) % 30
    hours   = (minutes // 60) % 24
    mins    = minutes % 60
    parts   = []
    if months: parts.append(f"{months} mois")
    if days or months: parts.append(f"{days} j")
    if hours or days or months: parts.append(f"{hours} h")
    parts.append(f"{mins} min")
    return " ".join(parts)


def translate_skill(name: str) -> str:
    return SKILL_TRANSLATIONS.get(name.capitalize(), name)


def get_skill_level_be(xp: int) -> str:
    for niveau, seuil in enumerate(SKILL_SEUILS_BE):
        if xp < seuil:
            return f"Niveau {niveau}"
    return "Niveau 5"


def get_skill_level_java(xp: int, metier: str) -> str:
    seuils = SKILL_SEUILS_JAVA.get(metier, [])
    if not seuils:
        return "Inconnu"
    for i, seuil in enumerate(seuils):
        if xp < seuil:
            return f"Niveau {i}"
    return "Niveau 5"


def resolve_grade(groups: list, is_prime: bool) -> str:
    groups_lower = {g.lower() for g in groups}
    if "premium" in groups_lower and is_prime:
        return "Premium +"
    for g in GRADE_PRIORITE:
        if g.lower() in groups_lower:
            return g
    return "Joueur"


# ============================================================
# 🔑 Custom ID
# ============================================================

def make_select_cid(pseudo: str, serveur: str, section: str, owner_id: int) -> str:
    return f"ng_profil:{pseudo}:{serveur}:{section}:{owner_id}"


def parse_select_cid(custom_id: str) -> tuple[str, str, str, int] | None:
    parts = custom_id.split(":")
    if len(parts) != 5 or parts[0] != "ng_profil":
        return None
    try:
        return parts[1], parts[2], parts[3], int(parts[4])
    except ValueError:
        return None


# ============================================================
# 🧩 Builders de sections
# ============================================================

def build_section_general(data: dict) -> Container:
    c = Container()
    c.add_item(TextDisplay("## 📋 Informations générales"))
    c.add_item(Separator())

    created      = datetime.strptime(data["created_at"], "%Y-%m-%d %H:%M:%S")
    last_login   = datetime.strptime(data["last_connection"], "%Y-%m-%d %H:%M:%S")
    total_s      = sum((s.get("playtime") or 0) for s in data["servers"].values())
    playtime_str = format_playtime(total_s)
    grade        = resolve_grade(
        data.get("servers", {}).get("alpha", {}).get("groups") or [],
        data.get("is_prime", False),
    )
    bio          = (data.get("description") or "").strip()
    profil_link  = f"https://nationsglory.fr/profil/{data['username']}"

    c.add_item(TextDisplay(
        f"**👤 Pseudo :** `{data['username']}`\n"
        f"**📅 Inscription :** {created.strftime('%d/%m/%Y à %H:%M')}\n"
        f"**🔌 Dernière connexion :** {last_login.strftime('%d/%m/%Y à %H:%M')}\n"
        f"**🎖️ Grade :** {grade}\n"
        f"**⏱️ Temps de jeu (global) :** {playtime_str}\n"
        f"**📝 Description :** {bio or '*Aucune description.*'}\n"
        f"**🔗 Profil :** [Voir sur NationsGlory]({profil_link})"
    ))
    return c


def build_section_country(server: dict, serveur: str) -> Container:
    c = Container()
    c.add_item(TextDisplay(f"## 🏛️ Pays — {serveur.capitalize()}"))
    c.add_item(Separator())

    country_name = server.get("country") or "Aucun"
    country_rank = server.get("country_rank") or "—"
    power        = server.get("power") or 0
    max_power    = server.get("max_power") or 0
    desc         = (server.get("country_description") or "").strip()
    country_link = f"https://nationsglory.fr/country/{serveur}/{country_name.lower()}/about"

    c.add_item(TextDisplay(
        f"**🌍 Pays :** {country_name}\n"
        f"**🎖️ Rang dans le pays :** {country_rank}\n"
        f"**⚡ Power joueur :** {power} / {max_power}\n"
        f"**📜 Description :** {desc or '*Aucune description.*'}\n"
        f"**🔗 Pays :** [Voir sur NationsGlory]({country_link})"
    ))
    return c


def build_section_skills(server: dict, serveur: str) -> Container:
    c = Container()
    c.add_item(TextDisplay(f"## 🧠 Compétences — {serveur.capitalize()}"))
    c.add_item(Separator())

    raw_skills = server.get("skills") or []

    if not raw_skills:
        c.add_item(TextDisplay("*Aucune compétence enregistrée.*"))
        return c

    skills = (
        [{"name": k, "xp": v} for k, v in raw_skills.items()]
        if isinstance(raw_skills, dict)
        else raw_skills
    )

    be            = serveur in BEDROCK_SERVERS
    total_paliers = 0
    lines         = []

    for skill_data in sorted(skills, key=lambda x: x.get("xp", 0), reverse=True):
        name  = translate_skill(skill_data.get("name", "?"))
        xp    = skill_data.get("xp", 0)
        level = get_skill_level_be(xp) if be else get_skill_level_java(xp, name)
        try:
            total_paliers += int(level.split(" ")[1])
        except (IndexError, ValueError):
            pass
        lines.append(f"**{name}** : `{xp}` xp — {level}")

    lines.append(f"\n**🔢 Somme des paliers :** `{total_paliers}`")
    c.add_item(TextDisplay("\n".join(lines)))
    return c


# ============================================================
# 🧱 Dispatch sections
# ============================================================

def dispatch_section(data: dict, server: dict, serveur: str, section: str) -> Container:
    match section:
        case "general":
            return build_section_general(data)
        case "country":
            return build_section_country(server, serveur)
        case "skills":
            return build_section_skills(server, serveur)
        case _:
            c = Container()
            c.add_item(TextDisplay("❌ Section inconnue."))
            return c


# ============================================================
# 🧩 Construction view
# ============================================================

def build_profil_view(
    data: dict,
    server: dict,
    serveur: str,
    section: str,
    owner_id: int,
) -> LayoutView:
    """Construit la LayoutView complète du profil joueur."""
    pseudo = data["username"]
    view   = LayoutView(timeout=VIEW_TIMEOUT)

    header = Container()
    header.add_item(TextDisplay(f"# 👤 {pseudo} — {serveur.capitalize()}"))
    header.add_item(Separator())
    header.add_item(TextDisplay(
        f"Profil de **{pseudo}** sur le serveur **{serveur.capitalize()}** de __NationsGlory__."
    ))
    view.add_item(header)

    options = [
        SelectOption(label="📋 Général",    value=make_select_cid(pseudo, serveur, "general", owner_id), default=(section == "general")),
        SelectOption(label="🏛️ Pays",       value=make_select_cid(pseudo, serveur, "country", owner_id), default=(section == "country")),
        SelectOption(label="🧠 Compétences", value=make_select_cid(pseudo, serveur, "skills",  owner_id), default=(section == "skills")),
    ]

    select = Select(
        placeholder="Choisis une catégorie",
        options=options,
        custom_id=make_select_cid(pseudo, serveur, section, owner_id),
    )

    async def on_select(interaction: Interaction) -> None:
        if interaction.user.id != owner_id:
            await interaction.response.send_message(
                view=error_container("Tu n'es pas l'auteur de cette commande."),
                ephemeral=True,
            )
            return

        parsed = parse_select_cid(interaction.data["values"][0])
        if not parsed:
            return

        _, _, new_section, _ = parsed
        new_view = build_profil_view(data, server, serveur, new_section, owner_id)
        await interaction.response.edit_message(view=new_view)

    select.callback = on_select

    nav = Container()
    nav.add_item(ActionRow(select))
    view.add_item(nav)

    view.add_item(dispatch_section(data, server, serveur, section))

    footer = Container()
    footer.add_item(Separator())
    footer.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(footer)

    return view


# ============================================================
# 🧭 Commande principale
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="profil", description="👤 Obtenir les infos d'un joueur NationsGlory")
@app_commands.describe(pseudo="Nom du joueur", serveur="Serveur NationsGlory")
@app_commands.choices(serveur=SERVER_CHOICES)
async def ngprofil(interaction: Interaction, pseudo: str, serveur: str):

    # 🛡️ Vérification ban
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification activation
    if not await verifier_commande(interaction, "ng_profil"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "ng_profil")

    # 🧩 Récupération + construction view
    try:
        data = await fetch_profil(pseudo)

        if data is None:
            await interaction.followup.send(
                view=error_container(f"Le joueur **{pseudo}** est introuvable sur NationsGlory."),
                ephemeral=True,
            )
            return

        server = data["servers"].get(serveur.lower())

        if not server:
            await interaction.followup.send(
                view=error_container(
                    f"Le joueur **{pseudo}** n'a pas de données sur le serveur **{serveur.capitalize()}**.\n"
                    "Il n'y a peut-être jamais joué."
                ),
                ephemeral=True,
            )
            return

        view = build_profil_view(data, server, serveur, "general", interaction.user.id)
        await interaction.followup.send(view=view)

    except aiohttp.ClientConnectorError:
        await interaction.followup.send(
            view=error_container("⚠️ **L'API NationsGlory ne répond pas.**\nRéessaie dans quelques instants."),
            ephemeral=True,
        )

    except aiohttp.ServerTimeoutError:
        await interaction.followup.send(
            view=error_container("⚠️ **L'API NationsGlory a mis trop de temps à répondre.**\nRéessaie dans quelques instants."),
            ephemeral=True,
        )

    except Exception:
        log.exception("Erreur commande /ng profil")
        await interaction.followup.send(
            view=error_container("Une erreur est survenue."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@ngprofil.error
async def ngprofil_error(interaction: Interaction, error: app_commands.AppCommandError):
    await handle_app_command_error(interaction, error)