"""
utils/ticket_limits.py — Valeurs limites centralisées du système de tickets.

Audit 2026-10-16 : avant ce fichier, les constantes du système de tickets
étaient dispersées entre views/ticket/_helpers.py, views/ticket/transcript.py,
views/ticket/panel_setup_view.py et cogs/ticket/ticket_panel_list.py — ce qui
rendait difficile d'avoir une vue d'ensemble pour les rééquilibrer. Tout est
maintenant ici, avec une seule source de vérité par valeur.

Ce fichier ne contient QUE des constantes (pas de logique) : il peut être
importé aussi bien depuis utils/, views/ que cogs/ sans créer de dépendance
circulaire.
"""
from __future__ import annotations

# ============================================================
# ⏳ Cooldowns (secondes)
# ============================================================

# Anti-spam à l'ouverture d'un ticket (par utilisateur, par panel).
TICKET_COOLDOWN_SECONDS = 30

# Cooldown de renommage d'un salon ticket (rate-limit Discord : 2
# renommages / 10 min par salon — on se cale large pour éviter le 429).
RENAME_COOLDOWN_SECONDS = 600

# Cooldown de la relance ("Wake-up") envoyée par le staff à l'utilisateur.
WAKEUP_COOLDOWN_SECONDS = 3600

# Délai avant suppression définitive du salon après l'envoi du transcript
# (laisse le temps au message de confirmation d'être lu).
DELETE_DELAY_SECONDS = 8


# ============================================================
# 🎫 Tickets simultanés (par utilisateur, par panel)
# ============================================================

MAX_TICKETS_USER_DEFAULT = 1
MAX_TICKETS_USER_VIP = 2


# ============================================================
# 📬 Tickets ouverts (par panel, toutes les files confondues)
# ============================================================

MAX_TICKETS_PANEL_DEFAULT = 1000
MAX_TICKETS_PANEL_GOLD = 100


# ============================================================
# 👥 Rôles staff par panel
# ============================================================

# Nombre maximum de rôles staff sélectionnables sur un panel (select natif
# multi-valeurs). Valeur reprise telle quelle de la V3 (3 champs texte) —
# simplement centralisée ici pour pouvoir l'ajuster facilement plus tard.
MAX_STAFF_ROLES_PER_PANEL = 3


# ============================================================
# 📁 Catégories Discord
# ============================================================

# Limite plateforme Discord (fixe, non négociable) : 50 salons max par
# catégorie, tous types confondus. Utilisé pour détecter qu'une catégorie
# de tickets est pleine et basculer sur la catégorie de secours.
MAX_CHANNELS_PER_CATEGORY = 50


# ============================================================
# 📝 Longueurs de champs (modals / selects)
# ============================================================

PANEL_TITLE_MAX_LENGTH = 80
PANEL_MESSAGE_MAX_LENGTH = 500
TICKET_RAISON_MAX_LENGTH = 500

# Longueur max d'un emoji de panel saisi en texte (large marge : un emoji
# personnalisé complet "<a:nom_long:1234567890123456789>" tient dedans).
PANEL_EMOJI_MAX_LENGTH = 64

# Emoji par défaut quand un panel n'a pas (encore) d'emoji configuré —
# comportement identique à avant l'ajout de cette configuration.
DEFAULT_PANEL_EMOJI = "🎫"


# ============================================================
# 🪟 Timeouts de vues (secondes)
# ============================================================

WIZARD_TIMEOUT = 600


# ============================================================
# 📋 Affichage
# ============================================================

# Nombre de panels affichés par /ticket panel_list avant troncature.
MAX_PANELS_DISPLAY = 17

# Nombre de messages parcourus pour générer un transcript.
TRANSCRIPT_HISTORY_LIMIT = 1000
