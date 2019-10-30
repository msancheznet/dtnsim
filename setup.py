# ========================================================================================
# DtnSim: setup.py
#   
# Author:   Marc Sanchez Net
# Date:     10/30/2019
#
# License Terms
# -------------
#
# Copyright (c) 2019, California Institute of Technology ("Caltech").  
# U.S. Government sponsorship acknowledged.
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, 
# are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, 
#   this list of conditions and the following disclaimer.
# * Redistributions must reproduce the above copyright notice, this list 
#   of conditions and the following disclaimer in the documentation and/or other 
#   materials provided with the distribution.
# * Neither the name of Caltech nor its operating division, the Jet Propulsion Laboratory, 
#   nor the names of its contributors may be used to endorse or promote products 
#   derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND 
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED 
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. 
# IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, 
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, 
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, 
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) 
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY 
# OF SUCH DAMAGE.
# ========================================================================================

# Generic imports
from pathlib import Path
from setuptools import setup

# Package imports
from bin.main import __version__, __release__

# ========================================================================================
# === Prepare for setup
# ========================================================================================

from simulator import *

# The text of the README file
README = (Path(__file__).parent / "README.md").read_text()

# ========================================================================================
# === Main setup
# ========================================================================================

setup(
    name             = 'dsnsim',
    version          = __version__,
    release          = __release__,
    description      = 'Python-based DTN simulator',
    long_description = README,
    author           = 'Marc Sanchez Net',
    author_email     = 'marc.sanchez.net@jpl.nasa.gov',
    license          = 'Apache 2.0',
    url              = 'https://github.com/msancheznet/dtnsim',
    python_requires  = '>=3.6.0',
    setup_requires   = [],                  # See conda_environment.yaml for dependencies
    install_requires = ['setuptools'],      # See conda_environment.yaml for dependencies
    extras_require   = {
                'test': [],
                'docs': ['sphinx', 'sphinx_bootstrap_theme'],
            },
    entry_points     = {
                'sphinx.html_themes': [
                    'bootstrap = sphinx_bootstrap_theme',
                ]
    },
    packages         = ["simulator"],
)