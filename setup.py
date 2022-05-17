#!/usr/bin/env python
# Always prefer setuptools over distutils

import sys
from setuptools import setup, find_packages

DS = 'VacuumController'
author = 'srubio@cells.es',
description = '%s Tango Device Server'%DS
version = open(DS+'/VERSION').read().strip()
license = 'GPL-3.0'

__doc__ = """
Generic Device Server setup.py file copied from fandango/scripts/setup.ds.py

To install as system package:

  python setup.py install
  
To build src package:

  python setup.py sdist
  
To install as local package, just run:

  mkdir /tmp/builds/
  python setup.py install --root=/tmp/builds
  /tmp/builds/usr/bin/$DS -? -v4

To tune some options:

  RU=/opt/control
  python setup.py egg_info --egg-base=tmp install --root=$RU/files --no-compile \
    --install-lib=lib/python/site-packages --install-scripts=ds

-------------------------------------------------------------------------------
"""

## All the following defines are OPTIONAL
install_requires = ['fandango','PyTango',]

## For setup.py located in root folder or submodules
package_dir = {
#    DS: DS,    #'DS/tools': './tools',
}
packages = package_dir.keys() or find_packages()

## Additional files, remember to edit MANIFEST.in to include them in sdist
package_data = {'': [
  DS+'/VERSION',
  #'./tools/icon/*',
  #'./tools/*ui',
]}

## Launcher scripts
scripts = [
  './bin/'+DS,
  #'./scripts/VacuumController',
  #'./scripts/VacuumGauge',
  #'./scripts/IonPump',
  ]

## This option relays on DS.py having a main() method
entry_points = {
#        'console_scripts': [
#            '%s = %s.%s:main'%(DS,DS,DS),
#        ],
}


setup(
    name = 'tangods-'+DS.lower(),
    description = description,
    author = author,
    author_email = author,
    url = 'https://git.cells.es/controls/'+DS,
    license = license,
    version = version,
    
    install_requires = install_requires,    
    packages = packages,
    package_dir = package_dir,
    entry_points = entry_points,    
    scripts = scripts,
    include_package_data = True,
    package_data = package_data,
)
