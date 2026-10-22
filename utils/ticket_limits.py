"""
utils/ticket_limits.py — Valeurs limites du système de tickets.
"""

from __future__ import annotations

# ============================================================
# ⏳ Cooldowns (secondes)
# ============================================================

# Anti-spam à l'ouverture d'un ticket (par utilisateur, par panel).
TICKET_COOLDOWN_SECONDS = 30

# Cooldown de renommage d'un salon ticket.
RENAME_COOLDOWN_SECONDS = 600

# Cooldown de la relance ("Wake-up").
WAKEUP_COOLDOWN_SECONDS = 3600

# Délai avant suppression définitive du salon.
DELETE_DELAY_SECONDS = 8


# ============================================================
# 🎫 Tickets simultanés (par utilisateur, par panel)
# ============================================================

MAX_TICKETS_USER_DEFAULT = 1
MAX_TICKETS_USER_VIP = 2


# ============================================================
# 📬 Tickets ouverts (par panel)
# ============================================================

MAX_TICKETS_PANEL_DEFAULT = 50
MAX_TICKETS_PANEL_GOLD = 200


# ============================================================
# 👥 Rôles staff par panel
# ============================================================

# Nombre maximum de rôles staff par panel.
MAX_STAFF_ROLES_PER_PANEL = 3


# ============================================================
# 📁 Catégories Discord
# ============================================================

# Limite de salon par catégorie (Discord).
MAX_CHANNELS_PER_CATEGORY = 50


# ============================================================
# 📝 Longueurs de champs (modals / selects)
# ============================================================

PANEL_TITLE_MAX_LENGTH = 80
# Plafond Discord réel d'un TextInput de modal : 4000 caractères (identique
# pour le style "paragraph"). Mais le message du panel public partage son
# message avec le titre dans un même conteneur Components V2, et Discord
# limite le total du texte affiché (tous les TextDisplay confondus) à 4000
# caractères sur l'ensemble du message — pas 4000 par champ. 3500 laisse
# donc une marge confortable pour le titre (max 80) et le formatage (emoji,
# "# ") sans jamais risquer de dépasser ce plafond combiné.
PANEL_MESSAGE_MAX_LENGTH = 3500
TICKET_RAISON_MAX_LENGTH = 500

PANEL_EMOJI_MAX_LENGTH = 64
DEFAULT_PANEL_EMOJI = "🎫"

# URL de l'image de bannière du panel (Gold+ uniquement, cf. panel_setup_view).
PANEL_IMAGE_URL_MAX_LENGTH = 512


# ============================================================
# 🪟 Timeouts de vues (secondes)
# ============================================================

WIZARD_TIMEOUT = 600


# ============================================================
# 📋 Affichage
# ============================================================

# Nombre de panels affichés par /ticket panel_list (troncature).
MAX_PANELS_DISPLAY = 17

# Nombre de messages parcourus pour générer un transcript.
TRANSCRIPT_HISTORY_LIMIT = 1000

# Limite Discord : nombre maximum d'options dans un menu déroulant (select).
# Utilisé par le menu de configuration d'un panel (panel_setup_view) et par
# le sélecteur de panel réutilisable (panel_picker, pour /ticket panel_edit
# et /ticket panel_delete sans lien fourni).
MAX_SELECT_OPTIONS = 25