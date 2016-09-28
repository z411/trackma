========
Overview
========

Features
========

* Manage local list and synchronize when necessary, useful when offline
* Manage multiple accounts on different sites like MyAnimeList, Melative, Hummingbird or VNDB.
* Support for several mediatypes depending on the site (like VNs, anime, manga, LNs)
* Multiple user interfaces (Qt, GTK, curses, command-line)
* Detection of running media player, updates list if necessary
* Ability to launch media player for a requested media in the list and update list if necessary
* Highly scalable, easy to code new interfaces and support for other sites

Interfaces
==========

As mentioned, Trackma provides different interfaces to fit your environment better.

`trackma-qt` -- Qt Interface
----------------------------
The Qt interface is coded using PyQt4, and it provides a simple and intuitive interface for Qt users.
Porting to PyQt5 is planned.

.. image:: ./images/qt.png

`trackma-gtk` -- GTK Interface
------------------------------
The GTK interface is coded using Python-GI, and it provides a feature complete interface for GTK users.
Currently it uses GTK 3.

.. image:: ./images/gtk.png

`trackma-curses` - curses Interface
-----------------------------------
The curses interface is coded using the urwid library, and it provides an intuitive terminal based interface
with the same functionality as the previously mentioned GUIs.

.. image:: ./images/curses.png

`trackma` -- CLI
----------------
The command-line interface is a simple command based interface to Trackma, mostly used for development and debugging,
but it can also be used if you really don't want to install any dependencies.

.. image:: ./images/cli.png
