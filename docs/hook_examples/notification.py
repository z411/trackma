# -*- coding: utf-8 -*-
#
# This hook generates a system notification for Linux when using MAL
#
# Written by matoro, last updated 2016/09/01
# https://github.com/matoro/
# https://myanimelist.net/profile/Matoro_Mahri
#
# To use, copy this file to ~/.trackma/hook.py and fill in the access token.

##### Hook start #####

import os
import trackma.utils as utils

def notifyupdate(engine, show):
    os.system('notify-send --icon=/usr/lib/python3.5/site-packages/trackma/data/mal.jpg --app-name=trackma "Updated '+show['title']+'" "Progress: '+str(show['my_progress'])+'/'+str(show['total'])+'"')

##### HOOK END #####

def episode_changed(engine, show):
    notifyupdate(engine, show)

