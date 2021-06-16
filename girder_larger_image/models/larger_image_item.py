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
import time

from girder_jobs.models.job import Job
from large_image.exceptions import TileGeneralException
from girder_large_image.models.image_item import ImageItem
from girder_worker.girder_plugin import utils as workerUtils

from ..tilesource import AvailableTileSources, TileSourceException


class LargerImageItem(ImageItem):
    def createImageItem(self, item, fileObj, user=None, token=None,
                        createJob=True, notify=False, **kwargs):
        # Using setdefault ensures that 'largeImage' is in the item
        if 'fileId' in item.setdefault('largeImage', {}):
            # TODO: automatically delete the existing large file
            raise TileGeneralException('Item already has a largeImage set.')
        if fileObj['itemId'] != item['_id']:
            raise TileGeneralException('The provided file must be in the '
                                       'provided item.')
        if (item['largeImage'].get('expected') is True and
                'jobId' in item['largeImage']):
            raise TileGeneralException('Item is scheduled to generate a '
                                       'largeImage.')

        item['largeImage'].pop('expected', None)
        item['largeImage'].pop('sourceName', None)

        item['largeImage']['fileId'] = fileObj['_id']
        job = None
        for sourceName in AvailableTileSources:
            if getattr(AvailableTileSources[sourceName], 'girderSource',
                       False):
                if AvailableTileSources[sourceName].canRead(item):
                    item['largeImage']['sourceName'] = sourceName
                    break
        if 'sourceName' not in item['largeImage'] and not createJob:
            raise TileGeneralException(
                'A job must be used to generate a largeImage.')
        if 'sourceName' not in item['largeImage']:
            # No source was successful
            del item['largeImage']['fileId']
            job = self._createLargeImageJob(item, fileObj, user, token,
                                            **kwargs)
            item['largeImage']['expected'] = True
            item['largeImage']['notify'] = notify
            item['largeImage']['originalId'] = fileObj['_id']
            item['largeImage']['jobId'] = job['_id']

        self.save(item)
        return job

    def _createLargeImageJob(self, item, fileObj, user, token, **kwargs):
        import large_image_tasks.tasks
        from girder_worker_utils.transforms.girder_io import GirderUploadToItem
        from girder_worker_utils.transforms.contrib.girder_io import GirderFileIdAllowDirect
        from girder_worker_utils.transforms.common import TemporaryDirectory

        try:
            localPath = File().getLocalFilePath(fileObj)
        except (FilePathException, AttributeError):
            localPath = None
        job = large_image_tasks.tasks.create_tiff.apply_async(kwargs=dict(
            girder_job_title='TIFF Conversion: %s' % fileObj['name'],
            girder_job_other_fields={'meta': {
                'creator': 'large_image',
                'itemId': str(item['_id']),
                'task': 'createImageItem',
            }},
            inputFile=GirderFileIdAllowDirect(str(fileObj['_id']), fileObj['name'], localPath),
            inputName=fileObj['name'],
            outputDir=TemporaryDirectory(),
            girder_result_hooks=[
                GirderUploadToItem(str(item['_id']), False),
            ],
            **kwargs,
        ), countdown=int(kwargs['countdown']) if kwargs.get('countdown') else None)
        return job.job

        
        # path = os.path.join(os.path.dirname(__file__), '..', 'create_tiff.py')
        # with open(path, 'r') as f:
        #     script = f.read()

        # title = 'TIFF conversion: %s' % fileObj['name']
        # job = Job().createJob(
        #     title=title, type='large_image_tiff', handler='worker_handler',
        #     user=user)
        # jobToken = Job().createJobToken(job)

        # outputName = os.path.splitext(fileObj['name'])[0] + '.tiff'
        # if outputName == fileObj['name']:
        #     outputName = (os.path.splitext(fileObj['name'])[0] + '.' +
        #                   time.strftime('%Y%m%d-%H%M%S') + '.tiff')

        # task = {
        #     'mode': 'python',
        #     'script': script,
        #     'name': title,
        #     'inputs': [{
        #         'id': 'in_path',
        #         'target': 'filepath',
        #         'type': 'string',
        #         'format': 'text'
        #     }, {
        #         'id': 'out_filename',
        #         'type': 'string',
        #         'format': 'text'
        #     }, {
        #         'id': 'tile_size',
        #         'type': 'number',
        #         'format': 'number'
        #     }, {
        #         'id': 'quality',
        #         'type': 'number',
        #         'format': 'number'
        #     }, {
        #         'id': 'compression',
        #         'type': 'string',
        #         'format': 'text'
        #     }],
        #     'outputs': [{
        #         'id': 'out_path',
        #         'target': 'filepath',
        #         'type': 'string',
        #         'format': 'text'
        #     }]
        # }

        # inputs = {
        #     'in_path': workerUtils.girderInputSpec(
        #         fileObj, resourceType='file', token=token),
        #     'compression': {
        #         'mode': 'inline',
        #         'type': 'string',
        #         'format': 'text',
        #         'data': compression
        #     },
        #     'quality': {
        #         'mode': 'inline',
        #         'type': 'number',
        #         'format': 'number',
        #         'data': quality
        #     },
        #     'tile_size': {
        #         'mode': 'inline',
        #         'type': 'number',
        #         'format': 'number',
        #         'data': tileSize
        #     },
        #     'out_filename': {
        #         'mode': 'inline',
        #         'type': 'string',
        #         'format': 'text',
        #         'data': outputName
        #     }
        # }

        # outputs = {
        #     'out_path': workerUtils.girderOutputSpec(
        #         parent=item, token=token, parentType='item')
        # }

        # # TODO: Give the job an owner
        # job['kwargs'] = {
        #     'task': task,
        #     'inputs': inputs,
        #     'outputs': outputs,
        #     'jobInfo': workerUtils.jobInfoSpec(job, jobToken),
        #     'auto_convert': False,
        #     'validate': False
        # }
        # job['meta'] = {
        #     'creator': 'large_image',
        #     'itemId': str(item['_id']),
        #     'task': 'createImageItem',
        # }

        # job = Job().save(job)
        # Job().scheduleJob(job)

        # return job

    @classmethod
    def _loadTileSource(cls, item, **kwargs):
        if 'largeImage' not in item:
            raise TileSourceException('No large image file in this item.')
        if item['largeImage'].get('expected'):
            raise TileSourceException('The large image file for this item is '
                                      'still pending creation.')

        sourceName = item['largeImage']['sourceName']
        tileSource = AvailableTileSources[sourceName](item, **kwargs)
        return tileSource

    def getTile(self, item, x, y, z, mayRedirect=False, **kwargs):
        tileSource = self._loadTileSource(item, **kwargs)
        tileData = tileSource.getTile(x, y, z, mayRedirect=mayRedirect,
                                      **kwargs)
        tileMimeType = tileSource.getTileMimeType()
        return tileData, tileMimeType

    # def saveTile(self, item, x, y, z, data, mayRedirect=False, **kwargs):
    #     tileSource = self._loadTileSource(item, **kwargs)
    #     tileData = tileSource.saveTile(x, y, z, data, mayRedirect=mayRedirect)
    #     tileMimeType = tileSource.getTileMimeType()
    #     return tileData, tileMimeType
    