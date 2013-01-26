wMAL
====

wMAL aims to be a lightweight and simple but feature-rich program for Unix based systems
for fetching, updating and using data from personal lists hosted in different
media tracking websites like MyAnimeList, Melative or VNDB.

Features
--------
- Manage local list and synchronize when necessary, useful when offline
- Manage multiple accounts on different sites like MyAnimeList, Melative or VNDB.
- Support for several mediatypes depending on the site (like VNs, anime, manga, LNs)
- Multiple user interfaces (GTK, curses, command-line)
- Detection of running media player, updates list if necessary
- Ability to launch media player for a requested media in the list and update list if necessary
- Highly scalable, easy to code new interfaces and support for other sites

Screenshots
-----------

GTK interface

![GTK](http://z411.github.com/wmal-python/images/screen_gtk.png)

Curses interface

![Curses](http://z411.github.com/wmal-python/images/screen_curses.png)

CLI

![CLI](http://z411.github.com/wmal-python/images/screen_cli.png)

Requirements
------------

- Tested with Python 2.7, but it should work in 2.6 too.
- (Optional) Urwid (python-urwid) for the curses/urwid interface.
- (Optional) PyGTK (python-gtk2) for the GTK interface.

Installation
------------

Like any Python program, run the setup.py installation script:

<pre># python setup.py install</pre>

Then you can run the program with the interface you like.

<pre>
$ wmal
$ wmal-curses (requires urwid)
$ wmal-gtk (requires pygtk)
</pre>

Alternatively, you can just run the scripts directly from the bin/ folder.

Development
-----------

The code is hosted as a git repository in github:

http://github.com/z411/wmal-python

If you encounter any problems or have anything to suggest, please don't
hesitate to submit an issue in the github issue tracker:

http://github.com/z411/wmal-python/issues

License
-------
wMAL is licensed under the GPLv3 license, please see LICENSE for details.

Authors
-------
wMAL was written by z411 <electrik.persona@gmail.com>
GTK icon designed by shuuichi
