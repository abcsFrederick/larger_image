from girder import logger

from girder.plugins.large_image.tilesource import tiff_reader

try:
    from libtiff import libtiff_ctypes
except ValueError as exc:
    logger.warn('Failed to import libtiff; try upgrading the python module (%s)' % exc)
    raise ImportError(str(exc))
try:
    import PIL.Image
except ImportError:
    PIL = None


class TiledTiffDirectory(tiff_reader.TiledTiffDirectory):
    def _validate(self):
        try:
            return super(TiledTiffDirectory, self)._validate()
        except tiff_reader.ValidationTiffException as e:
            if e.message != 'Only JPEG compression TIFF files are supported':
                raise

        if (not self._tiffInfo.get('istiled') or
                not self._tiffInfo.get('tilewidth') or
                not self._tiffInfo.get('tilelength')):
            raise tiff_reader.ValidationTiffException('Only tiled TIFF files are supported')

    def getTile(self, x, y):
        tile = super(TiledTiffDirectory, self).getTile(x, y)
        if tile is not None:
            return tile

        compression_types = (
            libtiff_ctypes.COMPRESSION_NONE,
            libtiff_ctypes.COMPRESSION_ADOBE_DEFLATE,
            libtiff_ctypes.COMPRESSION_LZW
        )
        if self._tiffInfo.get('compression') in compression_types:
            tile_plane = self._tiffFile.read_one_tile(x*self._tileHeight,
                                                      y*self._tileWidth)
            return PIL.Image.fromarray(tile_plane)
