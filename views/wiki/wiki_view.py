"""
views/wiki/wiki_view.py — Interface interactive du wiki de GuideOn.
"""

from __future__ import annotations

from datetime import timedelta

import discord
from discord import ButtonStyle, SelectOption
from discord.ui import ActionRow, Button, Container, Section, Select, Separator, TextDisplay

from utils.datetime_utils import format_duration
from utils.uptime import uptime_seconds
from views._components.base_view import BaseLayoutView


# ============================================================
# 📋 Liste des commandes
# ============================================================

CATEGORIES: dict[str, dict] = {
    "birthday": {
        "name": "Système anniversaire", "emoji": "🎂",
        "description": "⇝ N'oubli plus aucun anniversaire !",
        "available": True,
        "commands": [
            ("birthday add",    "🎂 Enregistre ta date d'anniversaire"),
            ("birthday config", "🎂 Configure le système d'anniversaires"),
            ("birthday list",   "🎂 [VIP] Affiche les anniversaires des 30 prochains jours"),
            ("birthday next",   "🎂 [VIP] Affiche le prochain anniversaire à venir"),
        ],
    },
    "utility": {
        "name": "Commandes utilitaires", "emoji": "🔧",
        "description": "⇝ Outils pratiques du quotidien.",
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
        "name": "Commandes de configuration", "emoji": "⚙️",
        "description": "⇝ Automatise ton serveur avec GuideOn !",
        "available": True,
        "commands": [
            ("config autorole",      "🎭 Configure l'attribution automatique de rôles"),
            ("config bienvenue",     "👋 Configure le système de bienvenue"),
            ("config role_all",      "👥 Attribue ou retire un rôle à tous les membres du serveur"),
            ("config role_reaction", "🎭 Configure le système de rôles réaction"),
        ],
    },
    "exp": {
        "name": "Système exp", "emoji": "🧩",
        "description": "⇝ Valorise les plus actifs du serveur !",
        "available": True,
        "commands": [
            ("exp config",      "🧮 Configure le système d'EXP"),
            ("exp gestion",     "🛠️ Ajuste manuellement l'EXP d'un membre"),
            ("exp leaderboard", "🏆 Affiche le classement EXP du serveur"),
            ("exp level",       "📊 Affiche le niveau et l'EXP d'un membre"),
        ],
    },
    "giveaway": {
        "name": "Système giveaways", "emoji": "🎁",
        "description": "⇝ Fais gagner des cadeaux à tes membres !",
        "available": True,
        "commands": [
            ("giveaway blacklist", "🚫 Gère la blacklist du système de giveaway"),
            ("giveaway create",    "🎉 Crée un nouveau giveaway"),
            ("giveaway list",      "📋 Liste les giveaways du serveur (✨ Gold+)"),
            ("giveaway manage",    "🛠️ Gère un giveaway existant"),
        ],
    },
    "invite": {
        "name": "Système invitations", "emoji": "✉️",
        "description": "⇝ Tracking et récompenses d'invitations",
        "available": True,
        "commands": [
            ("invite classement", "🏆 Affiche le classement des invitations du serveur"),
            ("invite config",     "📨 Configure le système d'invitations"),
            ("invite gestion",    "🛠️ Ajuste manuellement les compteurs d'invitations d'un membre"),
            ("invite user",       "📨 Affiche les invitations d'un membre"),
        ],
    },
    "moderation": {
        "name": "Système modération", "emoji": "🛡️",
        "description": "⇝ Outils de modération & automod.",
        "available": True,
        "commands": [
            ("mod ban",         "🔨 Bannit un membre du serveur"),
            ("mod clear",       "🧹 Supprime des messages en masse dans un salon"),
            ("mod config",      "🛡️ Configure l'automod du serveur"),
            ("mod historique",  "📁 Affiche l'historique de sanction d'un membre"),
            ("mod kick",        "🍃 Expulse un membre du serveur"),
            ("mod lock",        "🔒 Verrouille un salon textuel"),
            ("mod logs",        "📋 Configure le système de logs du serveur"),
            ("mod mute",        "🔇 Rend un membre muet temporairement"),
            ("mod permissions", "🔐 Gère les permissions de modération"),
            ("mod rename",      "🖊️ Modifie le pseudo d'un membre"),
            ("mod softban",     "🧹 Bannit un membre et supprime ses derniers messages"),
            ("mod tempban",     "⏳ Bannit un membre pour une durée déterminée"),
            ("mod unban",       "🔓 Révoque un bannissement"),
            ("mod unlock",      "🔓 Déverrouille un salon textuel"),
            ("mod unmute",      "🔊 Enlève le mute d'un membre"),
            ("mod unwarn",      "🚫 Révoque un avertissement"),
            ("mod vocal",       "🔊 Gestion vocale de masse"),
            ("mod warn",        "⚠️ Avertit un membre"),
        ],
    },
    "ng": {
        "name": "NationsGlory", "emoji": "🌍",
        "description": "⇝ Commandes autour de NationsGlory",
        "available": True,
        "commands": [
            ("ng autel",    "⛪ Affiche les informations sur les autels NationsGlory"),
            ("ng convert",  "🧮 Convertis un nombre d'items en stacks, coffres ou double-coffres"),
            ("ng dynmaps",  "🗺️ Lien des dynmaps NationsGlory"),
            ("ng info",     "📌 Informations NationsGlory"),
            ("ng version",  "🔃 Afficher la version actuelle de NationsGlory Bedrock"),
            ("ng onu",      "☕ Informations sur les ONUs NationsGlory"),
            ("ng rd",       "📘 Affiche les infos d'un palier de R&D"),
            ("ng sanction", "📋 Affiche le tableau des sanctions d'un serveur NationsGlory"),
            ("ng skin",     "🧥 Récupère le skin d'un joueur NationsGlory"),
        ],
    },
    "qr": {
        "name": "QRCode", "emoji": "🖼️",
        "description": "⇝ Partage tes liens facilement via QRCode !",
        "available": True,
        "commands": [
            ("qr generate", "🖼️ Génère un QR code personnalisé"),
            ("qr list",     "📋 Liste tes QR codes enregistrés"),
            ("qr scan",     "🔍 Scanne un QR code depuis une image"),
        ],
    },
    "ticket": {
        "name": "Tickets", "emoji": "🎫",
        "description": "⇝ Construit ton meilleur support !",
        "available": True,
        "commands": [
            ("ticket add",          "👤 Ajouter un utilisateur à ce ticket"),
            ("ticket ban",          "🔨 Bannir un utilisateur des tickets"),
            ("ticket close",        "🔒 Fermer ce ticket"),
            ("ticket delete",       "🗑️ Supprimer définitivement ce ticket"),
            ("ticket panel_create", "🎫 Créer un nouveau panel de tickets"),
            ("ticket panel_delete", "🗑️ Supprimer un panel de tickets"),
            ("ticket panel_edit",   "✏️ Modifier un panel de tickets existant"),
            ("ticket panel_list",   "📋 Lister les panels de tickets du serveur"),
            ("ticket remove",       "👤 Retirer un utilisateur de ce ticket"),
            ("ticket rename",       "✏️ Renommer ce ticket"),
            ("ticket unban",        "♻️ Révoquer le ban tickets d'un utilisateur"),
            ("ticket wakeup",       "🔔 Relancer le créateur du ticket"),
        ],
    },
}


# ============================================================
# 🔩 Paramètres
# ============================================================

COMMANDS_PER_PAGE = 8
EMAIL_GUIDEON = "gestion.guideon@gmail.com"
DISCORD_GUIDEON = "https://discord.gg/ZKX3YQdDFT"


# ============================================================
# 🔧 Fonctions utilitaires
# ============================================================

def _uptime() -> str:
    """Récupère l'uptime du bot."""
    return format_duration(timedelta(seconds=uptime_seconds()))


def _make_category_select(owner_id: int, callback) -> Select:
    """Construit le menu de sélection."""

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
    """Gestion des boutons de navigation."""

    defs = [
        ("home",    "🏠", "Accueil",      ButtonStyle.primary),
        ("support", "💬", "Support",      ButtonStyle.secondary),
        ("partner", "🤝", "Partenaires",  ButtonStyle.secondary),
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

        elif key == "partner":
            _oid, _b = owner_id, bot
            async def _cb_partner(interaction: discord.Interaction, oid=_oid, b=_b):
                await interaction.response.edit_message(view=WikipartnerView(oid, b))
            btn.callback = _cb_partner
        buttons.append(btn)
    return buttons


# ============================================================
# 🏠 Accueil
# ============================================================

class WikiHomeView(BaseLayoutView):
    def __init__(self, bot: discord.Client, owner_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=300)
        self.bot = bot
        self._build()

    def _build(self) -> None:
        bot = self.bot
        total_cmds = sum(len(c["commands"]) for c in CATEGORIES.values())

        c = Container()
        c.add_item(TextDisplay("# 📖 Wiki GuideOn"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "Bienvenue dans le **wiki** du bot GuideOn !\n"
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
            url=DISCORD_GUIDEON,
        )
        c.add_item(Section(
            TextDisplay(
                "**🤝 Partenariat**\n"
                "GuideOn est ouvert aux partenariats !"
            ),
            accessory=partner_btn,
        ))
        c.add_item(Separator())

        c.add_item(TextDisplay("➥ **Découvrez nos commandes** :"))

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


# ============================================================
# 💻 Catégories de commande
# ============================================================

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
                "⏳ Commandes en cours de développement ...\n"
                "Disponibles prochainement !"
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
                emoji="<:precedent:1515658763913138236>", style=ButtonStyle.secondary,
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
                emoji="<:suivant:1515658825913339904>", style=ButtonStyle.secondary,
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


# ============================================================
# 💬  Support
# ============================================================

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
            "➤ Notre équipe est **disponible** pour t'aider !\n\n"

            f"**📬 Discord :** {DISCORD_GUIDEON}\n"
            "**🌐 Site web :** https://guideonbot.guideon.dev/\n"
            "**💻 TOP GG :** https://top.gg/bot/1184180079069249666\n"
            f"**📧 Email :** `{EMAIL_GUIDEON}`\n"
        ))
        c.add_item(Separator())

        c.add_item(ActionRow(*_nav_buttons(self.owner_id, active="support", bot=self.bot)))
        c.add_item(Separator())
        
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)


# ============================================================
# 🤝 Partenaires
# ============================================================

class WikipartnerView(BaseLayoutView):
    def __init__(self, owner_id: int, bot: discord.Client) -> None:
        super().__init__(owner_id=owner_id, timeout=300)
        self.bot = bot
        self._build()

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay("# 🤝 Partenaire GuideOn"))
        c.add_item(Separator())

        c.add_item(TextDisplay(
            "➤ Retrouvez la liste des **partenaires GuideOn** :\n\n"

            "- **[NationsGlory Alpha](https://discord.gg/hHvv5paB6j)**\n"
            "-# Serveur Minecraft semi-rp.\n"
            "- **[SwiftSky](https://discord.gg/zezkpMrD5e)**\n"
            "-# Service de graphisme professionnel.\n"
            "- **[GloryForProgress](https://discord.gg/SvwVJpTBCZ)**\n"
            "-# Bot référent d'aide NationsGlory.\n"
            "- **[Le Souk's](https://discord.gg/CAWsejVb7C)**\n"
            "-# Serveur d'échange et de vente.\n"
        ))
        c.add_item(Separator())

        c.add_item(ActionRow(*_nav_buttons(self.owner_id, active="partner", bot=self.bot)))
        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)