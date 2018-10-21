#!/usr/bin/env python

from setuptools import setup, find_packages
from trackma import utils
import os
import subprocess

try:
    LONG_DESCRIPTION = open("README.rst").read()
except IOError:
    LONG_DESCRIPTION = __doc__

NAME = "Trackma"
REQUIREMENTS = []
EXTRA_REQUIREMENTS = {
    'curses': ['urwid'],
    'GTK': ['pygobject'],
    'Qt': [],
}


def create_mo_files():
    data_files = []
    localedir = 'locales'
    po_dirs = [localedir + '/' + l + '/LC_MESSAGES/'
               for l in next(os.walk(localedir))[1]]
    for d in po_dirs:
        mo_files = []
        po_files = [f
                    for f in next(os.walk(d))[2]
                    if os.path.splitext(f)[1] == '.po']
        for po_file in po_files:
            filename, extension = os.path.splitext(po_file)
            mo_file = filename + '.mo'
            msgfmt_cmd = 'msgfmt {} -o {}'.format(d + po_file, d + mo_file)
            subprocess.call(msgfmt_cmd, shell=True)
            mo_files.append(d + mo_file)
        data_files.append((d, mo_files))
    return data_files

setup(
    name=NAME,
    version=utils.VERSION,
    packages=find_packages(),

    install_requires=REQUIREMENTS,
    extras_require=EXTRA_REQUIREMENTS,
    package_data={'trackma': ['data/*']},

    author='z411',
    author_email='z411@krutt.org',
    description='Open multi-site list manager',
    long_description=LONG_DESCRIPTION,
    url='https://github.com/z411/trackma',
    keywords='list manager, curses, gtk, qt, myanimelist, hummingbird, vndb',
    license="GPL-3",
    entry_points={
        'console_scripts': [
            'trackma = trackma.ui.cli:main',
            'trackma-curses = trackma.ui.curses:main [curses]',
        ],
        'gui_scripts': [
            'trackma-gtk = trackma.ui.gtkui:main [GTK]',
            'trackma-qt = trackma.ui.qtui:main [Qt]',
            'trackma-qt4 = trackma.ui.qt4ui:main [Qt]',
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
    ],
    data_files = create_mo_files(),
    )
