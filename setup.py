#!/usr/bin/env python3

from setuptools import find_packages, setup

from trackma import utils

try:
    LONG_DESCRIPTION = open("README.md").read()
except IOError:
    LONG_DESCRIPTION = __doc__

NAME = "Trackma"
REQUIREMENTS = []
EXTRA_REQUIREMENTS = {
    'curses': ['urwid'],
    'GTK': ['pygobject'],
    'Qt': [],
}

setup(
    name=NAME,
    version=utils.VERSION,
    packages=find_packages(),

    install_requires=REQUIREMENTS,
    extras_require=EXTRA_REQUIREMENTS,
    package_data={'trackma': ['data/*', 'data/anime-relations/*.txt', 'ui/gtk/data/*']},

    author='z411',
    author_email='z411@krutt.org',
    description='Open multi-site list manager',
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    url='https://github.com/z411/trackma',
    keywords='list manager, curses, gtk, qt, myanimelist, hummingbird, vndb',
    license="GPL-3",
    entry_points={
        'console_scripts': [
            'trackma = trackma.ui.cli:main',
            'trackma-curses = trackma.ui.curses:main [curses]',
        ],
        'gui_scripts': [
            'trackma-gtk = trackma.ui.gtk:main [GTK]',
            'trackma-qt = trackma.ui.qt:main [Qt]',
            'trackma-qt4 = trackma.ui.qt.qt4:main [Qt4]',
        ]
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: End Users/Desktop',
        'Topic :: Internet',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Operating System :: POSIX',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
    ]
    )
