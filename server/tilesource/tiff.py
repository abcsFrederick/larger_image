from girder.plugins.large_image.tilesource import tiff

from .tiff_reader import TiledTiffDirectory

tiff.TiledTiffDirectory = TiledTiffDirectory


class TiffFileTileSource(tiff.TiffFileTileSource):
    cacheName = 'tilesource'
    name = 'tifffile'
