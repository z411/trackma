# -*- coding: utf-8 -*-
# This file is part of Trackma.
# This configuration file is licensed under the same terms as Trackma.
# ===================================
#
# To use this file, you must move it to ~/.trackma/hooks/my_hook.py
#
# ===================================
# This Python file contains hook functions for Trackma's engine signals.
# You can customize it freely to make Trackma do what you want after
# changes in your list have been made.
#
# These functions are called upon immediately by Trackma after the
# signal of the same name has been triggered. A reference to the Engine
# and the relevant arguments are also passed to the function.
#
# You can have several hook files in the "hooks" directory.
# ===================================

# These functions are called when changes are made locally.
def playing(engine, show, is_playing, episode):
    """This is called when a player is detected to be playing a show.
    It's called both when the player is opened (is_playing=True) and
    when the player is closed (is_playing=False).

    `show`: dictionary with the information of the show
    `is_playing`: boolean signaling whether the player has been opened or closed
    `episode`: episode number
    """

    pass

def show_added(engine, show):
    """This is called after an item has been added to the local list.
    `show` contains the item information as a dictionary."""
    pass

def episode_changed(engine, show):
    """This is called after the episode of an item has been updated in the local list.
    `show` contains the item information as a dictionary."""
    pass

def score_changed(engine, show):
    """This is called after the episode of an item has been updated in the local list.
    `show` contains the item information as a dictionary."""
    pass

def status_changed(engine, show, old_status):
    """This is called after the status of an item has been updated in the local list.
    `show` contains the item information as a dictionary.
    `old_status` contains the status ID before the change."""
    pass

def show_deleted(engine, show):
    """This is called after an item has been deleted from the local list.
    `show` contains the item information as a dictionary."""
    pass

# These functions are called when the change is made remotely.
def show_synced(engine, show, change):
    """This is called when an item has been synced with the remote list correctly.
    If the queue has multiple items, this is called once for each item after it's processed.

    `show` contains the item information as a dictionary.
    `change` contains a dictionary that includes only the keys that were changed,
    and a special key 'action' (add|update|delete) that identifies the change type.
    """

    if change['action'] == 'add':
        print("Show ID %d, title %s, was added to the remote list." % (show['id'], show['title']))
    elif change['action'] == 'update':
        print("Show ID %d, title %s, was updated in the remote list." % (show['id'], show['title']))
    elif change['action'] == 'delete':
        print("Show ID %d, title %s, was deleted from the remote list." % (show['id'], show['title']))

def sync_complete(engine, items):
    """This is called after the entire queue has been processed.
    Unlike show_synced, it's only called once after all itmes have been processed,
    and `items` contains a list of tuples (show,change) of all the shows that were
    processed correctly.
    """

    print("Finished. List of changes made: ")
    for item in items:
        (show, change) = item
        print("Action: %s, show ID: %d" % (change['action'], show['id']))
