"""
Génération de la carte EXP en PIL.

À reprendre du V3 (utils/exp_image.py, ~577 lignes) tel quel.
Aucune dépendance à la DB, c'est purement de la composition d'image.

Signature attendue :
    async def generate_exp_card(
        user: discord.User,
        level: int,
        current_xp: int,
        next_level_xp: int,
        rank: int,
        background: str = "fond_exp_1",
    ) -> discord.File:
        ...

TODO : recopier le contenu de l'ancien utils/exp_image.py et adapter les chemins
       d'assets vers source/fond_exp_*.png et source/font/*.ttf.
"""
