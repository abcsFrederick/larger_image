import FileListWidget from '@girder/core/views/widgets/FileListWidget';
import { wrap } from '@girder/core/utilities/PluginUtils';
import { AccessType } from '@girder/core/constants';

import LargeImageWidget from './largeImageWidget';

wrap(FileListWidget, 'initialize', function (initialize, settings) {
    this.largeImage = settings.largeImage;
    initialize.call(this, settings);
});

wrap(FileListWidget, 'render', function (render) {
    render.call(this);
    if (!this.parentItem || !this.parentItem.get('_id')) {
        return this;
    }
    if (this.parentItem.getAccessLevel() < AccessType.WRITE) {
        return this;
    }
    // replace the large_image direct POST with dialog
    this.$('.g-large-image-create').off('click');
    this.$('.g-large-image-create').on('click', (e) => {
        var cid = $(e.currentTarget).parent().attr('file-cid');
        var largeImageWidget = new LargeImageWidget({
            el: $('#g-dialog-container'),
            item: this.parentItem,
            file: this.collection.get(cid),
            parentView: this
        }).off('l:submitted', null, this).on('l:created', function () {
            this.render();
        }, this);
        largeImageWidget.render();
    });
    if (!this.fileEdit && !this.upload && this.largeImage) {
        this.largeImageDialog(this.largeImage);
        this.largeImage = false;
    }
    return this;
});
