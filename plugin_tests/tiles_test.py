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

import os

from girder import config
from tests import base

import common

os.environ['GIRDER_PORT'] = os.environ.get('GIRDER_TEST_PORT', '20200')
config.loadConfig()


def setUpModule():
    base.enabledPlugins.append('large_image')
    base.startServer(False)


def tearDownModule():
    base.stopServer()


class LargeImageTilesTest(common.LargeImageCommonTest):
    def testTilesFromGreyscale(self):
        file = self._uploadFile(os.path.join('plugins', 'large_image',
                                             'plugin_tests', 'test_files',
                                             'grey10kx5k.tif'))
        itemId = str(file['itemId'])
        fileId = str(file['_id'])
        # FIXME: route
        tileMetadata = self._postTileViaHttp(itemId, fileId)
        self.assertEqual(tileMetadata['tileWidth'], 256)
        self.assertEqual(tileMetadata['tileHeight'], 256)
        self.assertEqual(tileMetadata['sizeX'], 10000)
        self.assertEqual(tileMetadata['sizeY'], 5000)
        self.assertEqual(tileMetadata['levels'], 7)
        self.assertEqual(tileMetadata['magnification'], None)
        self.assertEqual(tileMetadata['mm_x'], None)
        self.assertEqual(tileMetadata['mm_y'], None)
        self._testTilesZXY(itemId, tileMetadata)
