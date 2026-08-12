"""
cogs/delta/ — Squelette pré-préparé pour le serveur NG "Delta" (refonte
multi-serveurs, phase 14, §8 du prompt).

Ce package est intentionnellement vide : Delta n'est pas encore un serveur
NG actif (voir ng_servers.active=false une fois sa ligne créée -- cf
PHASE_14.md pour pourquoi cette ligne n'est PAS encore seedée par une
migration Alembic).

Ajouter ici les commandes /delta en dupliquant cogs/alpha/ -- mais
attention, la majorité du système staff fonctionne déjà pour Delta SANS
rien dupliquer ici, grâce aux phases 11-12 :

    - /ngstaff config, rank, derank, stafflist, edit_stafflist, nota_debug
      résolvent déjà dynamiquement le serveur via require_ng_server (voir
      utils/ng_server_check.py) -- dès que la ligne ng_servers 'delta' est
      active, ces commandes fonctionnent sur le Discord Delta sans AUCUN
      fichier à ajouter ici.

Seuls les "systèmes particuliers" restent Alpha-only par design (phase 13,
voir PHASE_13.md) et n'ont donc pas d'équivalent générique -- ce sont eux
qu'il faut dupliquer ici si Delta a besoin des mêmes fonctionnalités
(contenu Discord permanent, events) :

    1. Dupliquer cogs/alpha/config_alpha.py, index.py, regle_interne.py,
       nous_rejoindre.py, event_start.py, event_regle.py, event_list.py
       -> cogs/delta/*.py.
    2. Adapter les noms de commande (name="...") et les descriptions pour
       remplacer "Alpha" par "Delta" partout où c'est affiché à
       l'utilisateur.
    3. Remplacer utils.perm_alpha (check_op_alpha, check_modo_plus,
       require_alpha_guild) par un équivalent RBAC générique -- NE PAS
       copier perm_alpha.py tel quel, il est câblé en dur sur "alpha" par
       design. S'inspirer de utils.perm_check.has_grade_check (RBAC
       générique, déjà utilisé par /ngstaff) plutôt que de perm_alpha.
    4. Enregistrer les nouvelles commandes dans bot.py, dans un nouveau
       groupe self._groupDELTA (groupeDELTA(), à ajouter à
       utils/groupes.py), synchronisé uniquement sur le Discord Delta.
    5. content_*_channel_id / content_*_emoji (index, règle interne, nous
       rejoindre, stafflist) vivent déjà dans ng_rank_configs, keyées par
       server -- /ngstaff config (généré phase 11) permet déjà de les
       configurer pour 'delta' sans code supplémentaire ; seule
       l'INTERFACE d'affichage (les commandes elles-mêmes) doit être
       dupliquée, pas le stockage.

Rappel §8 du prompt -- activation future en 3 étapes une fois ce squelette
rempli (ou même sans rien dupliquer, si Delta n'a besoin que du système
staff rank/derank/stafflist déjà générique) :
    1. Dupliquer cogs/alpha/ -> cogs/delta/ et adapter les IDs Discord
       (uniquement pour les systèmes particuliers, voir ci-dessus).
    2. Passer ng_servers.active=true où name='delta' (via le site --
       source de vérité sur cette table, cf §4.1 du prompt).
    3. Configurer via /ngstaff config sur le Discord Delta.
"""
