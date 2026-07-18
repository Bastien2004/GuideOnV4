"""
views/user/user_view.py — Vue de profil utilisateur ("carte d'identité"
Discord), extraite de la commande /id pour être partagée avec /user.

Reste en LayoutView simple, PAS BaseLayoutView : les deux boutons présents
("Télécharger la PP", "Ouvrir dans le navigateur") sont des boutons de type
ButtonStyle.link — ils n'ont AUCUN callback côté bot, Discord ouvre l'URL
directement côté client. Il n'y a donc rien à protéger (pas de owner_id à
imposer), rien à capturer comme erreur de composant, et le message n'a pas
de timeout à gérer puisqu'aucune interaction ne remonte jamais au bot.
BaseLayoutView n'apporterait rien ici, même si la présence de Button peut
laisser penser le contraire au premier coup d'œil.
"""
from __future__ import annotations

import re

import discord
from discord import MediaGalleryItem
from discord.ui import ActionRow, Button, Container, LayoutView, MediaGallery, Separator, TextDisplay

# ============================================================
# 🔎 Extraction ID Discord
# ============================================================

def extract_id(value: str) -> int | None:
    """Extrait un ID Discord depuis une mention ou un texte."""
    match = re.search(r"\d{15,20}", value)
    return int(match.group()) if match else None


# ============================================================
# 🖼️ Récupération URL avatar
# ============================================================

def get_avatar_url(user: discord.User) -> str:
    """Retourne l'URL de l'avatar utilisateur."""
    return user.display_avatar.replace(
        size=1024,
        format="gif" if user.display_avatar.is_animated() else "png"
    ).url


# ============================================================
# 📅 Formatage date création compte
# ============================================================

def get_creation_date(user: discord.User) -> str:
    """Retourne la date de création formatée."""
    return discord.utils.format_dt(user.created_at, style="F")


# ============================================================
# 📌 Section informations utilisateur
# ============================================================

def build_user_infos_section(container: Container, user: discord.User, created_at: str) -> None:
    """Création de la section informations utilisateur."""
    container.add_item(
        TextDisplay(
            "## <:info:1495443961144152094> Informations\n"
            f"**Pseudo :** `{user}`\n"
            f"**Nom affiché :** `{user.display_name}`\n"
            f"**ID :** `{user.id}`\n"
            f"**Bot :** `{'Oui' if user.bot else 'Non'}`\n"
            f"**Compte créé le :** {created_at}"
        )
    )

    container.add_item(Separator())


# ============================================================
# 🖼️ Section avatar
# ============================================================

def build_avatar_section(container: Container, avatar_url: str) -> None:
    """Création de la section avatar."""

    container.add_item(TextDisplay("## <:fichier:1495446721520730242> Avatar"))

    container.add_item(MediaGallery(MediaGalleryItem(media=avatar_url)))
    container.add_item(Separator())

    container.add_item(
        ActionRow(
            Button(
                label="Télécharger la PP",
                style=discord.ButtonStyle.link,
                url=avatar_url,
                emoji="📥"
            ),

            Button(
                label="Ouvrir dans le navigateur",
                style=discord.ButtonStyle.link,
                url=avatar_url,
                emoji="🌐"
            )
        )
    )
    container.add_item(Separator())


# ============================================================
# 🧩 Construction view CV2
# ============================================================

def build_user_view(user: discord.User) -> LayoutView:
    """Construction du container"""

    avatar_url = get_avatar_url(user)
    created_at = get_creation_date(user)

    view = LayoutView(timeout=None)
    container = Container()

    # Header
    container.add_item(TextDisplay("# <:profil:1495444182137831515> Profil utilisateur"))
    container.add_item(Separator())

    # Informations utilisateur
    build_user_infos_section(container, user, created_at)

    # Avatar
    build_avatar_section(container, avatar_url)

    # Footer
    container.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(container)

    return view