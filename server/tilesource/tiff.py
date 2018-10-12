from girder.plugins.large_image.tilesource import tiff
from girder.plugins.large_image.tilesource.base import GirderTileSource

from .tiff_reader import TiledTiffDirectory

tiff.TiledTiffDirectory = TiledTiffDirectory


class TiffFileTileSource(tiff.TiffFileTileSource):
    cacheName = 'tilesource'
    name = 'tifffile'


class TiffGirderTileSource(TiffFileTileSource, GirderTileSource):
    """
    Provides tile access to Girder items with a TIFF file.
    """
    cacheName = 'tilesource'
    name = 'tiff'
