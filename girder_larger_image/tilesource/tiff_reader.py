# import os
# import six
from girder import logger

from large_image_source_tiff import tiff_reader

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
    # def _open(self, filePath, directoryNum):
    #     """
    #     Open a TIFF file to a given file and IFD number.

    #     :param filePath: A path to a TIFF file on disk.
    #     :type filePath: str
    #     :param directoryNum: The number of the TIFF IFD to be used.
    #     :type directoryNum: int
    #     :raises: InvalidOperationTiffException or IOTiffException
    #     """
    #     self._close()
    #     if not os.path.isfile(filePath):
    #         raise InvalidOperationTiffException(
    #             'TIFF file does not exist: %s' % filePath)
    #     try:
    #         bytePath = filePath
    #         if not isinstance(bytePath, six.binary_type):
    #             bytePath = filePath.encode('utf8')
    #         self._tiffFile = libtiff_ctypes.TIFF.open(bytePath, 'r')
    #     except TypeError:
    #         raise tiff_reader.IOTiffException(
    #             'Could not open TIFF file: %s' % filePath)
    #     # pylibtiff changed the case of some functions between version 0.4 and
    #     # the version that supports libtiff 4.0.6.  To support both, ensure
    #     # that the cased functions exist.
    #     for func in self.CoreFunctions:
    #         if (not hasattr(self._tiffFile, func) and
    #                 hasattr(self._tiffFile, func.lower())):
    #             setattr(self._tiffFile, func, getattr(
    #                 self._tiffFile, func.lower()))

    #     self._directoryNum = directoryNum
    #     if self._tiffFile.SetDirectory(self._directoryNum) != 1:
    #         self._tiffFile.close()
    #         raise tiff_reader.IOTiffException(
    #             'Could not set TIFF directory to %d' % directoryNum)
    def _validate(self):
        validateExceptions = (
            'Only JPEG compression TIFF files are supported',
            'Only RGB and greyscale TIFF files are supported'
        )
        try:
            return super(TiledTiffDirectory, self)._validate()
        except tiff_reader.ValidationTiffException as e:
            if e.message not in validateExceptions:
                raise

        if (not self._tiffInfo.get('istiled') or
                not self._tiffInfo.get('tilewidth') or
                not self._tiffInfo.get('tilelength')):
            raise tiff_reader.ValidationTiffException('Only tiled TIFF files are supported')
    # TODO
    # def _getJpegFrameAndSave(self, x, y, data, entire=False):

    #     bytesWrite = libtiff_ctypes.libtiff.TIFFWriteTile(
    #         self._tiffFile, data, x, y).value
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
    # def saveTile(self, x, y, data):
    #     print 'save modified tile in tiff_reader.py'
    #     tileNum = self._toTileNum(x, y)
    #     imageBuffer = six.BytesIO()

    #     if self._tiffInfo.get('compression') == libtiff_ctypes.COMPRESSION_JPEG:
    #         # Write JPEG Start Of Image marker
    #         imageBuffer.write(b'\xff\xd8')
    #         imageBuffer.write(self._getJpegTables())
    #         imageBuffer.write(self._getJpegFrameAndSave(x, y, data))
    #         # Write JPEG End Of Image marker
    #         imageBuffer.write(b'\xff\xd9')
    #         return imageBuffer.getvalue()
