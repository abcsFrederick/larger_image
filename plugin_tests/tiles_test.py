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
import time

import requests

from tests import base

from girder import config
from girder.constants import SortDir

import common

os.environ['GIRDER_PORT'] = os.environ.get('GIRDER_TEST_PORT', '20200')
config.loadConfig()


def setUpModule():
    base.enabledPlugins.append('larger_image')
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

    def _postTileViaHttp(self, itemId, fileId, jobAction=None):
        """
        When we know we need to process a job, we have to use an actual http
        request rather than the normal simulated request to cherrypy.  This is
        required because cherrypy needs to know how it was reached so that
        girder_worker can reach it when done.

        :param itemId: the id of the item with the file to process.
        :param fileId: the id of the file that should be processed.
        :param jobAction: if 'delete', delete the job immediately.
        :returns: metadata from the tile if the conversion was successful,
                  False if it converted but didn't result in useable tiles, and
                  None if it failed.
        """
        from girder.plugins.jobs.models.job import Job

        urlArgs = int(os.environ['GIRDER_PORT']), itemId
        url = 'http://127.0.0.1:%d/api/v1/item/%s/tiles/extended' % urlArgs
        headers = [('Accept', 'application/json')]
        self._buildHeaders(headers, None, self.admin, None, None, None)
        headers = {header[0]: header[1] for header in headers}
        req = requests.post(url, headers=headers, data={'fileId': fileId})
        self.assertEqual(req.status_code, 200)
        # If we ask to create the item again right away, we should be told that
        # either there is already a job running or the item has already been
        # added
        req = requests.post(url, headers=headers, data={'fileId': fileId})
        self.assertEqual(req.status_code, 400)
        self.assertTrue('Item already has' in req.json()['message'] or
                        'Item is scheduled' in req.json()['message'])

        if jobAction == 'delete':
            Job().remove(Job().find({}, sort=[('_id', SortDir.DESCENDING)])[0])

        starttime = time.time()
        resp = None
        while time.time() - starttime < 30:
            try:
                resp = self.request(path='/item/%s/tiles' % itemId,
                                    user=self.admin)
                self.assertStatusOk(resp)
                break
            except AssertionError as exc:
                if 'didn\'t meet requirements' in exc.args[0]:
                    return False
                if 'No large image file' in exc.args[0]:
                    return None
                self.assertIn('is still pending creation', exc.args[0])
            time.sleep(0.1)
        self.assertStatusOk(resp)
        return resp.json
