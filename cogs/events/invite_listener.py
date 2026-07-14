"""
cogs/events/invite_listener.py — Tracking des invitations Discord.

commands.Cog avec setup() → chargé automatiquement par _load_cogs_from_directory
(rglob récursif sur cogs/). Maintient un cache des invites par serveur et
détecte, à chaque on_member_join, l'invite utilisée pour attribuer l'arrivée
au bon inviteur.

Logique métier (V4) :

- on_ready : peuple le cache pour chaque guild où le bot a la permission.
- on_invite_create / on_invite_delete : maintient le cache à jour.
- on_member_join :
    1. ignore les bots
    2. si système désactivé pour la guild → skip
    3. compare invites actuelles vs cache → identifie le code utilisé
    4. détermine "fake" si compte < 7 jours (règle V3)
    5. record_join() : crée le lien membre→inviteur + incrémente regular/fake
    6. met à jour le cache
    7. si inviter atteint le seuil et système activé → attribue le rôle-récompense
- on_member_remove :
    1. ignore les bots / si système désactivé / si lien absent ou déjà compté
    2. règle V3 : pénalité "left" uniquement si départ < 24h après l'arrivée
    3. mark_left() : retrouve le VRAI inviteur via la table de liens et incrémente "left"

⚠️ Détection : deux mécanismes complémentaires.

1. Invite à usages multiples (illimité ou non) : toujours présente dans
   `guild.invites()` après le join, avec `uses` incrémenté → détectée par
   diff de compteur (mécanisme historique, inchangé).

2. Invite à usage UNIQUE (max_uses=1) ou qui vient d'atteindre son max_uses :
   Discord la SUPPRIME dès qu'elle est consommée. Elle est donc absente de
   `guild.invites()` au moment où on_member_join s'exécute — un simple diff
   de compteur ne peut jamais la voir puisqu'elle a disparu de la liste
   observée. C'était un bug réel : toute arrivée via un lien à usage unique
   n'était jamais attribuée (inviter_id restait toujours None). Corrigé en
   gardant, pour chaque code, un instantané (uses/max_uses/inviter) — à la
   fois dans le cache courant et dans un tampon `_recent_deletes` alimenté
   par on_invite_delete — et en traitant comme candidate toute invite connue
   qui a disparu alors qu'elle était sur le point d'atteindre son max_uses.

Cas non détectables (limite inhérente à une détection par diff, non
spécifique à cette correction) : arrivée via vanity URL, lien externe,
race condition (deux arrivées quasi simultanées sur deux invites différentes
avant rafraîchissement du cache). Dans ces cas, le lien est enregistré avec
inviter_id=None (pas de pénalité au départ, pas d'incrémentation regular/fake).
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord.ext import commands

from utils.managers.invite_manager import (
    get_link,
    load_invite_config,
    mark_left,
    record_join,
)

log = logging.getLogger(__name__)

# Règles métier (fidèles V3, non configurables).
FAKE_ACCOUNT_AGE = timedelta(days=7)
LEFT_PENALTY_WINDOW = timedelta(days=1)

# Durée pendant laquelle une invite tout juste supprimée reste consultable
# pour l'attribution d'un join (voir _recent_deletes ci-dessous).
RECENT_DELETE_TTL_SECONDS = 15.0

InviteSnapshot = dict  # {"uses": int, "max_uses": int, "inviter_id": int | None, "inviter_is_bot": bool}


class InviteListener(commands.Cog):
    """Cog de tracking des invitations."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # {guild_id: {code: InviteSnapshot}} — instantané complet (pas
        # seulement le compteur "uses") afin de pouvoir attribuer un join même
        # quand l'invite a disparu (usage unique consommé).
        self._invite_cache: dict[int, dict[str, InviteSnapshot]] = {}
        # {guild_id: {code: {**InviteSnapshot, "deleted_at": float}}} — tampon
        # des invites tout juste supprimées, pour couvrir le cas où
        # on_invite_delete traite la suppression AVANT que on_member_join
        # n'ait eu la main sur le lock (l'ordre relatif des deux events n'est
        # pas garanti par la gateway).
        self._recent_deletes: dict[int, dict[str, InviteSnapshot]] = {}
        # Lock par guild pour sérialiser cache_invites ↔ on_member_join ↔ on_invite_delete.
        self._guild_locks: dict[int, asyncio.Lock] = {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _lock_for(self, guild_id: int) -> asyncio.Lock:
        lock = self._guild_locks.get(guild_id)
        if lock is None:
            lock = asyncio.Lock()
            self._guild_locks[guild_id] = lock
        return lock

    @staticmethod
    def _snapshot_invite(invite: discord.Invite) -> InviteSnapshot:
        inviter = invite.inviter
        return {
            "uses": invite.uses or 0,
            "max_uses": getattr(invite, "max_uses", 0) or 0,
            "inviter_id": inviter.id if inviter is not None else None,
            "inviter_is_bot": bool(inviter is not None and inviter.bot),
        }

    def _prune_recent_deletes(self, guild_id: int) -> None:
        recent = self._recent_deletes.get(guild_id)
        if not recent:
            return
        now = time.monotonic()
        expired = [
            code for code, snap in recent.items()
            if now - snap.get("deleted_at", 0.0) > RECENT_DELETE_TTL_SECONDS
        ]
        for code in expired:
            recent.pop(code, None)

    async def _refresh_cache(self, guild: discord.Guild) -> dict[str, InviteSnapshot] | None:
        """
        Récupère les invites Discord et écrit le cache de la guild. Renvoie le
        nouveau cache, ou None si on n'a pas la permission de lire les invites.
        """
        try:
            invites = await guild.invites()
        except discord.Forbidden:
            log.warning(
                "[Invite] Permission 'Gérer le serveur' manquante → cache impossible "
                "pour la guild %s (%s)",
                guild.name, guild.id,
            )
            return None
        except discord.HTTPException:
            log.exception("[Invite] Échec récupération invites guild %s", guild.id)
            return None

        cache = {invite.code: self._snapshot_invite(invite) for invite in invites}
        self._invite_cache[guild.id] = cache
        return cache

    @staticmethod
    def _resolve_inviter(
        inviter_id: Optional[int], inviter_is_bot: bool, joining_member_id: int
    ) -> Optional[int]:
        """Filtre les inviteurs invalides (bot, ou membre s'auto-invitant)."""
        if inviter_id is None or inviter_is_bot or inviter_id == joining_member_id:
            return None
        return inviter_id

    @classmethod
    def _detect_used_code(
        cls,
        before: dict[str, InviteSnapshot],
        recent_deleted: dict[str, InviteSnapshot],
        current: dict[str, "discord.Invite"],
        joining_member_id: int,
    ) -> Optional[tuple[str, Optional[int]]]:
        """
        Détermine l'invite utilisée pour ce join. Renvoie (code, inviter_id)
        ou None si ambigu/indétectable. `inviter_id` est déjà filtré (bot /
        auto-invitation exclus).

        Deux sources de candidats :
        1. Invite toujours présente dans `current`, avec uses incrémenté par
           rapport à `before` (invite à usages multiples, y compris illimitée).
        2. Invite connue (dans `before` OU `recent_deleted`) mais absente de
           `current`, qui était sur le point d'atteindre son max_uses — c'est
           la signature d'une invite à usage unique (ou dernier usage
           disponible) qui vient d'être consommée puis supprimée par Discord.
        """
        candidates: list[tuple[str, Optional[int]]] = []

        # 1) Compteur incrémenté sur une invite toujours en vie.
        for code, invite in current.items():
            old = before.get(code)
            new_uses = invite.uses or 0
            inviter = invite.inviter
            inviter_id = inviter.id if inviter is not None else None
            inviter_is_bot = bool(inviter is not None and inviter.bot)

            if old is None:
                # Invite apparue entre deux events (race) : si uses >= 1 et le
                # cache ne la connaissait pas encore, on la considère candidate.
                if new_uses >= 1:
                    candidates.append((code, cls._resolve_inviter(inviter_id, inviter_is_bot, joining_member_id)))
            elif new_uses > old.get("uses", 0):
                candidates.append((code, cls._resolve_inviter(inviter_id, inviter_is_bot, joining_member_id)))

        # 2) Invite disparue (usage unique consommé, ou dernier usage atteint).
        known_gone_sources: dict[str, InviteSnapshot] = {**before, **recent_deleted}
        for code, snap in known_gone_sources.items():
            if code in current:
                continue
            max_uses = snap.get("max_uses", 0)
            uses = snap.get("uses", 0)
            # max_uses=0 signifie illimité chez Discord : une invite illimitée
            # ne disparaît jamais "d'usure", donc on ne considère ce cas que
            # pour une invite à usages limités sur le point d'être épuisée.
            if max_uses and uses + 1 >= max_uses:
                candidates.append((
                    code,
                    cls._resolve_inviter(
                        snap.get("inviter_id"), snap.get("inviter_is_bot", False), joining_member_id,
                    ),
                ))

        if len(candidates) == 1:
            return candidates[0]
        return None  # ambigu ou aucun

    async def _maybe_grant_reward(
        self,
        guild: discord.Guild,
        inviter_id: int,
        inviter_total: int,
        cfg: dict,
    ) -> None:
        """Attribue le rôle-récompense si l'inviteur atteint le seuil."""
        threshold = cfg.get("reward_threshold", 10)
        role_id = cfg.get("reward_role_id")
        if role_id is None or threshold <= 0 or inviter_total < threshold:
            return

        inviter_member = guild.get_member(inviter_id)
        if inviter_member is None or inviter_member.bot:
            return

        role = guild.get_role(role_id)
        if role is None:
            return
        if role in inviter_member.roles:
            return
        # Garde-fous (le rôle-récompense pourrait avoir été déplacé après config) :
        # rôle géré ou @everyone → on ne tente pas.
        if role.is_default() or role.managed:
            return
        # Hiérarchie : on n'attribue pas si le rôle est >= top_role du bot.
        me = guild.me
        if me is not None and role >= me.top_role:
            log.info(
                "[Invite] Rôle-récompense %s ignoré (au-dessus du bot) guild=%s",
                role.id, guild.id,
            )
            return

        try:
            await inviter_member.add_roles(role, reason="Récompense d'invitations atteinte")
            log.info(
                "[Invite] Rôle-récompense '%s' attribué à %s (guild=%s, total=%d)",
                role.name, inviter_member.id, guild.id, inviter_total,
            )
        except discord.Forbidden:
            log.warning(
                "[Invite] Impossible d'attribuer '%s' à %s (Forbidden, guild=%s)",
                role.name, inviter_member.id, guild.id,
            )
        except discord.HTTPException:
            log.exception(
                "[Invite] Erreur HTTP en attribuant '%s' à %s (guild=%s)",
                role.name, inviter_member.id, guild.id,
            )

    # ------------------------------------------------------------------
    # Listeners
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Peuple le cache des invites pour chaque guild au démarrage."""
        for guild in self.bot.guilds:
            await self._refresh_cache(guild)
        log.info(
            "[Invite] Cache initialisé pour %d guild(s)", len(self._invite_cache)
        )

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite) -> None:
        guild = invite.guild
        if not isinstance(guild, discord.Guild):
            return
        async with self._lock_for(guild.id):
            self._invite_cache.setdefault(guild.id, {})
            self._invite_cache[guild.id][invite.code] = self._snapshot_invite(invite)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite) -> None:
        guild = invite.guild
        if not isinstance(guild, discord.Guild):
            return
        async with self._lock_for(guild.id):
            cache = self._invite_cache.get(guild.id)
            entry = cache.pop(invite.code, None) if cache is not None else None
            if entry is None:
                # Invite jamais vue dans notre cache (bot lancé après sa
                # création, par ex.) : on reconstruit un instantané minimal
                # depuis l'objet fourni par l'event.
                entry = self._snapshot_invite(invite)

            recent = self._recent_deletes.setdefault(guild.id, {})
            recent[invite.code] = {**entry, "deleted_at": time.monotonic()}
            self._prune_recent_deletes(guild.id)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return

        guild = member.guild
        cfg = await load_invite_config(guild.id)
        if not cfg.get("enabled"):
            return

        async with self._lock_for(guild.id):
            # Récupération des invites actuelles
            try:
                current_list = await guild.invites()
            except discord.Forbidden:
                log.warning(
                    "[Invite] Pas de permission pour lire les invites (guild=%s) "
                    "— arrivée de %s non attribuée",
                    guild.id, member.id,
                )
                current_list = []
            except discord.HTTPException:
                log.exception("[Invite] Erreur récup invites (guild=%s)", guild.id)
                current_list = []

            current_by_code = {inv.code: inv for inv in current_list}

            # Cache pas encore initialisé : on initialise et on enregistre le
            # lien sans inviteur (membre arrivé avant le 1er load).
            if guild.id not in self._invite_cache:
                self._invite_cache[guild.id] = {
                    code: self._snapshot_invite(inv) for code, inv in current_by_code.items()
                }
                used = None
            else:
                before = self._invite_cache[guild.id]
                recent_deleted = self._recent_deletes.get(guild.id, {})
                self._prune_recent_deletes(guild.id)

                used = self._detect_used_code(before, recent_deleted, current_by_code, member.id)

                # MAJ du cache (instantané complet)
                self._invite_cache[guild.id] = {
                    code: self._snapshot_invite(inv) for code, inv in current_by_code.items()
                }
                # Le code identifié comme consommé ne doit plus servir à
                # attribuer un futur join (évite une double-attribution si un
                # 2e join arrivait après coup sur le même code déjà disparu).
                if used is not None:
                    recent_deleted.pop(used[0], None)

        # Détermination inviter + fake
        inviter_id = None
        invite_code = None
        if used is not None:
            invite_code, inviter_id = used

        is_fake = self._is_fake_account(member) if inviter_id is not None else False

        # Enregistrement (lien + incrément du compteur)
        try:
            inviter_stats = await record_join(
                guild.id, member.id, inviter_id, invite_code, is_fake
            )
        except Exception:
            log.exception(
                "[Invite] record_join échoué (guild=%s, member=%s)", guild.id, member.id
            )
            return

        log.info(
            "[Invite] Join %s (guild=%s) inviter=%s code=%s fake=%s total_inviter=%d",
            member.id, guild.id, inviter_id, invite_code, is_fake,
            inviter_stats.get("total", 0),
        )

        # Attribution du rôle-récompense (sur invite non-fake uniquement)
        if inviter_id is not None and not is_fake:
            await self._maybe_grant_reward(
                guild, inviter_id, inviter_stats.get("total", 0), cfg
            )

    @staticmethod
    def _is_fake_account(member: discord.Member) -> bool:
        """True si le compte du membre a moins de FAKE_ACCOUNT_AGE."""
        age = datetime.now(timezone.utc) - member.created_at
        return age < FAKE_ACCOUNT_AGE

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if member.bot:
            return

        guild = member.guild
        cfg = await load_invite_config(guild.id)
        if not cfg.get("enabled"):
            return

        link = await get_link(guild.id, member.id)
        if link is None or link.get("inviter_id") is None or link.get("counted_left"):
            return

        # Règle V3 : pénalité uniquement si départ < 24h après l'arrivée.
        joined_at = link.get("created_at")
        if joined_at is not None:
            # Sur PostgreSQL avec DateTime(timezone=True), joined_at est tz-aware.
            # Sur SQLite ou en cas de driver non-tz-aware, il peut être naïf :
            # on l'aligne sur UTC (server_default=now() stocke en UTC).
            if joined_at.tzinfo is None:
                joined_at = joined_at.replace(tzinfo=timezone.utc)
            elapsed = datetime.now(timezone.utc) - joined_at
            if elapsed >= LEFT_PENALTY_WINDOW:
                return

        try:
            result = await mark_left(guild.id, member.id)
        except Exception:
            log.exception(
                "[Invite] mark_left échoué (guild=%s, member=%s)", guild.id, member.id
            )
            return

        if result is not None:
            inviter_id, stats = result
            log.info(
                "[Invite] Leave %s (guild=%s) attribué à inviter=%s total=%d",
                member.id, guild.id, inviter_id, stats.get("total", 0),
            )


# ----------------------------------------------------
# 🔧 Setup du cog
# ----------------------------------------------------

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(InviteListener(bot))