-------------------------------------------------------------------------------
wMAL v0.1 Copyright (c) 2012 z411 (electrik.persona@gmail.com)
Distributed under the GNU General Public License v3, see COPYING for details.
-------------------------------------------------------------------------------
wMAL aims to be a lightweight and simple but feature-rich terminal or GUI based
script for fetching, updating and using data from show lists from different
media tracking websites like MyAnimeList, Melative or VNDB.

The script logs into your account, and lets you review your list,
search for shows, and update your episodes all directly from the same client.
Aditionally it can search for a specified folder for the next episode
you have to watch and it starts your media player of choice automatically.
It also updates the episode automatically whenever the media player is closed,
or detect if there's a player running in your system.

REQUIREMENTS
============
- Tested with Python 2.7, but it should work in 2.6 too.
- (Optional) Urwid (python-urwid) for the curses/urwid interface.
- (Optional) PyGTK (python-gtk2) for the GTK interface.

USAGE
=====
Start the program by running any of the available interfaces:

$ ./wmal.py
$ ./wmal-curses.py (requires urwid)
$ ./wmal-gtk.py (requires pygtk)

PROPOSED MODEL
==============
The project aims to be scalable as to support different clients and anime
databases in the future. Here's the expected design method (may change):

Client (CLI)    <-->                          <--> libmelative <-->
Client (curses) <--> Engine <--> Data Handler <--> libmal      <--> Internet (API)
Client (GTK)    <-->                  |       <--> libanidb    <-->
                                      v              etc...
                                   Local DB

TO DO LIST
==========
- Clean up code.
- Improve regex for episode search.
- Add/delete support.
- Support for manga lists.
- Show user information.
- Win32 interface?
- Improve vndb, Melative and AniDB support.
