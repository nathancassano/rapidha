# -*- coding: utf-8 -*-
from setuptools import setup
from os import path

with open(path.join(path.abspath(path.dirname(__file__)), 'README.md')) as f:
  long_description = f.read()

setup(
   name='RapidHA',
   version='1.0',
   description='Python module for RapidHA serial device communication',
   long_description=long_description,
   license="Apache 2",
   author='Nathan Cassano',
   packages=['rapidha'],
   scripts=['bin/rapidha'],
   install_requires=['serial', 'xbee'],
   classifiers=[
     'Development Status :: 5 - Production/Stable',
     'Environment :: Console',
     'Programming Language :: Python',
     'License :: OSI Approved :: Apache Software License',
     'Topic :: System :: Networking',
     'Topic :: Software Development :: Embedded Systems',
     'Topic :: System :: Hardware :: Hardware Drivers'
   ],
   url='https://github.com/nathancassano/rapidha'
)
