from large_image.tilesource import AvailableTileSources
from large_image.exceptions import TileSourceException
from .tiff import TiffFileTileSource, TiffGirderTileSource
from large_image_source_openslide import girder_source

AvailableTileSources['openslide'] = girder_source.OpenslideGirderTileSource
AvailableTileSources['tifffile'] = TiffFileTileSource
AvailableTileSources['tiff'] = TiffGirderTileSource

__all__ = ['TileSourceException', 'AvailableTileSources']
