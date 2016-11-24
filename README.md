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
- Secure, uses HTTPS wherever possible.

Currently supported websites
----------------------------
- [Anilist](https://anilist.co/) (Anime, Manga)
- [Hummingbird](https://hummingbird.me/) (Anime)
- [Melative](http://melative.com/) (Partial; Anime, Manga, VNs, LNs)
- [MyAnimeList](https://myanimelist.net/) (Anime, Manga)
- [Shikimori](http://shikimori.org/) (Anime, Manga)
- [VNDB](https://vndb.org/) (VNs)

Screenshots
-----------

Qt interface

![Qt](https://z411.github.io/trackma/images/screen_qt.png)

GTK interface

![GTK](http://z411.github.com/trackma/images/screen_gtk.png)

Curses interface

![Curses](http://z411.github.com/trackma/images/screen_curses.png)

CLI

![CLI](http://z411.github.com/trackma/images/screen_cli.png)

Documentation
-------------

The documentation for Trackma is [available on ReadTheDocs](http://trackma.readthedocs.org).

Requirements
------------

- Python 3.4/3.5
- lsof - for the media player detection tracker.
- (Optional) inotifyx - for instant media recognition (Linux only)
- (Optional) PyQt - for the Qt Interface
- (Optional) PyGI (python3-gi and python3-cairo) - for the GTK interface.
- (Optional) Urwid (python3-urwid) - for the curses/urwid interface.
- (Optional/Recommended) PIL (python3-pil) - for showing preview images in the Qt/GTK interfaces.
- python3-pip (to install through pip) *or* python3-setuptools (to install through setup.py)

Installation
------------

Make sure you've installed the proper dependencies (listed above)
according to the user interface you plan to use, and then run the
following command:

<pre># pip3 install Trackma</pre>

Or download the source code and install:

<pre># git clone https://github.com/z411/trackma.git
# cd trackma
# sudo python3 setup.py install</pre>

Then you can run the program with the interface you like.

<pre>
$ trackma
$ trackma-curses
$ trackma-gtk
$ trackma-qt
</pre>

Trackma also has user-provided packages for Arch Linux, Gentoo Linux and OpenSUSE.

- **Arch Linux:** http://aur.archlinux.org/packages/trackma-git
- **Fedora:** https://copr.fedoraproject.org/coprs/dyskette/trackma/
- **Gentoo Linux:** http://gpo.zugaina.org/net-misc/trackma
- **OpenSUSE:** http://download.opensuse.org/repositories/home:/Rethil/

Configuration
-------------

A configuration file will be created in `~/.trackma/config.json`, make sure to fill in the directory
where you store your video files and other settings. Details about what each option does can be done here:

https://github.com/z411/trackma/wiki/Configuration-File

Alternatively, the GTK and Qt interfaces provide a visual Settings panel.

Development
-----------

The code is hosted as a git repository in github:

http://github.com/z411/trackma

If you plan to make changes to the code, I suggest using the following method to install Trackma
instead of the normal way, so the changes you make get reflected immediately:

<pre># python3 setup.py develop</pre>

If you encounter any problems or have anything to suggest, please don't
hesitate to submit an issue in the github issue tracker:

http://github.com/z411/trackma/issues

License
-------
Trackma is licensed under the GPLv3 license, please see LICENSE for details.

Authors
-------
Trackma was originally written by z411 <z411@krutt.org>
For other authors see AUTHORS file
GTK icon designed by shuuichi
