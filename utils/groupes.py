"""
utils/groupes.py — Groupes de commandes slash (V4, pattern V3 conservé).

On garde EXACTEMENT le pattern V3 : chaque groupe est une factory qui renvoie
une nouvelle instance d'app_commands.Group. bot.py instancie le groupe, y
attache les commandes (fonctions libres) via add_command(), puis fait
tree.add_command(groupe).

    # bot.py
    from utils.groupes import groupeCONFIG
    from cogs.config.bienvenue import bienvenue
    from cogs.config.autorole import autorole

    groupCONFIG = groupeCONFIG()
    for cmd in [bienvenue, autorole, ...]:
        groupCONFIG.add_command(cmd)
    self.tree.add_command(groupCONFIG)

IMPORTANT : les commandes sont des FONCTIONS LIBRES decorees @app_commands.command
(pas des methodes de cog). Un groupe partage module-level ne lie pas `self`, donc
le pattern cog ne convient pas pour des groupes eclates sur plusieurs fichiers.
"""
from discord import app_commands


# Groupe moderation
class GroupeMOD(app_commands.Group):
    def __init__(self):
        super().__init__(name="mod", description="Commandes de moderation")

def groupeMOD():
    return GroupeMOD()


# Groupe NationsGlory
class GroupeNG(app_commands.Group):
    def __init__(self):
        super().__init__(name="ng", description="Commandes NationsGlory")

def groupeNG():
    return GroupeNG()


# Groupe config
class GroupeCONFIG(app_commands.Group):
    def __init__(self):
        super().__init__(name="config", description="Commandes de configuration")

def groupeCONFIG():
    return GroupeCONFIG()


# Groupe event
class GroupeEVENT(app_commands.Group):
    def __init__(self):
        super().__init__(name="event", description="Commandes d'evenements")

def groupeEVENT():
    return GroupeEVENT()


# Groupe developpeur
class GroupeDEV(app_commands.Group):
    def __init__(self):
        super().__init__(name="dev", description="Commandes reservees aux developpeurs")

def groupeDEV():
    return GroupeDEV()


# Groupe experience
class GroupeEXP(app_commands.Group):
    def __init__(self):
        super().__init__(name="exp", description="Commandes systeme d'experience")

def groupeEXP():
    return GroupeEXP()


# Groupe giveaway
class GroupeGIVE(app_commands.Group):
    def __init__(self):
        super().__init__(name="giveaway", description="Commandes systeme de giveaway")

def groupeGIVE():
    return GroupeGIVE()


# Groupe invite
class GroupeINV(app_commands.Group):
    def __init__(self):
        super().__init__(name="invite", description="Commandes systeme d'invitation")

def groupeINV():
    return GroupeINV()


# Groupe ticket
class GroupeTICKET(app_commands.Group):
    def __init__(self):
        super().__init__(name="ticket", description="Commandes systeme de ticket")

def groupeTICKET():
    return GroupeTICKET()


# Groupe Alpha
class GroupeALPHA(app_commands.Group):
    def __init__(self):
        super().__init__(name="alpha", description="Commandes Discord Alpha")

def groupeALPHA():
    return GroupeALPHA()


# Groupe Anniversaire
class GroupeANNIV(app_commands.Group):
    def __init__(self):
        super().__init__(name="anniv", description="Commandes event anniversaire")

def groupeANNIV():
    return GroupeANNIV()


# Groupe Anniversaire Admin
class GroupeANNIVADMIN(app_commands.Group):
    def __init__(self):
        super().__init__(name="anniv_admin", description="Commandes administrateurs event anniversaire")

def groupeANNIVADMIN():
    return GroupeANNIVADMIN()