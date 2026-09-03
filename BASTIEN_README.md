# MEDIALINK — (Bastien)

Ta partie : **les 4 fichiers dans `utils/medialink/providers/`**. Le reste (base
de données, vues Discord, commande `/medialink config`) est déjà fait. Normalement tu n'as
pas besoin d'y toucher

## Contraintes

Un seul fichier à lire avant de commencer : **`utils/medialink/providers/base.py`**.
C'est la classe `BaseMediaProvider` — chaque plateforme (YouTube, Twitch, Reddit,
TikTok) doit l'implémenter avec exactement les mêmes méthodes :

- `connect(external_id, **credentials)` — initialise la connexion à UN compte.
- `disconnect()` — libère les ressources.
- `validate_account(external_id)` — vérifie qu'un compte existe (avant de le
  laisser être ajouté côté Discord).
- `get_account(external_id)` — récupère nom/avatar/URL affichables.
- `fetch_events()` — renvoie la liste des nouveaux événements détectés.
- `check_status()` — vérifie que la connexion fonctionne encore.

**Règle d'or, à ne jamais casser** : un Provider ne doit **jamais** envoyer de
message Discord lui-même. Il se contente de renvoyer des `MediaEvent`
(`utils/medialink/event.py`) — c'est le reste du pipeline (pas ton problème) qui
décide quoi en faire et où l'envoyer. Ça permet de tester chaque Provider tout
seul, sans bot Discord qui tourne.

## Statut des 4 fichiers

| Fichier | Statut |
|---|---|
| `youtube.py` | Prêt à coder — auth simple (clé API), tous les endpoints et pièges à quota sont commentés dans le fichier. |
| `twitch.py` | Prêt à coder — auth OAuth app token (plus de travail que YouTube), tout est détaillé dans le fichier, y compris le choix polling vs webhooks. |
| `reddit.py` | Prêt à coder, **mais un point à valider avec Paul d'abord** : on suit un subreddit ou un utilisateur ? C'est marqué en tête de fichier. |
| `tiktok.py` | **Bloqué.** TikTok n'a pas d'API publique pour lire les posts d'un compte tiers. Lis le fichier avant de commencer quoi que ce soit dessus — il explique pourquoi et liste les options (aucune n'est un simple "coder l'intégration"). |

Dans chaque fichier, cherche les commentaires `TODO Bastien` — ce sont les
endroits précis où remplacer `raise NotImplementedError(...)` par du vrai code.
Ne change pas les signatures des méthodes (noms, paramètres) : le reste du
pipeline les appelle telles quelles.

## Où mettre les clés API / secrets

Le bot centralise déjà toute la config sensible dans `utils/settings.py` (via
pydantic-settings + un fichier `.env`, jamais en dur dans le code). Il y a déjà
un exemple pour une autre API tierce : le champ `ng_api_key`. Suis exactement
ce modèle — chaque fichier provider te dit précisément quels champs ajouter
(ex: `youtube_api_key`, `twitch_client_id`, `twitch_client_secret`...).


## Anti-doublon — un point qui revient dans les 3 fichiers

Le système anti-doublon (pour ne jamais poster deux fois la même annonce) est
géré ailleurs (`utils/medialink/event_manager.py`, pas ton fichier) — mais il
dépend entièrement de la valeur que tu mets dans `MediaEvent.external_id`.
Chaque fichier `.py` t'indique précisément quel champ de l'API utiliser (ex:
l'ID de vidéo YouTube, l'ID de session de live Twitch — **pas** l'ID de chaîne,
qui ne change jamais). Si tu as un doute sur quel champ utiliser pour un cas
particulier, demande avant de deviner : une mauvaise clé ici veut dire soit des
doublons, soit des événements ratés silencieusement.

## En cas de doute

Le fichier `utils/medialink/providers/base.py` est la seule source de vérité
sur ce qu'on attend de toi côté signatures. Pour tout le reste (quel champ
event_type utiliser, comment un event remonte jusqu'à Discord, etc.), demande à
Paul plutôt que de deviner — plusieurs points sont volontairement laissés
ouverts dans les commentaires (pas des oublis, des décisions pas encore prises).