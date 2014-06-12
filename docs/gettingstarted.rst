===============
Getting Started
===============

Pre-requisites
==============
To run wMAL you only need:

* Python >= 2.6
* lsof

To use any of the interfaces you need to install any of these depending on the interface you want to use:

* PyQT4 *(for the Qt interface)*
* PyGTK2 *(for the Gtk interface)*
* urwid *(for the curses interface)*

(lsof is optional if you plan to disable the media tracker)

Installation
============

Generic install
---------------

Installation is done by getting the dependencies, cloning the wMAL repository, navigating to the directory and running (as root) ``python setup.py install``.
Then you can run the interface you like by using its respective command ``wmal-qt``, ``wmal-gtk``, ``wmal-curses`` or ``wmal``.

For example, installing wMAL with its GTK interface on Debian-based systems like Ubuntu can be done by entering the following commands:

.. code-block:: bash

    sudo apt-get install git python python-gtk2 python-imaging
    git clone https://github.com/z411/wmal-python.git
    cd wmal-python
    sudo python2 setup.py install

Then, you can run wMAL's GTK interface by running:

.. code-block:: bash

    wmal-gtk
    
Arch Linux and Gentoo Linux users
---------------------------------

An Arch Linux package can be found at the AUR here: `wMAL @ AUR <https://aur.archlinux.org/packages/wmal-git>`_.

A Gentoo Linux ebuild can also be found at the booboo overlay: `wMAL @ booboo overlay <http://gpo.zugaina.org/net-misc/wmal-python>`_.

Configuration
=============
After installing, you'll want to immediately make sure that the options pointing to the name of your player  and the directory of video files are correct.

Currently the GTK interface provides an intuitive graphical way to edit wMAL's configuration.

.. TODO : Image here

If you don't want to use the GTK interface you can also edit the configuration file manually, described below.

Configuration file
==================
wMAL's configuration is stored in a JSON file in ``~/.wmal/config.json``. This file can be edited freely, but make sure wMAL is closed,
otherwise your options will get overwritten.

The configuration options are the following:

* ``auto_status_change``

  * Decides if the status of a show should be changed automatically whenever possible, i.e. when completed or when starting watching it. Depends on the API. 
  * Type: Boolean
  * Default value: ``true``

* ``autoretrieve``

  * Specifies list autoretrieval mode.
  * Possible values:

    * ``"off"``: No autoretrieve
    * ``"always"``: Retrieve at program start
    * ``"days"``: Retrieve after specified days
    
  * Default value: ``"off"``
  
* ``autoretrieve_days``

  * How many days to wait before autoretrieving. Only works if "autoretrieve" is set to "days"; ignored otherwise. 
  * Type: Integer
  * Default value: ``3``

* ``autosend``

  * Specified changes auto-send mode. 
  * Possible values:
  
    * ``"off"``: No autosend.
    * ``"always"``: Autosend after every change.
    * ``"hours"``: Autosend after specified hours.
    * ``"size"``: Autosend after queue reaches specified size.
  
  * Default value: ``"hours"``

* ``autosend_at_exit``

  * Specifies whether changes should be sent when exiting the program.
  * Type: Boolean
  * Default value: ``true``

* ``autosend_hours``

  * How many hours to wait before autosending. Only works if `"autosend"` is set to `"hours"`; ignored otherwise. 
  * Type: Integer
  * Default value: ``5``

* ``autosend_size``

  * Specifies the limit of the queue size; after this limit is reached, the changes will be autosent. Only works if `"autosend"` is set to `"size"`; ignored otherwise. 
  * Type: Integer
  * Default value: ``5``

* ``debug_disable_lock``

  * Specifies if the lock file check to see if the cache is currently open should be disabled. Currently set to true as default, as the feature in the present moment is unstable an annoying.
  * Type: Boolean
  * Default value: ``true``

* ``player``

  * Process name of the media player to launch to play an episode.
  * Type: String
  * Default value: ``"mpv"``

* ``searchdir``

  * Full path of the directory to search for video files when launching a media player (without trailing slash).
  * Type: String
  * Default value: ``"~/Videos"``

* ``tracker_enabled``

  * Specifies if the tracker should be used. Disable if you don't want the tracker and/or the lsof dependency.
  * Type: Boolean
  * Default value: ``true``

* ``tracker_interval``

  * Time **in seconds** for the tracker to re-check for a running player in the background. Decrease this value if you want wMAL to react quicker when you have a media player running.
  * Type: Integer
  * Default value: ``120``

* ``tracker_process``

  * Regex string to match the process name of a background running player for the tracker to detect it.
  * Type: String
  * Default value: ``"mplayer|mplayer2|mpv"``

* ``tracker_update_wait``

  * Time **in minutes** to wait before updating an episode when a player is running. If the player is closed before this time limit is reached, the episode won't be updated.
  * Type: Integer
  * Default value: ``5``
