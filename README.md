# GuideON V4 — Démarrage rapide

## Répartition du travail

- **Ton collègue (DB/infra)** : `utils/db/`, `utils/managers/`, `migrations/`, `docker-compose.yml`, `.env` (DATABASE_URL)
- **Toi (Discord/UI)** : `bot.py`, `utils/` (hors db/managers), `views/`, `cogs/`

## Ce qui est déjà fait (35 fichiers, prêts à utiliser)

### Cœur du bot
- `bot.py` — point d'entrée, charge automatiquement les cogs
- `utils/settings.py` — config Pydantic (lit `.env`)
- `utils/logging_config.py` — logger unique
- `utils/error_handler.py` — handler global + error_id
- `utils/permission.py` — décorateurs `@is_guild_admin()`, `@is_dev()`, etc.
- `utils/datetime_utils.py` — `parse_duration("1d2h30m")`, timezones
- `utils/id_sanction.py` — IDs courts
- `utils/exp_lock.py` — verrous async par user
- `utils/uptime.py` — temps de démarrage
- `utils/safe_channel_edit.py` — edit channel avec gestion rate-limit
- `utils/theme.py` — couleurs/emojis centralisés

### Composants UI (à utiliser partout)
- `views/components/base_view.py` — BaseView (owner_check + error_id)
- `views/components/confirm_view.py` — ConfirmView (Oui/Non)
- `views/components/paginated_view.py` — Pagination générique
- `views/components/wizard_view.py` — Multi-étapes
- `views/components/channel_select.py` — ChannelSelect réutilisable
- `views/components/role_select.py` — RoleSelect réutilisable
- `views/components/text_modal.py` — TextModal réutilisable
- `views/components/back_button.py` — Bouton "Retour"

### Exemple complet (patron à copier pour les autres systèmes)
- `cogs/ticket/_state.py` — Dataclass d'état du wizard
- `cogs/ticket/ticket_panel_create.py` — Commande qui lance le wizard
- `views/ticket/embeds.py` — Builders d'embeds
- `views/ticket/panel_setup_view.py` — Wizard assemblage
- `views/ticket/category_select.py` · `transcript_select.py` · `staff_roles_select.py`
- `views/ticket/title_button.py` · `description_button.py`
- `views/ticket/publish_button.py` — Bouton final (appellera ticket_manager)

## Démarrer en local SANS DB

```bash
python -m venv .venv
source .venv/bin/activate          # Linux/Mac
# .venv\Scripts\activate            # Windows

pip install -e ".[dev]"
cp .env.example .env                # remplir DISCORD_TOKEN minimum
python bot.py
```

Le bot se connecte, charge tous les cogs présents (donc `ticket_panel_create`),
et te répondra sur `/ticket_panel_create` sur ton serveur Dev.

## Patron pour remplir une commande vide

1. **Crée un _state.py** dans le dossier du cog si wizard : `cogs/X/_state.py`
2. **Remplis le fichier cog** : classe `commands.Cog`, `@app_commands.command`, `async def setup(bot)`
3. **Crée les views modulaires** dans `views/X/` :
   - `panel_setup_view.py` qui hérite de `WizardView`
   - Un fichier par sélecteur / bouton
   - `embeds.py` pour les embeds
4. **Appelle le manager** dans le bouton final (cf. `views/ticket/publish_button.py`).
   Les appels manager sont en TODO commentés — décommente quand ton collègue a fini.

## Convention de découpe

- View < 300 lignes → 1 fichier `views/X/ma_view.py`
- View > 300 lignes → éclatée en sous-fichiers comme `views/ticket/`
- Composant réutilisable partout → `views/components/`

## Ce qui reste

63 fichiers `.py` vides à remplir. Ordre suggéré :

1. `cogs/_commande/` (ping, info, id, timestamp, report, wiki — simples)
2. `cogs/exp/exp_level.py` (lecture seule)
3. `cogs/giveaway/` (wizard, similaire à ticket)
4. `cogs/mod/` (le plus gros — en dernier)

## Avant de commit

```bash
ruff check .
ruff format .
python -c "import bot"     # vérifie que tout s'importe
```
