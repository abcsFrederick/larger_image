from girder.plugins.large_image.tilesource import AvailableTileSources, TileSourceException

from .tiff import TiffFileTileSource, TiffGirderTileSource

AvailableTileSources['tifffile'] = TiffFileTileSource
AvailableTileSources['tiff'] = TiffGirderTileSource

__all__ = ['TileSourceException', 'AvailableTileSources']
