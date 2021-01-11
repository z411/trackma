#############################################
# Author: ahmubashshir                      #
# Inspired by: slapelachie                  #
#                                           #
# and github:DAgostinatrice/HQMediaPlayer   #
# A Discord RPC hook for the trackma client #
# Place under ~/.config/trackma/hooks/      #
#############################################

#############################################
# use images from pypresence-assets dir     #
# when creating discord application         #
#############################################

import time
import os

from pypresence.client import Client
from pypresence.exceptions import InvalidID, InvalidPipe
from trackma.utils import estimate_aired_episodes

from asyncio import (
    new_event_loop as new_loop,
    set_event_loop as set_loop)


class drpc:
    id = ""  # set discord application id here
    enabled = False
    rpc = None
    pid = None

    def __init__(self):
        # To prevent loop error with pypresence
        set_loop(new_loop())
        self.pid = os.getpid()

    def present(self, engine, start=None, details="Regretting...", state=None):
        self.restart()
        if self.enabled:
            try:
                self.rpc.set_activity(
                    pid=self.pid,
                    large_image="icon",
                    large_text=details,
                    small_image=engine.account["api"],
                    small_text=(
                        "{} at {}".format(
                            engine.account["username"],
                            engine.account["api"]
                        )
                    ),
                    details=details,
                    state=state,
                    start=time.time()*1000 - start if start else None,
                    instance=False
                )
            except InvalidID:
                self.enabled = False
                self.rpc.close()

    def restart(self):
        if not self.enabled:
            try:
                self.enabled = True
                self.rpc = Client(self.id)
                self.rpc.start()
            except InvalidPipe:
                self.enabled = False


rpc = drpc()


def init(engine):
    rpc.present(engine)


def tracker_state(engine, status):
    if status["state"] == 1:
        show = status["show"][0]
        title = show["titles"][0]
        episode = status["show"][-1]
        total = show["total"] or estimate_aired_episodes(
            engine.get_show_info(show['id'])
        ) or '?'

        if status["paused"]:
            rpc.present(engine,
                        status["viewOffset"],
                        "Paused {}".format(title),
                        "Episode {} of {}".format(
                            episode,
                            total
                        )
                        )
        else:
            rpc.present(engine,
                        status["viewOffset"],
                        "Watching {}".format(title),
                        "Episode {} of {}".format(
                            episode,
                            total
                        )
                        )

    else:
        rpc.present(engine)
