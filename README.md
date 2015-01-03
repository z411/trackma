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
- [MyAnimeList](http://myanimelist.net/) (Anime, Manga)
- [Hummingbird](http://hummingbird.me/) (Anime)
- [VNDB](https://vndb.org/) (VNs)
- [Melative](http://melative.com/) (Partial; Anime, Manga, VNs, LNs)

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

- Python 2.6/2.7
- lsof - for the media player detection tracker.
- (Optional) PyQt - for the Qt Interface
- (Optional) PyGTK (python-gtk2) - for the GTK interface.
- (Optional) Urwid (python-urwid) - for the curses/urwid interface.
- (Optional/Recommended) PIL (python-imaging) - for showing preview images in the Qt/GTK interfaces.

Installation
------------

Make sure you've installed the proper dependencies (listed above)
according to the user interface you plan to use, and then run the
following command:

<pre># pip install Trackma</pre>

Or if you've downloaded the source code:

<pre># python setup.py install</pre>

Then you can run the program with the interface you like.

<pre>
$ trackma
$ trackma-curses
$ trackma-gtk
$ trackma-qt
</pre>

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

<pre># python setup.py develop</pre>

If you encounter any problems or have anything to suggest, please don't
hesitate to submit an issue in the github issue tracker:

http://github.com/z411/trackma/issues

License
-------
Trackma is licensed under the GPLv3 license, please see LICENSE for details.

Authors
-------
Trackma was written by z411 <z411@krutt.org>
GTK icon designed by shuuichi
