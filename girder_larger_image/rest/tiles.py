#!/usr/bin/env python
# -*- coding: utf-8 -*-
import cherrypy
import pathlib

from girder.api import access, filter_logging
from girder.api.v1.item import Item as ItemResource
from girder.api.describe import describeRoute, Description
from girder.api.rest import filtermodel, loadmodel, setResponseHeader, setRawResponse
from girder.exceptions import RestException
from girder.models.model_base import AccessType
from girder.models.file import File
from girder.utility.progress import setResponseTimeLimit

from girder_large_image import loadmodelcache
from girder_large_image.rest.tiles import ImageMimeTypes, \
    TilesItemResource, _adjustParams, _handleETag
from large_image.exceptions import TileGeneralException

try:
    from girder_colormaps.models.colormap import Colormap
except ImportError:
    Colormap = None

from ..models.larger_image_item import LargerImageItem


from large_image.constants import TileInputUnits



class TilesItemResource(TilesItemResource):
    def __init__(self, apiRoot):
        # Avoid redefining routes, call the Resource constructor
        # super(ItemResource, self).__init__()
        super().__init__(apiRoot)
        apiRoot.item.route('POST', (':itemId', 'tiles', 'extended'),
                           self.createTiles)
        apiRoot.item.route('GET', (':itemId', 'tiles', 'extended', 'zxy', ':z', ':x', ':y'),
                           self.getTile)
        # remove and replace original get region route
        apiRoot.item.removeRoute('GET', (':itemId', 'tiles', 'region'))
        apiRoot.item.route('GET', (':itemId', 'tiles', 'extended', 'region'),
                           self.getTilesRegion)
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
               dataType='int', default=100, required=False)
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
    @access.public(cookie=True) # access.cookie always looks up the token
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

    @describeRoute(
        Description('Get any region of a large image item, optionally scaling '
                    'it.')
        .notes('If neither width nor height is specified, the full resolution '
               'region is returned.  If a width or height is specified, '
               'aspect ratio is always preserved (if both are given, the '
               'resulting image may be smaller in one of the two '
               'dimensions).  When scaling must be applied, the image is '
               'downsampled from a higher resolution layer, never upsampled.')
        .param('itemId', 'The ID of the item.', paramType='path')
        .param('left', 'The left column (0-based) of the region to process.  '
               'Negative values are offsets from the right edge.',
               required=False, dataType='float')
        .param('top', 'The top row (0-based) of the region to process.  '
               'Negative values are offsets from the bottom edge.',
               required=False, dataType='float')
        .param('right', 'The right column (0-based from the left) of the '
               'region to process.  The region will not include this column.  '
               'Negative values are offsets from the right edge.',
               required=False, dataType='float')
        .param('bottom', 'The bottom row (0-based from the top) of the region '
               'to process.  The region will not include this row.  Negative '
               'values are offsets from the bottom edge.',
               required=False, dataType='float')
        .param('regionWidth', 'The width of the region to process.',
               required=False, dataType='float')
        .param('regionHeight', 'The height of the region to process.',
               required=False, dataType='float')
        .param('units', 'Units used for left, top, right, bottom, '
               'regionWidth, and regionHeight.  base_pixels are pixels at the '
               'maximum resolution, pixels and mm are at the specified '
               'magnfication, fraction is a scale of [0-1].', required=False,
               enum=sorted(set(TileInputUnits.values())),
               default='base_pixels')
        .param('width', 'The maximum width of the output image in pixels.',
               required=False, dataType='int')
        .param('height', 'The maximum height of the output image in pixels.',
               required=False, dataType='int')
        .param('fill', 'A fill color.  If output dimensions are specified and '
               'fill is specified and not "none", the output image is padded '
               'on either the sides or the top and bottom to the requested '
               'output size.  Most css colors are accepted.', required=False)
        .param('magnification', 'Magnification of the output image.  If '
               'neither width for height is specified, the magnification, '
               'mm_x, and mm_y parameters are used to select the output size.',
               required=False, dataType='float')
        .param('mm_x', 'The size of the output pixels in millimeters',
               required=False, dataType='float')
        .param('mm_y', 'The size of the output pixels in millimeters',
               required=False, dataType='float')
        .param('exact', 'If magnification, mm_x, or mm_y are specified, they '
               'must match an existing level of the image exactly.',
               required=False, dataType='boolean', default=False)
        .param('frame', 'For multiframe images, the 0-based frame number.  '
               'This is ignored on non-multiframe images.', required=False,
               dataType='int')
        .param('encoding', 'Output image encoding.  TILED generates a tiled '
               'tiff without the upper limit on image size the other options '
               'have.  For geospatial sources, TILED will also have '
               'appropriate tagging.', required=False,
               enum=['JPEG', 'PNG', 'TIFF', 'TILED'], default='JPEG')
        .param('jpegQuality', 'Quality used for generating JPEG images',
               required=False, dataType='int', default=95)
        .param('jpegSubsampling', 'Chroma subsampling used for generating '
               'JPEG images.  0, 1, and 2 are full, half, and quarter '
               'resolution chroma respectively.', required=False,
               enum=['0', '1', '2'], dataType='int', default='0')
        .param('tiffCompression', 'Compression method when storing a TIFF '
               'image', required=False,
               enum=['none', 'raw', 'lzw', 'tiff_lzw', 'jpeg', 'deflate',
                     'tiff_adobe_deflate'])
        .param('style', 'JSON-encoded style string', required=False)
        .param('resample', 'If false, an existing level of the image is used '
               'for the region.  If true, the internal values are '
               'interpolated to match the specified size as needed.  0-3 for '
               'a specific interpolation method (0-nearest, 1-lanczos, '
               '2-bilinear, 3-bicubic)', required=False,
               enum=['false', 'true', '0', '1', '2', '3'])
        .param('contentDisposition', 'Specify the Content-Disposition response '
               'header disposition-type value.', required=False,
               enum=['inline', 'attachment'])
        .param('contentDispositionFilename', 'Specify the filename used in '
               'the Content-Disposition response header.', required=False)
        .produces(ImageMimeTypes)
        .errorResponse('ID was invalid.')
        .errorResponse('Read access was denied for the item.', 403)
        .errorResponse('Insufficient memory.')
    )
    @access.public(cookie=True)
    @loadmodel(model='item', map={'itemId': 'item'}, level=AccessType.READ)
    def getTilesRegion(self, item, params):

        _adjustParams(params)
        params = self._parseParams(params, True, [
            ('left', float, 'region', 'left'),
            ('top', float, 'region', 'top'),
            ('right', float, 'region', 'right'),
            ('bottom', float, 'region', 'bottom'),
            ('regionWidth', float, 'region', 'width'),
            ('regionHeight', float, 'region', 'height'),
            ('units', str, 'region', 'units'),
            ('unitsWH', str, 'region', 'unitsWH'),
            ('width', int, 'output', 'maxWidth'),
            ('height', int, 'output', 'maxHeight'),
            ('fill', str),
            ('magnification', float, 'scale', 'magnification'),
            ('mm_x', float, 'scale', 'mm_x'),
            ('mm_y', float, 'scale', 'mm_y'),
            ('exact', bool, 'scale', 'exact'),
            ('frame', int),
            ('encoding', str),
            ('jpegQuality', int),
            ('jpegSubsampling', int),
            ('tiffCompression', str),
            ('style', str),
            ('resample', 'boolOrInt'),
            ('contentDisposition', str),
            ('contentDispositionFileName', str)
        ])
        _handleETag('getTilesRegion', item, params)
        setResponseTimeLimit(86400)
        try:
            regionData, regionMime = self.imageItemModel.getRegion(
                item, **params)
        except TileGeneralException as e:
            raise RestException(e.args[0])
        except ValueError as e:
            raise RestException('Value Error: %s' % e.args[0])

        subname = str(params.get('region')['left']) + ',' + str(params.get('region')['top'])

        self._setContentDisposition(
            item, params.get('contentDisposition'), regionMime, subname,
            params.get('contentDispositionFilename'))
        setResponseHeader('Content-Type', regionMime)

        if isinstance(regionData, pathlib.Path):
            BUF_SIZE = 65536

            def stream():
                try:
                    with regionData.open('rb') as f:
                        while True:
                            data = f.read(BUF_SIZE)
                            if not data:
                                break
                            yield data
                finally:
                    regionData.unlink()
            return stream
        setRawResponse()
        return regionData