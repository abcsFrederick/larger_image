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

from girder.api import access
from girder.api.v1.item import Item as ItemResource
from girder.api.describe import describeRoute, Description
from girder.api.rest import filtermodel, loadmodel
from girder.exceptions import RestException
from girder.models.model_base import AccessType
from girder.models.file import File

from girder.plugins.large_image.models import TileGeneralException
from girder.plugins.large_image.rest.tiles import ImageMimeTypes

from ..models.larger_image_item import LargerImageItem


class TilesItemResource(ItemResource):
    def __init__(self, apiRoot):
        # Avoid redefining routes, call the Resource constructor
        super(ItemResource, self).__init__()

        apiRoot.item.route('POST', (':itemId', 'tiles', 'extended'),
                           self.createTiles)
        # Cache the model singleton
        self.largerImageItemModel = LargerImageItem()

    @describeRoute(
        Description('Create a large image for this item.')
        .param('itemId', 'The ID of the item.', paramType='path')
        .param('fileId', 'The ID of the source file containing the image. '
                         'Required if there is more than one file in the item.',
               required=False)
        .param('notify', 'If a job is required to create the large image, '
               'a nofication can be sent when it is complete.',
               dataType='boolean', default=True, required=False)
        .param('quality', 'The quality of JPEG compression.',
               dataType='int', default=90, required=False)
        .param('compression', 'The image compression type.',
               required=False, default='JPEG',
               enum=['none', 'JPEG', 'Deflate', 'PackBits', 'LZW'])
    )
    @access.user
    @loadmodel(model='item', map={'itemId': 'item'}, level=AccessType.WRITE)
    @filtermodel(model='job', plugin='jobs')
    def createTiles(self, item, params):
        largeImageFileId = params.get('fileId')
        if largeImageFileId is None:
            files = list(File().find({
                'itemId': item['_id'],
                'mimeType': {'$in': ImageMimeTypes},
            }, limit=2))
            if len(files) == 1:
                largeImageFileId = str(files[0]['_id'])
        if not largeImageFileId:
            raise RestException('Missing "fileId" parameter.')
        largeImageFile = File().load(largeImageFileId, force=True, exc=True)
        user = self.getCurrentUser()
        token = self.getCurrentToken()
        try:
            return self.largerImageItemModel.createImageItem(
                item, largeImageFile, user, token,
                notify=self.boolParam('notify', params, default=True),
                quality=params.get('quality', 90),
                compression=params.get('compression', 'jpeg').lower())
        except TileGeneralException as e:
            raise RestException(e.args[0])
