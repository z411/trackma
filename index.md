Trackma
=======

Trackma aims to be a lightweight and simple but feature-rich program for Unix based systems
for fetching, updating and using data from personal lists hosted in several media tracking websites.

Features
--------
- Manage local list and synchronize when necessary, useful when offline
- Manage multiple accounts on different media tracking sites
- Support for several mediatypes (as supported by the site)
- Multiple user interfaces (Qt, GTK, curses, command-line)
- Detection of running media player, updates list if necessary
- Ability to launch media player for a requested media in the list and update list if necessary
- Highly scalable, easy to code new interfaces and support for other sites

Currently supported websites
----------------------------
- [MyAnimeList](https://myanimelist.net/) (Anime, Manga)
- [Anilist](https://anilist.co/) (Anime, Manga)
- [Kitsu](https://kitsu.io/) (Anime, Manga, Drama)
- [VNDB](https://vndb.org/) (VNs)
- [Shikimori](https://shikimori.org/) (Anime, Manga)

Screenshots
-----------

Qt interface

![Qt](https://z411.github.io/trackma/images/screen_qt.png)

GTK interface

![GTK](https://z411.github.io/trackma/images/screen_gtk.png)

Curses interface

![Curses](https://z411.github.io/trackma/images/screen_curses.png)

CLI

![CLI](https://z411.github.io/trackma/images/screen_cli.png)

Requirements
------------

- Python 2.6/2.7
- lsof - for the media player detection tracker.
- (Optional) PyQt - for the Qt Interface
- (Optional) PyGTK (python-gtk2) - for the GTK interface.
- (Optional) Urwid (python-urwid) - for the curses/urwid interface.
- (Optional/Recommended) PIL (python-imaging) - for showing preview images in the Qt/GTK interfaces.

Installation
------------

Like any Python program, run the setup.py installation script:

<pre># python setup.py install</pre>

Then you can run the program with the interface you like.

<pre>
$ trackma
$ trackma-curses (requires urwid)
$ trackma-gtk (requires pygtk)
$ trackma-qt (requires PyQt)
</pre>

Alternatively, you can just run the scripts directly from the bin/ folder.

Configuration
-------------

A configuration file will be created in `~/.trackma/config.json`, make sure to fill in the directory
where you store your video files and other settings. Details about what each option does can be done here:

https://github.com/z411/trackma/wiki/Configuration-File

Alternatively, the GTK and Qt interfaces provide a visual Settings panel.

Development
-----------

The code is hosted as a git repository in github:

https://github.com/z411/trackma

If you encounter any problems or have anything to suggest, please don't
hesitate to submit an issue in the github issue tracker:

https://github.com/z411/trackma/issues

License
-------
Trackma is licensed under the GPLv3 license, please see LICENSE for details.

Authors
-------
Trackma was written by z411 <z411@krutt.org>
GTK icon designed by shuuichi
