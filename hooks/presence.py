"""
 Author: ahmubashshir
 Inspired by: slapelachie and github:DAgostinatrice/HQMediaPlayer
 A Discord RPC hook for the trackma client.
 Place under ~/.config/trackma/hooks/

 use images from pypresence-assets dir
 when creating discord application
"""
import os
import time
from asyncio import new_event_loop as new_loop
from asyncio import set_event_loop as set_loop
from threading import Thread

from pypresence.client import Client
from pypresence.exceptions import InvalidID, InvalidPipe

from trackma.utils import estimate_aired_episodes
from trackma.utils import Tracker

class DiscordRPC(Thread):
    """
    Discord RPC Thread

    Updates discord rich presence status periodically.
    """

    _client_id = "1014724581904367696"  # set discord application id here
    _enabled = False
    _update = False
    regret = True

    _rpc = None
    _pid = None
    _errors = (
        ConnectionRefusedError,
        InvalidID,
        InvalidPipe,
        FileNotFoundError,
        ConnectionResetError
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pid = os.getpid()

        self._details = {
            'details': "Regretting...",
            'state': None,
            'start': None,
            'img': None,
            'txt': None
        }

    def present(self, engine, start=None, details="Regretting...", state=None, url=None, thumb="icon"):
        """
        Set status for DiscordRPC.
        """
        self._details = {
            'details': details,
            'state': state,
            'start': time.time()*1000 - start if start else None,
            'thumb': thumb,
            'buttons': [ { "label": "View %s" % engine.api_info['mediatype'].capitalize(), "url": url } ] if url else None,
            'img': engine.account["api"],
            'txt': "{} at {}".format(
                engine.account["username"],
                engine.account["api"]
            )
        }
        self._update = True

    def run(self):
        set_loop(new_loop())
        while True:
            try:
                self._reconnect()
                if self._enabled and self._update:
                    if self._details['details'] == "Regretting..." \
                            and not self.regret:
                        self._rpc.clear_activity(pid=self._pid)
                    else:
                        self._rpc.set_activity(
                            pid=self._pid,
                            large_image=self._details['thumb'],
                            large_text=self._details['details'],
                            small_image=self._details['img'],
                            small_text=self._details['txt'],
                            buttons=self._details['buttons'],
                            details=self._details['details'],
                            state=self._details['state'],
                            start=self._details['start']
                        )
                    self._update = False
                time.sleep(1)
            except self._errors:
                self._enabled = False
                try:
                    self._rpc.close()
                except AttributeError:
                    pass

    def _reconnect(self):
        if not self._enabled:
            try:
                self._rpc = Client(self._client_id)
                self._rpc.start()
                self._enabled = True

            except self._errors:
                self._enabled = False


rpc = DiscordRPC(daemon=True)


def init(engine):
    """
    Initialize this hook.
    """
    rpc.start()
    rpc.present(engine)


def tracker_state(engine, status):
    """
    Update status in thread.
    """
    if status["state"] == Tracker.PLAYING or status["state"] == Tracker.IGNORED:
        show = status["show"][0]
        title = show["titles"][0]
        episode = status["show"][-1]
        url = engine.get_show_info(show['id'])["url"]
        thumb = engine.get_show_info(show['id'])["image"]
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
                        ),
                        url,
                        thumb
                        )
        else:
            rpc.present(engine,
                        status["viewOffset"],
                        "Watching {}".format(title),
                        "Episode {} of {}".format(
                            episode,
                            total
                        ),
                        url,
                        thumb
                        )

    else:
        rpc.present(engine)
