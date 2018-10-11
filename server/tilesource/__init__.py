from girder.plugins.large_image.tilesource import AvailableTileSources, TileSourceException

from .tiff import TiffFileTileSource


AvailableTileSources['.tiff'] = TiffFileTileSource

__all__ = ['TileSourceException', 'AvailableTileSources']
