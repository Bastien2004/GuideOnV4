"""
views/wiki/wiki_view.py — Interface Components V2 du /wiki GuideON.

Architecture :
    WikiHomeView      : accueil (stats bot + partenariat + menu catégorie + nav)
    WikiCategoryView  : liste des commandes d'une catégorie (paginée)
    WikiSupportView   : infos support (Discord, site, email)
    WikiLinksView     : liens utiles

Interactions : tous les callbacks sont assignés directement sur les boutons/
selects de chaque vue — pas de on_interaction global, conforme à la
convention V4. Sécurité owner-check sur toutes les vues interactives.
"""
from __future__ import annotations

from datetime import timedelta

import discord
from discord import ButtonStyle, SelectOption
from discord.ui import ActionRow, Button, Container, Section, Select, Separator, TextDisplay

from utils.datetime_utils import format_duration
from utils.uptime import uptime_seconds
from views._components.base_view import BaseLayoutView

# ═══════════════════════════════════════════════════════════════
# 📋 Liste des commandes
# ═══════════════════════════════════════════════════════════════

CATEGORIES: dict[str, dict] = {
    "birthday": {
        "name": "Birthday", "emoji": "🎂",
        "description": "Commandes d'anniversaire",
        "available": True,
        "commands": [
            ("birthday add",    "🎂 Enregistre ta date d'anniversaire"),
            ("birthday config", "🎂 Configure le système d'anniversaires"),
            ("birthday list",   "🎂 [VIP] Affiche les anniversaires des 30 prochains jours"),
            ("birthday next",   "🎂 [VIP] Affiche le prochain anniversaire à venir"),
        ],
    },
    "utility": {
        "name": "Utilitaire", "emoji": "🔧",
        "description": "Outils pratiques du quotidien",
        "available": True,
        "commands": [
            ("id",        "👤 Récupère les informations d'un utilisateur via son ID ou sa mention"),
            ("info",      "❔ Découvre GuideOn Bot"),
            ("ping",      "🏓 Affiche la latence du bot"),
            ("report",    "⚠️ Signale un bug ou un problème"),
            ("timestamp", "⏱️ Convertit une date en timestamp Discord"),
            ("user",      "👤 Affiche le profil d'un membre du serveur"),
            ("wiki",      "📖 Consulte le wiki de GuideOn Bot"),
        ],
    },
    "config": {
        "name": "Configuration", "emoji": "⚙️",
        "description": "Personnaliser GuideON sur ton serveur",
        "available": True,
        "commands": [
            ("autorole",      "🎭 Configure l'attribution automatique de rôles"),
            ("bienvenue",     "👋 Configure le système de bienvenue"),
            ("role_all",      "👥 Attribue ou retire un rôle à tous les membres du serveur"),
            ("role_reaction", "🎭 Configure le système de rôles réaction"),
        ],
    },
    "exp": {
        "name": "EXP", "emoji": "🧩",
        "description": "Système d'expérience (bientôt)",
        "available": False,
        "commands": [
            ("config",      "🧮 Configure le système d'EXP"),
            ("gestion",     "🛠️ Ajuste manuellement l'EXP d'un membre"),
            ("leaderboard", "🏆 Affiche le classement EXP du serveur"),
            ("level",       "📊 Affiche le niveau et l'EXP d'un membre"),
        ],
    },
    "giveaway": {
        "name": "Giveaways", "emoji": "🎁",
        "description": "Système de giveaways",
        "available": True,
        "commands": [
            ("blacklist", "🚫 Gère la blacklist du système de giveaway"),
            ("create",    "🎉 Crée un nouveau giveaway"),
            ("list",      "📋 Liste les giveaways du serveur (✨ Gold+)"),
            ("manage",    "🛠️ Gère un giveaway existant"),
        ],
    },
    "invite": {
        "name": "Invitations", "emoji": "✉️",
        "description": "Tracking et récompenses d'invitations",
        "available": True,
        "commands": [
            ("classement", "🏆 Affiche le classement des invitations du serveur"),
            ("config",     "📨 Configure le système d'invitations"),
            ("gestion",    "🛠️ Ajuste manuellement les compteurs d'invitations d'un membre"),
            ("user",       "📨 Affiche les invitations d'un membre"),
        ],
    },
    "moderation": {
        "name": "Modération", "emoji": "🛡️",
        "description": "Outils de modération (bientôt)",
        "available": False,
        "commands": [
            ("ban",         "🔨 Bannit un membre du serveur"),
            ("clear",       "🧹 Supprime des messages en masse dans un salon"),
            ("config",      "🛡️ Configure l'automod du serveur"),
            ("historique",  "📁 Affiche l'historique de sanction d'un membre"),
            ("kick",        "🍃 Expulse un membre du serveur"),
            ("lock",        "🔒 Verrouille un salon textuel"),
            ("logs",        "📋 Configure le système de logs du serveur"),
            ("mute",        "🔇 Rend un membre muet temporairement"),
            ("permissions", "🔐 Gère les permissions de modération"),
            ("rename",      "🖊️ Modifie le pseudo d'un membre"),
            ("softban",     "🧹 Bannit un membre et supprime ses derniers messages"),
            ("tempban",     "⏳ Bannit un membre pour une durée déterminée"),
            ("unban",       "🔓 Révoque un bannissement"),
            ("unlock",      "🔓 Déverrouille un salon textuel"),
            ("unmute",      "🔊 Enlève le mute d'un membre"),
            ("unwarn",      "🚫 Révoque un avertissement"),
            ("vocal",       "🔊 Gestion vocale de masse"),
            ("warn",        "⚠️ Avertit un membre"),
        ],
    },
    "ng": {
        "name": "NationsGlory", "emoji": "🌍",
        "description": "Commandes autour de NationsGlory",
        "available": True,
        "commands": [
            ("autel",    "⛪ Affiche les informations sur les autels NationsGlory"),
            ("convert",  "🧮 Convertis un nombre d'items en stacks, coffres ou double-coffres"),
            ("dynmaps",  "🗺️ Lien des dynmaps NationsGlory"),
            ("info",     "📌 Informations NationsGlory"),
            ("version",  "🔃 Afficher la version actuelle de NationsGlory Bedrock"),
            ("onu",      "☕ Informations sur les ONUs NationsGlory"),
            ("rd",       "📘 Affiche les infos d'un palier de R&D"),
            ("sanction", "📋 Affiche le tableau des sanctions d'un serveur NationsGlory"),
            ("skin",     "🧥 Récupère le skin d'un joueur NationsGlory"),
        ],
    },
    "qr": {
        "name": "QRCode", "emoji": "🖼️",
        "description": "Commandes de QR code",
        "available": True,
        "commands": [
            ("generate", "🖼️ Génère un QR code personnalisé"),
            ("list",     "📋 Liste tes QR codes enregistrés"),
            ("scan",     "🔍 Scanne un QR code depuis une image"),
        ],
    },
    "ticket": {
        "name": "Tickets", "emoji": "🎫",
        "description": "Système de support par tickets",
        "available": True,
        "commands": [
            ("add",          "👤 Ajouter un utilisateur à ce ticket"),
            ("ban",          "🔨 Bannir un utilisateur des tickets"),
            ("close",        "🔒 Fermer ce ticket"),
            ("delete",       "🗑️ Supprimer définitivement ce ticket"),
            ("panel_create", "🎫 Créer un nouveau panel de tickets"),
            ("panel_delete", "🗑️ Supprimer un panel de tickets"),
            ("panel_edit",   "✏️ Modifier un panel de tickets existant"),
            ("panel_list",   "📋 Lister les panels de tickets du serveur"),
            ("remove",       "👤 Retirer un utilisateur de ce ticket"),
            ("rename",       "✏️ Renommer ce ticket"),
            ("unban",        "♻️ Révoquer le ban tickets d'un utilisateur"),
            ("wakeup",       "🔔 Relancer le créateur du ticket"),
        ],
    },
}


COMMANDS_PER_PAGE = 8

# Contacts partenariat.
PARTNERSHIP_EMAIL = "gestion.guideon@gmail.com"
PARTNERSHIP_DISCORD = "https://discord.gg/ZKX3YQdDFT"


# ═══════════════════════════════════════════════════════════════
# 🔧  Helpers internes
# ═══════════════════════════════════════════════════════════════

def _uptime() -> str:
    return format_duration(timedelta(seconds=uptime_seconds()))


def _make_category_select(owner_id: int, callback) -> Select:
    """Construit le Select de choix de catégorie avec callback assigné."""
    options = [
        SelectOption(
            label=f"{cat['name']}{'  ⏳' if not cat['available'] else ''}",
            value=cat_id,
            emoji=cat["emoji"],
            description=cat["description"][:50],
        )
        for cat_id, cat in CATEGORIES.items()
    ]
    select = Select(
        placeholder="📚 Choisir une catégorie...",
        options=options,
        custom_id=f"wiki_cat:{owner_id}",
        min_values=1, max_values=1,
    )
    select.callback = callback
    return select


def _nav_buttons(owner_id: int, active: str, bot: discord.Client | None = None) -> list[Button]:
    """3 boutons de navigation avec callbacks assignés. `active` désactive le sien."""
    defs = [
        ("home",    "🏠", "Accueil", ButtonStyle.primary),
        ("support", "💬", "Support", ButtonStyle.secondary),
        ("links",   "🔗", "Liens",   ButtonStyle.secondary),
    ]
    buttons = []
    for key, emoji, label, style in defs:
        btn = Button(
            label=label, emoji=emoji, style=style,
            custom_id=f"wiki_{key}:{owner_id}",
            disabled=(key == active),
        )
        if key == "home":
            _b, _oid = bot, owner_id
            async def _cb_home(interaction: discord.Interaction, b=_b, oid=_oid):
                await interaction.response.edit_message(view=WikiHomeView(b, oid))
            btn.callback = _cb_home
        elif key == "support":
            _oid, _b = owner_id, bot
            async def _cb_support(interaction: discord.Interaction, oid=_oid, b=_b):
                await interaction.response.edit_message(view=WikiSupportView(oid, b))
            btn.callback = _cb_support
        elif key == "links":
            _oid, _b = owner_id, bot
            async def _cb_links(interaction: discord.Interaction, oid=_oid, b=_b):
                await interaction.response.edit_message(view=WikiLinksView(oid, b))
            btn.callback = _cb_links
        buttons.append(btn)
    return buttons


# ═══════════════════════════════════════════════════════════════
# 🏠  Accueil
# ═══════════════════════════════════════════════════════════════

class WikiHomeView(BaseLayoutView):
    def __init__(self, bot: discord.Client, owner_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=300)
        self.bot = bot
        self._build()

    def _build(self) -> None:
        bot = self.bot
        total_cmds = sum(len(c["commands"]) for c in CATEGORIES.values())

        c = Container()
        c.add_item(TextDisplay("# 📖 Wiki GuideON"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "Bienvenue dans le **wiki** de GuideON !\n"
            "Retrouve ici toutes nos commandes triées par catégorie."
        ))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"**Utilisateurs :** `{sum(g.member_count or 0 for g in bot.guilds)}`\n"
            f"**Commandes :** `{total_cmds}`\n"
            f"**Uptime :** `{_uptime()}`"
        ))
        c.add_item(Separator())

        # 🤝 Partenariat
        partner_btn = Button(
            label="Nous contacter", emoji="📧",
            style=ButtonStyle.link,
            url=f"mailto:{PARTNERSHIP_EMAIL}",
        )
        c.add_item(Section(
            TextDisplay(
                "**🤝 Partenariat**\n"
                "-# Communauté, projet, événement à mettre en avant ? "
                "GuideON est ouvert aux partenariats — présentations mutuelles, "
                "intégrations, événements communs. On en discute :"
            ),
            accessory=partner_btn,
        ))
        c.add_item(Separator())

        c.add_item(TextDisplay("Sélectionne une catégorie pour explorer les commandes :"))

        _bot, _oid = self.bot, self.owner_id
        async def on_cat(interaction: discord.Interaction) -> None:
            cat_id = interaction.data["values"][0]
            await interaction.response.edit_message(
                view=WikiCategoryView(cat_id, 0, _oid, _bot)
            )

        c.add_item(ActionRow(_make_category_select(self.owner_id, on_cat)))
        c.add_item(Separator())
        c.add_item(ActionRow(*_nav_buttons(self.owner_id, active="home", bot=bot)))
        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)


# ═══════════════════════════════════════════════════════════════
# 📂  Catégorie (paginée)
# ═══════════════════════════════════════════════════════════════

class WikiCategoryView(BaseLayoutView):
    def __init__(self, cat_id: str, page: int, owner_id: int, bot: discord.Client) -> None:
        super().__init__(owner_id=owner_id, timeout=300)
        self.cat_id = cat_id
        self.page = page
        self.bot = bot
        self._build()

    def _build(self) -> None:
        cat = CATEGORIES[self.cat_id]
        cmds = cat["commands"]
        total_pages = max(1, (len(cmds) + COMMANDS_PER_PAGE - 1) // COMMANDS_PER_PAGE)
        page = max(0, min(self.page, total_pages - 1))
        page_cmds = cmds[page * COMMANDS_PER_PAGE:(page + 1) * COMMANDS_PER_PAGE]

        c = Container()
        avail_tag = "" if cat["available"] else " *(Bientôt disponible)*"
        c.add_item(TextDisplay(f"# {cat['emoji']} {cat['name']}{avail_tag}"))
        c.add_item(Separator())
        c.add_item(TextDisplay(f"`{len(cmds)}` commande(s) · page `{page + 1}/{total_pages}`"))
        c.add_item(Separator())

        if not cat["available"]:
            c.add_item(TextDisplay(
                "⏳ Ces commandes sont en cours de développement.\n"
                "Elles seront disponibles dans une prochaine mise à jour !"
            ))
            c.add_item(Separator())
        else:
            for name, description in page_cmds:
                c.add_item(TextDisplay(f"`/{name}` — {description}"))
            c.add_item(Separator())

        # Pagination
        if total_pages > 1:
            _cat_id, _page, _oid, _bot = self.cat_id, page, self.owner_id, self.bot

            prev_btn = Button(
                emoji="⬅️", style=ButtonStyle.secondary,
                custom_id=f"wiki_prev:{_cat_id}:{page}:{_oid}",
                disabled=(page == 0),
            )
            indicator = Button(
                label=f"{page + 1} / {total_pages}",
                style=ButtonStyle.secondary,
                custom_id="wiki_indicator",
                disabled=True,
            )
            next_btn = Button(
                emoji="➡️", style=ButtonStyle.secondary,
                custom_id=f"wiki_next:{_cat_id}:{page}:{_oid}",
                disabled=(page == total_pages - 1),
            )

            async def _on_prev(interaction: discord.Interaction, cid=_cat_id, p=_page, oid=_oid, b=_bot):
                await interaction.response.edit_message(view=WikiCategoryView(cid, p - 1, oid, b))

            async def _on_next(interaction: discord.Interaction, cid=_cat_id, p=_page, oid=_oid, b=_bot):
                await interaction.response.edit_message(view=WikiCategoryView(cid, p + 1, oid, b))

            prev_btn.callback = _on_prev
            next_btn.callback = _on_next
            c.add_item(ActionRow(prev_btn, indicator, next_btn))
            c.add_item(Separator())

        # Select catégorie
        _oid, _bot = self.owner_id, self.bot

        async def on_cat(interaction: discord.Interaction, oid=_oid, b=_bot) -> None:
            cat_id = interaction.data["values"][0]
            await interaction.response.edit_message(view=WikiCategoryView(cat_id, 0, oid, b))

        c.add_item(ActionRow(_make_category_select(self.owner_id, on_cat)))
        c.add_item(Separator())
        c.add_item(ActionRow(*_nav_buttons(self.owner_id, active="", bot=self.bot)))
        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)


# ═══════════════════════════════════════════════════════════════
# 💬  Support
# ═══════════════════════════════════════════════════════════════

class WikiSupportView(BaseLayoutView):
    def __init__(self, owner_id: int, bot: discord.Client) -> None:
        super().__init__(owner_id=owner_id, timeout=300)
        self.bot = bot
        self._build()

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay("# 💬 Support GuideON"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "Notre équipe est disponible pour t'aider !\n\n"
            f"**📬 Discord :** {PARTNERSHIP_DISCORD}\n"
            "**🌐 Site web :** https://guideonbot.guideon.dev/\n"
            f"**📧 Email :** {PARTNERSHIP_EMAIL}"
        ))
        c.add_item(Separator())
        c.add_item(ActionRow(
            Button(label="Rejoindre le Discord", emoji="💬",
                   style=ButtonStyle.link, url=PARTNERSHIP_DISCORD),
            Button(label="Site web", emoji="🌐",
                   style=ButtonStyle.link, url="https://guideonbot.guideon.dev/"),
        ))
        c.add_item(Separator())
        c.add_item(ActionRow(*_nav_buttons(self.owner_id, active="support", bot=self.bot)))
        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)


# ═══════════════════════════════════════════════════════════════
# 🔗  Liens
# ═══════════════════════════════════════════════════════════════

class WikiLinksView(BaseLayoutView):
    def __init__(self, owner_id: int, bot: discord.Client) -> None:
        super().__init__(owner_id=owner_id, timeout=300)
        self.bot = bot
        self._build()

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay("# 🔗 Liens GuideON"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "Retrouvez GuideON partout :\n\n"
            "**🌐 Site web :** https://guideonbot.fr/\n"
            f"**💬 Discord :** {PARTNERSHIP_DISCORD}\n"
            "**📊 Top.gg :** https://top.gg/bot/1184180079069249666"
        ))
        c.add_item(Separator())
        c.add_item(ActionRow(
            Button(label="Site web", emoji="🌐",
                   style=ButtonStyle.link, url="https://guideonbot.fr/"),
            Button(label="Discord",  emoji="💬",
                   style=ButtonStyle.link, url=PARTNERSHIP_DISCORD),
            Button(label="Top.gg",   emoji="📊",
                   style=ButtonStyle.link, url="https://top.gg/bot/1184180079069249666"),
        ))
        c.add_item(Separator())
        c.add_item(ActionRow(*_nav_buttons(self.owner_id, active="links", bot=self.bot)))
        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)