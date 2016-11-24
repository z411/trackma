# -*- coding: utf-8 -*-
#
# This hook generates a system notification for Linux when using MAL
#
# Written by matoro, last updated 2016/09/01
# https://github.com/matoro/
# https://myanimelist.net/profile/Matoro_Mahri
#
# To use, copy this file to ~/.trackma/hooks/

import os
import trackma.utils as utils

def episode_changed(engine, show):
    os.system('notify-send --icon=/usr/lib/python3.5/site-packages/trackma/data/mal.jpg --app-name=trackma "Updated '+show['title']+'" "Progress: '+str(show['my_progress'])+'/'+str(show['total'])+'"')

