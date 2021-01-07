from large_image.tilesource import AvailableTileSources
from large_image.exceptions import TileSourceException
from .tiff import TiffFileTileSource, TiffGirderTileSource

AvailableTileSources['tifffile'] = TiffFileTileSource
AvailableTileSources['tiff'] = TiffGirderTileSource

__all__ = ['TileSourceException', 'AvailableTileSources']
