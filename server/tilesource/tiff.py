from six import BytesIO

import PIL.Image
import PIL.ImageOps
import PIL.ImageMath
import PIL.ImagePalette

import numpy

from girder.plugins.large_image.tilesource import tiff
from girder.plugins.large_image.tilesource.base import GirderTileSource, \
    TILE_FORMAT_PIL

from .tiff_reader import TiledTiffDirectory

tiff.TiledTiffDirectory = TiledTiffDirectory


class TiffFileTileSource(tiff.TiffFileTileSource):
    cacheName = 'tilesource'
    name = 'tifffile'

    def _normalizeImage(self, tile, tileEncoding, range_, exclude=None,
                        bitmask=False):
        if tileEncoding != TILE_FORMAT_PIL:
            tile = PIL.Image.open(BytesIO(tile))
            tileEncoding = TILE_FORMAT_PIL
        if len(tile.getbands()) > 1:
            raise NotImplementedError('single band label images only')
        if bitmask:
            if tile.mode != 'L':
                raise NotImplementedError('8-bit bitmask images only')
            mask = numpy.asarray(tile)
            array = numpy.zeros(mask.shape, dtype=numpy.uint8)
            min_, max_ = max(1, int(range_[0])), min(8, int(range_[1]))
            for i in range(min_, max_ + 1):
                if bitmask and exclude and i in exclude:
                    continue
                value = int(i*255/8)
                array[numpy.nonzero(mask & 1 << i - 1)] = value
            tile = PIL.Image.fromarray(array)
        else:
            array = numpy.asarray(tile, dtype=numpy.float32)
            min_, max_ = range_
            if min_ == max_:
                array[numpy.where(array != min_)] = 0
                array[numpy.nonzero(array)] = 255
            else:
                array -= min_
                array *= 255/(max_ - min_)
            tile = PIL.Image.fromarray(array.round())
            tile = tile.convert('L')
        return tile, tileEncoding

    def _colormapImage(self, tile, tileEncoding, colormap, label=False):
        if tileEncoding != TILE_FORMAT_PIL:
            tile = PIL.Image.open(BytesIO(tile))
            tileEncoding = TILE_FORMAT_PIL
        if len(tile.getbands()) > 1:
            return tile, tileEncoding
            raise NotImplementedError('single band label images only')
        if label:
            # ouch
            mask = tile.point(lambda x: 0 if x == 0 else 255, '1')
        palette = PIL.ImagePalette.ImagePalette(palette=colormap)
        tile.putpalette(palette)
        if label:
            tile.putalpha(mask)
        return tile, tileEncoding

    def _labelImage(self, tile, tileEncoding, invert=True, flatten=False):
        if tileEncoding != TILE_FORMAT_PIL:
            tile = PIL.Image.open(BytesIO(tile))
            tileEncoding = TILE_FORMAT_PIL
        if len(tile.getbands()) > 1:
            raise NotImplementedError('single band label images only')
        if flatten:
            if tile.mode == 'I':
                n = 65536
            elif tile.mode == 'L':
                n = 256
            else:
                raise NotImplementedError('8-bit and 32-bit grayscale images only')
            lut = numpy.zeros(n)
            lut.fill(255)
            lut[0] = 0
            mask = tile.point(lut, 'L')
        else:
            mask = tile.convert('L')
        if invert:
            mask = PIL.ImageOps.invert(mask)
        tile = PIL.Image.new('RGBA', mask.size, 'white')
        tile.putalpha(mask)
        return tile, tileEncoding

    def _outputTile(self, tile, tileEncoding, *args, **kwargs):
        encoding = self.encoding
        if 'normalize' in kwargs and kwargs['normalize']:
            min_, max_ = kwargs.get('normalizeMin'), kwargs.get('normalizeMax')
            exclude = kwargs.get('exclude')
            bitmask = kwargs.get('bitmask', False)
            tile, tileEncoding = self._normalizeImage(tile, tileEncoding,
                                                      range_=(min_, max_),
                                                      exclude=exclude,
                                                      bitmask=bitmask)

        label = kwargs.get('label', False)
        if 'colormap' in kwargs and kwargs['colormap']:
            colormap = kwargs['colormap']
            tile, tileEncoding = self._colormapImage(tile, tileEncoding,
                                                     colormap, label)
            self.encoding = 'PNG'
        elif label:
            invert = kwargs.get('invertLabel', True)
            flatten = kwargs.get('flattenLabel', False)
            tile, tileEncoding = self._labelImage(tile, tileEncoding,
                                                  invert=invert,
                                                  flatten=flatten)
            self.encoding = 'PNG'

        result = super(TiffFileTileSource, self)._outputTile(tile,
                                                             tileEncoding,
                                                             *args, **kwargs)
        self.encoding = encoding
        return result


class TiffGirderTileSource(TiffFileTileSource, GirderTileSource):
    """
    Provides tile access to Girder items with a TIFF file.
    """
    cacheName = 'tilesource'
    name = 'tiff'
