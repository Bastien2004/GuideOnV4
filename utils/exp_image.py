"""
utils/exp_image.py — Generation de la carte de niveau EXP d'un joueur.

Utilise un fond parmi ceux deja presents dans source/ (fond_exp_1..8.webp).
Repris a l'identique de la V3 (meme mise en page, meme fond actif), seul le
stockage change (EXP lue via utils.managers.exp_manager, DB, plus JSON).
"""
from __future__ import annotations

import io
import logging
import os

import aiohttp
from PIL import Image, ImageChops, ImageDraw, ImageFont

from utils.managers.exp_manager import level_progress, tier_name_for_level

log = logging.getLogger(__name__)

SOURCE_PATH = os.path.join(os.path.dirname(__file__), "..", "source")
BACKGROUND_FILENAME = "fond_exp_8.webp"

_FONT_CANDIDATES_BOLD = [
    "arialbd.ttf",
    "Arial Bold.ttf",
    "DejaVuSans-Bold.ttf",
    "LiberationSans-Bold.ttf",
    "FreeSansBold.ttf",
]
_FONT_CANDIDATES_REGULAR = [
    "arial.ttf",
    "Arial.ttf",
    "DejaVuSans.ttf",
    "LiberationSans-Regular.ttf",
    "FreeSans.ttf",
]


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Charge une police (police custom > polices systeme > police par defaut)."""
    candidates = _FONT_CANDIDATES_BOLD if bold else _FONT_CANDIDATES_REGULAR
    custom = os.path.join(SOURCE_PATH, "cool_font.ttf")
    if os.path.exists(custom):
        try:
            return ImageFont.truetype(custom, size)
        except OSError:
            log.warning("Police custom illisible (%s), bascule sur les polices systeme", custom)

    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue

    log.warning("Aucune police TrueType disponible, bascule sur la police par defaut PIL")
    return ImageFont.load_default()


class ExpImageBuilder:
    """Construit l'image de niveau EXP (avatar + tier + barre de progression)."""

    def __init__(self, member, total_exp: int):
        self.member = member
        self.total_exp = total_exp

    async def build(self) -> io.BytesIO:
        stats = level_progress(self.total_exp)

        fond_path = os.path.join(SOURCE_PATH, BACKGROUND_FILENAME)
        if os.path.exists(fond_path):
            background = Image.open(fond_path).convert("RGBA")
        else:
            log.warning("Fond EXP introuvable (%s), fond uni utilise en secours", fond_path)
            background = Image.new("RGBA", (1200, 400), (30, 30, 50, 255))

        width, height = background.size

        # ── Overlay noir semi-transparent ──
        overlay = Image.new("RGBA", background.size, (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        margin = int(width * 0.025)
        draw_overlay.rounded_rectangle(
            [margin, margin, width - margin, height - margin],
            radius=int(min(width, height) * 0.05),
            fill=(0, 0, 0, 90),
        )
        background = Image.alpha_composite(background, overlay)

        # ── Avatar (taille relative a la hauteur, centrage vertical) ──
        async with aiohttp.ClientSession() as session:
            async with session.get(self.member.display_avatar.url) as resp:
                avatar_bytes = await resp.read()

        avatar_size = int(height * 0.62)
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        avatar = avatar.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)

        mask = Image.new("L", avatar.size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)
        avatar.putalpha(mask)

        avatar_x = int(width * 0.07)
        avatar_y = (height - avatar_size) // 2

        border_width = 7
        contour_size = avatar_size + border_width * 2
        contour = Image.new("RGBA", (contour_size, contour_size), (0, 0, 0, 0))
        ImageDraw.Draw(contour).ellipse((0, 0, contour_size, contour_size), fill=(255, 255, 255, 255))
        background.paste(contour, (avatar_x - border_width, avatar_y - border_width), contour)
        background.paste(avatar, (avatar_x, avatar_y), avatar)

        # ── Polices ──
        font_name = _load_font(int(height * 0.175), bold=True)
        font_medium = _load_font(int(height * 0.105), bold=True)
        font_small = _load_font(int(height * 0.068), bold=False)

        draw = ImageDraw.Draw(background)
        text_x = avatar_x + avatar_size + int(width * 0.07)

        username = self.member.display_name
        tier_full = tier_name_for_level(stats["level"])
        tier_name_str = "".join(c for c in tier_full if c.isalnum() or c == " ").strip()

        progress = stats["progress_ratio"]
        exp_in_level = self.total_exp - stats["level_start_exp"]
        exp_needed = stats["next_level_exp"] - stats["level_start_exp"]

        if stats["level"] >= 200:
            exp_text = f"MAX LEVEL — {self.total_exp} EXP Total"
            progress = 1.0
        else:
            exp_text = f"{exp_in_level} / {exp_needed} EXP"

        name_h = draw.textbbox((0, 0), username, font=font_name)[3]
        tier_h = draw.textbbox((0, 0), tier_name_str, font=font_medium)[3]
        exp_h = draw.textbbox((0, 0), exp_text, font=font_small)[3]

        bar_height = int(height * 0.115)
        bar_width = int(width * 0.50)

        gap_name_tier = int(height * 0.045)
        gap_tier_exp = int(height * 0.065)
        gap_exp_bar = int(height * 0.025)

        block_height = name_h + gap_name_tier + tier_h + gap_tier_exp + exp_h + gap_exp_bar + bar_height
        block_y = (height - block_height) // 2

        pseudo_y = block_y
        tier_y = pseudo_y + name_h + gap_name_tier
        exp_y = tier_y + tier_h + gap_tier_exp
        bar_y = exp_y + exp_h + gap_exp_bar

        # ── Pseudo ──
        draw.text((text_x + 3, pseudo_y + 3), username, font=font_name, fill=(0, 0, 0, 150))
        draw.text((text_x, pseudo_y), username, font=font_name, fill=(255, 255, 255, 255))

        # ── Tier + niveau ──
        draw.text((text_x, tier_y), tier_name_str, font=font_medium, fill=(80, 180, 255, 255))
        tier_width = draw.textbbox((text_x, tier_y), tier_name_str, font=font_medium)[2] - text_x
        draw.text(
            (text_x + tier_width, tier_y),
            f" — Niveau {stats['level']}",
            font=font_medium,
            fill=(210, 210, 210, 255),
        )

        # ── Label EXP ──
        draw.text((text_x + 2, exp_y + 2), exp_text, font=font_small, fill=(0, 0, 0, 120))
        draw.text((text_x, exp_y), exp_text, font=font_small, fill=(255, 255, 255, 255))

        # ── Barre EXP ──
        # La piste (fond) est une pilule arrondie (rounded_rectangle). Le
        # remplissage doit épouser exactement la même forme des deux côtés :
        # on le dessine en colonnes pleine hauteur puis on le découpe avec un
        # masque de la même forme arrondie, sinon les coins du remplissage
        # ressortent carrés au niveau du bord gauche/droit de la piste.
        bar_img = Image.new("RGBA", (bar_width, bar_height), (0, 0, 0, 0))
        bar_draw = ImageDraw.Draw(bar_img)
        bar_radius = bar_height // 2

        bar_draw.rounded_rectangle(
            [0, 0, bar_width, bar_height],
            radius=bar_radius,
            fill=(75, 75, 85, 255),
            outline=(130, 130, 140, 255),
            width=2,
        )

        filled = int((bar_width - 4) * progress)
        if filled > 0:
            fill_layer = Image.new("RGBA", (bar_width, bar_height), (0, 0, 0, 0))
            fill_draw = ImageDraw.Draw(fill_layer)
            for i in range(filled):
                t = i / max(filled, 1)
                r = int(60 + (120 - 60) * t)
                g = int(140 + (200 - 140) * t)
                b = 255
                fill_draw.rectangle([2 + i, 2, 3 + i, bar_height - 2], fill=(r, g, b, 255))

            pill_mask = Image.new("L", (bar_width, bar_height), 0)
            ImageDraw.Draw(pill_mask).rounded_rectangle(
                [0, 0, bar_width, bar_height], radius=bar_radius, fill=255,
            )
            fill_layer.putalpha(ImageChops.multiply(fill_layer.getchannel("A"), pill_mask))

            bar_img = Image.alpha_composite(bar_img, fill_layer)

        background.paste(bar_img, (text_x, bar_y), bar_img)

        buffer = io.BytesIO()
        background.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer
