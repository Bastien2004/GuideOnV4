"""
utils/groupes.py — Groupes de commandes slash.
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