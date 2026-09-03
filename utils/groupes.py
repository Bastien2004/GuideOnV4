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


# Groupe Iris
class GroupeIRIS(app_commands.Group):
    def __init__(self):
        super().__init__(name="iris", description="Commandes Discord Iris")

def groupeIRIS():
    return GroupeIRIS()


# Groupe Birthday
class GroupeBIRTHDAY(app_commands.Group):
    def __init__(self):
        super().__init__(name="birthday", description="Commandes anniversaire")

def groupeBIRTHDAY():
    return GroupeBIRTHDAY()


# Groupe NG Staff
class GroupeNGSTAFF(app_commands.Group):
    def __init__(self):
        super().__init__(name="ngstaff", description="Commandes staff NationsGlory")

def groupeNGSTAFF():
    return GroupeNGSTAFF()


# Groupe qr
class GroupeQR(app_commands.Group):
    def __init__(self):
        super().__init__(name="qr", description="Commandes QR code")

def groupeQR():
    return GroupeQR()

'''
class GroupeMEDIALINK(app_commands.Group):
    def __init__(self):
        super().__init__(name="medialink", description="Commandes MEDIALINK")

def groupeMEDIALINK():
    return GroupeMEDIALINK()
'''