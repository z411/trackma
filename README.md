Trackma
=======

Trackma aims to be a lightweight and simple but feature-rich program for Unix based systems
for fetching, updating and using data from personal lists hosted in several media tracking websites.

Features
--------

- Manage local list and synchronize when necessary, useful when offline
- Manage multiple accounts on different media tracking sites
- Support for several media types (as supported by the site)
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

![GTK](https://z411.github.io/trackma/images/screen_gtk.png)

Curses interface

![Curses](https://z411.github.io/trackma/images/screen_curses.png)

CLI

![CLI](https://z411.github.io/trackma/images/screen_cli.png)

Dependencies
------------

The only required dependency to run Trackma is:

- Python 3.7+
- `python3-pip` (to install through `pip`) *or* `python3-poetry` (to install through `poetry`)

But only basic features will work (only CLI interface and no tracker). Everything else is optional.

The following user interfaces are available and their requirements are as follows:

| UI | Dependencies |
| --- | --- |
| Qt | PyQt5 (`python-pyqt5`) |
| GTK 3 | PyGI (`python3-gi` and `python3-cairo`) |
| curses | Urwid (`python3-urwid`) |
| CLI | None |

The following media recognition trackers are available and their requirements are as follows:

| Tracker | Description | Dependencies |
| --- | --- | --- |
| inotify | Instant, but only supported in Linux. Uses it whenever possible. | `inotify` *or* `pyinotify` |
| Polling | Slow, but supported in every POSIX platform. Fallback. | `lsof` |
| Plex | Connects to Plex server. Enabled manually. | None |
| Kodi | Connects to Kodi server. Enabled manually. | None |
| Jellyfin | Connects to Jellyfin server. Enabled manually. | None |
| MPRIS | Connects to running MPRIS capable media players. | `dbus-python` |
| Win32 | Recognition for Windows platforms. | None |

Additional optional dependencies:

- PIL (`python3-pil`) - for showing preview images in the Qt/GTK interfaces.

Installation
------------

Trackma has user-provided packages for several distributions.

- **Arch Linux:** <https://aur.archlinux.org/packages/trackma>, <http://aur.archlinux.org/packages/trackma-git>
- **Fedora:** <https://copr.fedoraproject.org/coprs/dyskette/trackma/>
- **Gentoo Linux:** <http://gpo.zugaina.org/net-misc/trackma>
- **NixOS:** <https://github.com/NixOS/nixpkgs/blob/master/pkgs/tools/misc/trackma/default.nix>
- **Void Linux:** <https://github.com/void-linux/void-packages/blob/master/srcpkgs/trackma/template>

A user from the community also is providing a Docker image:

- **Docker:** <https://hub.docker.com/r/frosty5689/trackma/>

### Manual installation

Make sure you've installed the proper dependencies (listed above)
according to the user interface you plan to use, and then run the
following command:

```sh
$ pip3 install Trackma
```

You can also install the git (probably unstable, but newer) version like this:

```sh
$ pip3 install -U git+https://github.com/z411/trackma.git
```

Or download the source code and install:

```sh
$ git clone --recursive https://github.com/z411/trackma.git
$ cd trackma
$ poetry build
$ pip3 install dist/trackma-0.8.5-py3-none-any.whl
```

### Extras (User Interfaces)

All user interfaces except for the default CLI mode require additional dependencies to function.
You may specify these as "extras" to be installed by the Python package manager.

The following extras are available:

| Extra | Description |
| --- | --- |
| `gtk` | The GTK interface. |
| `qt` | The Qt interface. |
| `curses` | The curses-based TUI. |
| `ui` | All user interfaces. |
| `trackers` | All tracker libraries. |
| `discord_rpc` | Set your watching activity in Discord. |
| `twitter` | Announce your watching activity on Twitter. |

If you want to install any of the extras be sure to specify them during installation:

#### pip

```sh
# With pip
$ pip3 install Trackma[gtk,trackers,curses]
$ pip3 install Trackma[ui,twitter,discord_rpc]
```

Note that pip does not have a way to install all available extras,
so you'll have to provide them all manually if desired.

Then you can run the program with the interface you like.

```sh
$ trackma
$ trackma-curses
$ trackma-gtk
$ trackma-qt
```

#### poetry

When using poetry on the cloned repository (see above),
you can install your desired extras as follows:

```sh
$ poetry install -E gtk -E trackers -E curses
$ poetry install -E ui -E twitter -E discord_rpc
$ poetry install --all-extras
```

Then you can run the interface you like in your virtual environment managed by poetry:

```sh
$ poetry run trackma
$ poetry run trackma-curses
$ poetry run trackma-gtk
$ poetry run trackma-qt
```

Configuration
-------------

A configuration file will be created in `~/.config/trackma/config.json`, make sure to fill in the directory
where you store your video files and other settings. Details about what each option does can be done here:

<https://github.com/z411/trackma/wiki/Configuration-File>

Alternatively, the GTK and Qt interfaces provide a visual Settings panel.

Development
-----------

The code is hosted as a git repository on [GitHub](https://github.com/z411/trackma).

Clone the repo and create the virtual environment using `poetry`:

```sh
$ git clone --recursive https://github.com/z411/trackma.git
$ cd trackma
$ poetry install --all-extras
$ poetry shell
```

Use the above commands from the [poetry](#poetry) section
for how to run your desired interface.

If you encounter any problems or have anything to suggest, please don't
hesitate to submit an issue in the GitHub [issue tracker](https://github.com/z411/trackma/issues).

License
-------

Trackma is licensed under the GPLv3 license, please see [LICENSE](../COPYING) for details.

Authors
-------

Trackma was originally written by z411 <z411@omaera.org>. For other contributors see AUTHORS file. GTK icon designed by shuuichi.
