"""
views/ticket/transcript.py — Génération de transcript + suppression définitive.
"""
from __future__ import annotations

import asyncio
import datetime
import html
import io
import json
import logging

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.container_universel import error_container, success_container
from utils.managers import ticket_manager as tm

log = logging.getLogger(__name__)

DELETE_DELAY_SECONDS = 8

# ============================================================
# 🧱 Template HTML (identique V3)
# ============================================================

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Transcript {base_name}</title>
    <style>
        :root {{
            --bg: #1e1e2e; --surface: #313244; --text: #cdd6f4;
            --subtext: #a6adc8; --accent: #89b4fa; --purple: #cba6f7;
            --green: #a6e3a1; --red: #f38ba8;
        }}
        body {{
            font-family: 'Whitney', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            background: var(--bg); color: var(--text); margin: 0; padding: 40px 20px;
            display: flex; justify-content: center;
        }}
        .container {{ max-width: 900px; width: 100%; }}
        .header {{
            background: var(--surface); padding: 25px; border-radius: 12px;
            border-left: 5px solid var(--accent); margin-bottom: 30px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }}
        h1 {{ margin: 0 0 10px 0; color: var(--accent); font-size: 24px; }}
        .meta-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; font-size: 14px; }}
        .meta-item b {{ color: var(--subtext); text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; }}
        .meta-item p {{ margin: 3px 0 0 0; font-weight: 500; }}

        .chat {{ display: flex; flex-direction: column; gap: 20px; }}
        .message-group {{ display: flex; gap: 16px; transition: background 0.2s; padding: 5px; border-radius: 8px; }}
        .message-group:hover {{ background: rgba(255,255,255,0.02); }}
        .avatar {{ width: 45px; height: 45px; border-radius: 50%; background: var(--surface); flex-shrink: 0; }}
        .content-wrapper {{ flex-grow: 1; }}
        .author-info {{ display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }}
        .author-name {{ font-weight: 600; color: var(--purple); }}
        .timestamp {{ font-size: 12px; color: var(--subtext); }}
        .msg-text {{ font-size: 15px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }}

        .attachment-box {{
            margin-top: 10px; padding: 10px; background: #181825; border-radius: 8px;
            border: 1px solid var(--surface); display: inline-flex; align-items: center; gap: 10px;
        }}
        .attachment-box a {{ color: var(--accent); text-decoration: none; font-size: 13px; }}
        .attachment-box a:hover {{ text-decoration: underline; }}
        .img-preview {{ max-width: 100%; border-radius: 8px; margin-top: 10px; max-height: 400px; border: 1px solid var(--surface); }}

        footer {{ margin-top: 50px; text-align: center; color: var(--subtext); font-size: 12px; opacity: 0.6; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎫 Transcript : {base_name}</h1>
            <div class="meta-grid">
                <div class="meta-item"><b>ID Ticket</b><p>{ticket_num}</p></div>
                <div class="meta-item"><b>Créateur</b><p>{pseudo} ({creator_id})</p></div>
                <div class="meta-item"><b>Raison</b><p>{raison}</p></div>
                <div class="meta-item"><b>Date de fermeture</b><p>{date_now}</p></div>
            </div>
        </div>
        <div class="chat">
            {rows}
        </div>
        <footer>Généré par GuideON Studio • Système de Tickets</footer>
    </div>
</body>
</html>"""


# ============================================================
# 📄 Génération du transcript
# ============================================================

async def generate_transcripts(channel: discord.TextChannel, ticket: dict) -> tuple:
    """Renvoie ((html_bytes, html_name), (json_bytes, json_name))."""
    messages_data = []

    async for msg in channel.history(limit=1000, oldest_first=True):
        content_escaped = html.escape(msg.clean_content) if msg.clean_content else ""
        messages_data.append({
            "author": str(msg.author),
            "author_id": msg.author.id,
            "avatar": str(msg.author.display_avatar.url),
            "timestamp": msg.created_at.strftime("%d/%m/%Y %H:%M"),
            "content": content_escaped,
            "attachments": [
                {
                    "url": a.url,
                    "is_img": (a.content_type.startswith("image") if a.content_type else False),
                }
                for a in msg.attachments
            ],
        })

    ticket_num = ticket.get("ticket_number", "0000")
    base_name = f"ticket-{ticket_num}"
    pseudo = ticket.get("pseudo") or str(ticket.get("creator_id", "?"))

    json_bytes = io.BytesIO(
        json.dumps(
            {"ticket": ticket, "messages": messages_data},
            indent=2, ensure_ascii=False,
        ).encode("utf-8")
    )
    json_bytes.seek(0)

    rows = ""
    for m in messages_data:
        att_html = ""
        for att in m["attachments"]:
            if att["is_img"]:
                att_html += f'<img src="{att["url"]}" class="img-preview">'
            else:
                att_html += (
                    f'<div class="attachment-box">📎 '
                    f'<a href="{att["url"]}" target="_blank">Fichier joint</a></div>'
                )

        rows += f"""
        <div class="message-group">
            <img src="{m['avatar']}" class="avatar">
            <div class="content-wrapper">
                <div class="author-info">
                    <span class="author-name">{m['author']}</span>
                    <span class="timestamp">{m['timestamp']}</span>
                </div>
                <div class="msg-text">{m['content'] or "<i>Composant ou Embed</i>"}</div>
                {att_html}
            </div>
        </div>"""

    html_content = HTML_TEMPLATE.format(
        base_name=base_name,
        ticket_num=ticket_num,
        pseudo=pseudo,
        creator_id=ticket.get("creator_id", "?"),
        raison=ticket.get("raison", "Non précisée"),
        date_now=datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        rows=rows,
    )
    html_bytes = io.BytesIO(html_content.encode("utf-8"))
    html_bytes.seek(0)

    return (html_bytes, f"{base_name}.html"), (json_bytes, f"{base_name}.json")


# ============================================================
# 🗑️ Suppression définitive
# ============================================================

async def do_delete_ticket(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    ticket: dict,
) -> None:
    """Archive (transcript) → supprime en DB → supprime le salon après délai."""
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

    guild_id = interaction.guild_id
    panel = await tm.get_panel(guild_id, ticket.get("panel_id", ""))
    await interaction.followup.send(
        "⌛ Archivage et génération du transcript en cours...", ephemeral=True
    )

    try:
        (h_bytes, h_name), (j_bytes, j_name) = await generate_transcripts(channel, ticket)

        if panel:
            tc_id = panel.get("transcript_channel_id")
            tc = interaction.guild.get_channel(int(tc_id)) if tc_id else None
            if tc:
                log_view = LayoutView(timeout=None)
                lc = Container()
                lc.add_item(TextDisplay(f"# 📄 Transcript : Ticket #{ticket.get('ticket_number')}"))
                lc.add_item(Separator())
                lc.add_item(TextDisplay(
                    f"**Utilisateur :** <@{ticket['creator_id']}>.\n"
                    f"**Fermé par :** {interaction.user.mention}.\n"
                    f"**Raison :** `{ticket.get('raison', 'Inconnue')}`."
                ))
                lc.add_item(Separator())
                lc.add_item(TextDisplay("-# GuideON Studio"))
                log_view.add_item(lc)

                await tc.send(view=log_view)
                await tc.send(files=[
                    discord.File(fp=h_bytes, filename=h_name),
                    discord.File(fp=j_bytes, filename=j_name),
                ])
            else:
                log.warning("Salon transcript %s introuvable (guild=%s).", tc_id, guild_id)

        await tm.delete_ticket(channel.id)

        await interaction.followup.send(
            view=success_container(
                "Le transcript a été envoyé. Ce salon va maintenant être supprimé."
            ),
            ephemeral=True,
        )

        await asyncio.sleep(DELETE_DELAY_SECONDS)
        await channel.delete(
            reason=f"Ticket #{ticket.get('ticket_number')} supprimé par {interaction.user}"
        )

    except Exception:
        log.exception("Erreur critique pendant la suppression du ticket %s.", channel.id)
        await interaction.followup.send(
            view=error_container("Une erreur est survenue lors de la génération du transcript."),
            ephemeral=True,
        )