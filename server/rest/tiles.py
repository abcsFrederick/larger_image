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

import cherrypy

from girder.api import access, filter_logging
from girder.api.v1.item import Item as ItemResource
from girder.api.describe import describeRoute, Description
from girder.api.rest import filtermodel, loadmodel, setResponseHeader  # , setRawResponse
from girder.exceptions import RestException
from girder.models.model_base import AccessType
from girder.models.file import File

from girder.plugins.large_image import loadmodelcache
from girder.plugins.large_image.models import TileGeneralException
from girder.plugins.large_image.rest.tiles import ImageMimeTypes, \
    TilesItemResource, _adjustParams

try:
    from girder.plugins.colormaps.models.colormap import Colormap
except ImportError:
    Colormap = None

from ..models.larger_image_item import LargerImageItem


class TilesItemResource(TilesItemResource):
    def __init__(self, apiRoot):
        # Avoid redefining routes, call the Resource constructor
        super(ItemResource, self).__init__()

        apiRoot.item.route('POST', (':itemId', 'tiles', 'extended'),
                           self.createTiles)
        apiRoot.item.route('GET', (':itemId', 'tiles', 'extended', 'zxy', ':z', ':x', ':y'),
                           self.getTile)
        # apiRoot.item.route('POST', (':itemId', 'tiles', 'extended', 'zxy', ':z', ':x', ':y'),
        # self.saveTile)
        filter_logging.addLoggingFilter(
            'GET (/[^/ ?#]+)*/item/[^/ ?#]+/tiles/zxy(/[^/ ?#]+){3}',
            frequency=250)
        # Cache the model singleton
        self.imageItemModel = LargerImageItem()

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
        .param('tileSize', 'The tile Size of WSI.',
               dataType='int', default=256, required=False)
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
            return self.imageItemModel.createImageItem(
                item, largeImageFile, user, token,
                notify=self.boolParam('notify', params, default=True),
                quality=params.get('quality', 90), tileSize=params.get('tileSize', 256),
                compression=params.get('compression', 'jpeg').lower())
        except TileGeneralException as e:
            raise RestException(e.args[0])

    @describeRoute(
        Description('Get a large image tile.')
        .param('itemId', 'The ID of the item.', paramType='path')
        .param('z', 'The layer number of the tile (0 is the most zoomed-out '
               'layer).', paramType='path')
        .param('x', 'The X coordinate of the tile (0 is the left side).',
               paramType='path')
        .param('y', 'The Y coordinate of the tile (0 is the top).',
               paramType='path')
        .param('redirect', 'If the tile exists as a complete file, allow an '
               'HTTP redirect instead of returning the data directly.  The '
               'redirect might not have the correct mime type.  "exact" must '
               'match the image encoding and quality parameters, "encoding" '
               'must match the image encoding but disregards quality, and '
               '"any" will redirect to any image if possible.', required=False,
               enum=['false', 'exact', 'encoding', 'any'], default='false')
        .param('normalize', 'Normalize image intensity (single band only).',
               required=False, dataType='boolean', default=False)
        .param('normalizeMin', 'Minimum threshold intensity.',
               required=False, dataType='float')
        .param('normalizeMin', 'Maximum threshold intensity.',
               required=False, dataType='float')
        .param('label', 'Return a label image (single band only).',
               required=False, dataType='boolean', default=False)
        .param('invertLabel', 'Invert label values for transparency.',
               required=False, dataType='boolean', default=True)
        .param('flattenLabel', 'Ignore values for transparency.',
               required=False, dataType='boolean', default=False)
        .param('exclude', 'Label values to exclude.', required=False)
        .param('oneHot', 'Label values are one-hot encoded.',
               required=False, dataType='boolean', default=False)
        .param('bit', 'One-hot encoded bit.',
               required=False, dataType='int')
        .param('colormapId', 'ID of colormap to apply to image.',
               required=False)
        .produces(ImageMimeTypes)
        .errorResponse('ID was invalid.')
        .errorResponse('Read access was denied for the item.', 403)
        .errorResponse('Invalid colormap on server.', 500)
    )
    # Without caching, this checks for permissions every time.  By using the
    # LoadModelCache, three database lookups are avoided, which saves around
    # 6 ms in tests.
    #   @access.cookie   # access.cookie always looks up the token
    #   @access.public
    #   @loadmodel(model='item', map={'itemId': 'item'}, level=AccessType.READ)
    #   def getTile(self, item, z, x, y, params):
    #       return self._getTile(item, z, x, y, params, True)
    @access.cookie   # access.cookie always looks up the token
    @access.public
    def getTile(self, itemId, z, x, y, params):
        _adjustParams(params)
        item = loadmodelcache.loadModel(
            self, 'item', id=itemId, allowCookie=True, level=AccessType.READ)
        # Explicitly set a expires time to encourage browsers to cache this for
        # a while.
        setResponseHeader('Expires', cherrypy.lib.httputil.HTTPDate(
            cherrypy.serving.response.time + 600))
        redirect = params.get('redirect', False)
        if redirect not in ('any', 'exact', 'encoding'):
            redirect = False
        typeList = [
            ('normalize', bool),
            ('normalizeMin', float),
            ('normalizeMax', float),
            ('label', bool),
            ('invertLabel', bool),
            ('flattenLabel', bool),
            ('oneHot', bool),
            ('bit', int),
        ]
        params = self._parseParams(params, True, typeList)
        if 'exclude' in params:
            # TODO: error handling
            params['exclude'] = [int(s) for s in params['exclude'].split(',')]
        if Colormap and 'colormapId' in params:
            # colormap = Colormap().load(params['colormapId'],
            #                            force=True, exc=True)
            #                            user=self.getCurrentUser(),
            #                            level=AccessType.READ)
            colormap = Colormap().load(params['colormapId'],
                                       force=True, exc=True)
            del params['colormapId']
            if 'bit' in params:
                params['colormap'] = colormap['colormap']
            else:
                # TODO: abstract in colormap
                try:
                    params['colormap'] = bytearray(colormap['binary'])
                except (KeyError, TypeError):
                    raise RestException('Invalid colormap on server',
                                        code=500)
        return self._getTile(item, z, x, y, params, mayRedirect=redirect)

    # @describeRoute(
    #     Description('Get a large image tile.')
    #     .param('itemId', 'The ID of the item.', paramType='path')
    #     .param('z', 'The layer number of the tile (0 is the most zoomed-out '
    #            'layer).', paramType='path')
    #     .param('x', 'The X coordinate of the tile (0 is the left side).',
    #            paramType='path')
    #     .param('y', 'The Y coordinate of the tile (0 is the top).',
    #            paramType='path')
    #     .param('data', 'data need to be saved.',
    #            paramType='path')
    #     .param('redirect', 'If the tile exists as a complete file, allow an '
    #            'HTTP redirect instead of returning the data directly.  The '
    #            'redirect might not have the correct mime type.  "exact" must '
    #            'match the image encoding and quality parameters, "encoding" '
    #            'must match the image encoding but disregards quality, and '
    #            '"any" will redirect to any image if possible.', required=False,
    #            enum=['false', 'exact', 'encoding', 'any'], default='false')
    #     .produces(ImageMimeTypes)
    #     .errorResponse('ID was invalid.')
    #     .errorResponse('Read access was denied for the item.', 403)
    # )
    # @access.public
    # def saveTile(self, itemId, z, x, y, params):
    #     _adjustParams(params)
    #     item = loadmodelcache.loadModel(
    #         self, 'item', id=itemId, allowCookie=True, level=AccessType.READ)
    #     # Explicitly set a expires time to encourage browsers to cache this for
    #     # a while.
    #     setResponseHeader('Expires', cherrypy.lib.httputil.HTTPDate(
    #         cherrypy.serving.response.time + 600))
    #     redirect = params.get('redirect', False)
    #     if redirect not in ('any', 'exact', 'encoding'):
    #         redirect = False
    #     data = []
    #     return self._saveTile(item, z, x, y, data, params, mayRedirect=redirect)

    # def _saveTile(self, item, z, x, y, data, imageArgs, mayRedirect=False):
    #     """
    #     Get an large image tile.

    #     :param item: the item to get a tile from.
    #     :param z: tile layer number (0 is the most zoomed-out).
    #     .param x: the X coordinate of the tile (0 is the left side).
    #     .param y: the Y coordinate of the tile (0 is the top).
    #     :param imageArgs: additional arguments to use when fetching image data.
    #     :param mayRedirect: if True or one of 'any', 'encoding', or 'exact',
    #         allow return a response whcih may be a redirect.
    #     :return: a function that returns the raw image data.
    #     """
    #     try:
    #         x, y, z = int(x), int(y), int(z)
    #     except ValueError:
    #         raise RestException('x, y, and z must be integers', code=400)
    #     if x < 0 or y < 0 or z < 0:
    #         raise RestException('x, y, and z must be positive integers',
    #                             code=400)
    #     try:
    #         tileData, tileMime = self.imageItemModel.saveTile(
    #             item, x, y, z, data, mayRedirect=mayRedirect, **imageArgs)
    #     except TileGeneralException as e:
    #         raise RestException(e.args[0], code=404)
    #     setResponseHeader('Content-Type', tileMime)
    #     setRawResponse()
    #     return tileData
