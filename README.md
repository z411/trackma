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
- [Kitsu](https://kitsu.io/) (Anime, Manga, Drama)
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

Dependencies
------------

The only required dependency to run Trackma is:

- Python 3.4/3.5
- python3-pip (to install through pip) *or* python3-setuptools (to install through setup.py)

But only basic features will work (only CLI interface and no tracker). Everything else is optional.

The following user interfaces are available and their requirements are as follows:

| UI | Dependencies |
| --- | --- |
| Qt | PyQt5 (python-pyqt5) *or* PyQt4 (python-qt4) |
| GTK 3 | PyGI (python3-gi and python3-cairo) |
| curses | Urwid (python3-urwid) |
| CLI | None |

The following media recognition trackers are available and their requirements are as follows:

| Tracker | Description | Dependencies |
| --- | --- | --- |
| inotify | Instant, but only supported in Linux. Uses it whenever possible. | inotify *or* pyinotify |
| Polling | Slow, but supported in every POSIX platform. Fallback. | lsof |
| Plex | Connects to Plex server. Enabled manually. | None |
| MPRIS | Connects to running MPRIS capable media players. | dbus-python |
| Win32 | Recognition for Windows platforms. | None |

Additional optional dependencies:

- PIL (python3-pil) - for showing preview images in the Qt/GTK interfaces.

Installation
------------

Make sure you've installed the proper dependencies (listed above)
according to the user interface you plan to use, and then run the
following command:

<pre># pip3 install Trackma</pre>

Or download the source code and install:

<pre># git clone --recursive https://github.com/z411/trackma.git
# cd trackma
# sudo python3 setup.py install</pre>

Then you can run the program with the interface you like.

<pre>
$ trackma
$ trackma-curses
$ trackma-gtk
$ trackma-qt
</pre>

Trackma also has user-provided packages for several distributions.

- **Arch Linux:** http://aur.archlinux.org/packages/trackma-git
- **Fedora:** https://copr.fedoraproject.org/coprs/dyskette/trackma/
- **Gentoo Linux:** http://gpo.zugaina.org/net-misc/trackma
- **OpenSUSE:** http://download.opensuse.org/repositories/home:/Rethil/
- **Void Linux:** https://github.com/voidlinux/void-packages/blob/master/srcpkgs/trackma/template

A user from the community also is providing a Docker image:

- **Docker:** https://hub.docker.com/r/frosty5689/trackma/

Configuration
-------------

A configuration file will be created in `~/.config/trackma/config.json`, make sure to fill in the directory
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
Trackma was originally written by z411 <z411@omaera.org>. For other contributors see AUTHORS file. GTK icon designed by shuuichi.
