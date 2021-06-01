from girder_large_image.rest.tiles import ImageMimeTypes, \
    TilesItemResource

class TilesEx(TilesItemResource):
	def getTilesRegion(self, item, params):
        regionData = super(AnnotationResource, self).getTilesRegion(item, params)