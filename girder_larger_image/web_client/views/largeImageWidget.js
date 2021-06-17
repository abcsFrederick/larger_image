import View from '@girder/core/views/View';
import { handleClose, handleOpen } from '@girder/core/dialog';
import { restRequest } from '@girder/core/rest';
import events from '@girder/core/events';

import LargeImageWidgetTemplate from '../templates/largeImageWidget.pug';

import '../stylesheets/largeImageWidget.styl';

import '@girder/core/utilities/jquery/girderEnable';
import '@girder/core/utilities/jquery/girderModal';

var LargeImageWidget = View.extend({
    events: {
        'input #l-quality': '_renderQualityLabel',
        'submit #l-large-image-form': function () {
            var data = {
                fileId: this.file.id,
                notify: this.$('#l-notify').is(':checked'),
                compression: this.$('#l-compression').val().toLowerCase(),
                quality: this.$('#l-quality').val(),
                tileSize: this.$('#l-tileSize').val(),
                force: this.$('#l-force').is(':checked')
            };

            restRequest({
                type: 'POST',
                url: 'item/' + this.item.id + '/tiles',
                data: data,
                error: function (error) {
                    if (error.status !== 0) {
                        events.trigger('g:alert', {
                            text: error.responseJSON.message,
                            type: 'info',
                            timeout: 5000,
                            icon: 'info'
                        });
                    }
                }
            }).done(() => {
                this.item.unset('largeImage');
                this.item.fetch();
                this.$el.modal('hide');
                this.trigger('l:submitted', {item: this.item, file: this.file});
            }).fail((err) => {
                this.$('.l-validation-failed-message')
                    .text(err.responseJSON.message);
                this.$('button.l-large-image').girderEnable(true);
                this.$('#l-' + err.responseJSON.field).focus();
            });

            this.$('button.l-large-image').girderEnable(false);
            this.$('.l-validation-failed-message').empty();

            return false;
        }
    },

    initialize: function (settings) {
        this.item = settings.item;
        this.file = settings.file;
    },

    _renderQualityLabel: function () {
        var quality = this.$('#l-quality').val();
        this.$('#l-quality-label').text(`Quality ${quality}%`);
    },

    // FIXME: where does girder implement this?
    _setApiDefaults: function (description) {
        var parameters = description.paths['/item/{itemId}/tiles/extended'].post.parameters;
        parameters.forEach((parameter) => {
            switch (parameter.name) {
                case 'notify':
                    $('#l-notify').prop('checked', parameter.default);
                    break;
                case 'compression':
                    parameter.enum.forEach((compressionType) => {
                        $('#l-compression').append($('<option>', {
                            value: compressionType,
                            text: compressionType,
                            selected: compressionType === parameter.default
                        }));
                    });
                    break;
                case 'quality':
                    $('#l-quality').val(parameter.default);
                    break;
                case 'tileSize':
                    $('#l-tileSize').val(parameter.default);
                    break;
            }
        });
    },

    render: function () {
        this.$el.html(LargeImageWidgetTemplate({
            item: this.item,
            file: this.file
        })).girderModal(this).on('shown.bs.modal', () => {
            this.$('#l-quality').select().focus();
        }).on('hidden.bs.modal', () => {
            handleClose('largeimage', undefined, this.file.get('_id'));
        });

        restRequest({
            type: 'GET',
            url: 'describe'
        }).done((result) => {
            $('#l-compression').empty();
            this._setApiDefaults(result);
            this._renderQualityLabel();
            this.$('#l-compression').girderEnable(true);
            this.$('button.l-large-image').girderEnable(true);
        }).fail((err) => {
            this.$('.l-validation-failed-message').text(err.responseJSON.message);
        });

        handleOpen('largeimage', undefined, this.file.get('_id'));

        return this;
    }
});

export default LargeImageWidget;
