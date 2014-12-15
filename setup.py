#!/usr/bin/env python

from distutils.core import setup

setup(name='Trackma',
      version='0.3',
      description='Open multi-site list manager',
      author='z411',
      url='https://github.com/z411/trackma',
      packages=['trackma', 'trackma.lib', 'trackma.ui'],
      package_data={'trackma': ['data/*']},
      scripts=['bin/trackma', 'bin/trackma-curses', 'bin/trackma-gtk', 'bin/trackma-qt'],
      requires=[]
      )
