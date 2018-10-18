#!/usr/bin/env python
# -*- coding: utf-8 -*-

###############################################################################
#  Girder, large_image plugin framework and tests adapted from Kitware Inc.
#  source and documentation by the Imaging and Visualization Group, Advanced
#  Biomedical Computational Science, Frederick National Laboratory for Cancer
#  Research.
#
#  Copyright Kitware Inc.
#
#  Licensed under the Apache License, Version 2.0 ( the "License" );
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
###############################################################################
import os.path
import tempfile

from tests import base


def setUpModule():
    base.enabledPlugins.append('larger_image')
    base.startServer()


def tearDownModule():
    base.stopServer()


class CreateTiffTest(base.TestCase):
    def testCreateTiff(self):
        in_path = os.path.join(os.path.dirname(__file__), 'test_files',
                               'grey10kx5kdeflate.tif')
        compression = 'none'
        quality = 90
        tile_size = 256
        out_path = os.path.join(tempfile.gettempdir(),
                                'grey10kx5kdeflate_tiled.tif')
        import girder.plugins.larger_image.create_tiff as create_tiff
        create_tiff.create_tiff(in_path, compression, quality, tile_size,
                                out_path)
