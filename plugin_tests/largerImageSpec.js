girderTest.importPlugin('jobs');
girderTest.importPlugin('worker');
girderTest.importPlugin('large_image');
girderTest.importPlugin('larger_image');
girderTest.startApp();

$(function () {
    describe('Test the larger_image plugin', function () {
        it('create the admin user', function () {
            girderTest.createUser(
                'admin', 'admin@email.com', 'Admin', 'Admin', 'testpassword')();
        });
        it('go to collections page', function () {
            runs(function () {
                $("a.g-nav-link[g-target='collections']").click();
            });

            waitsFor(function () {
                return $('.g-collection-create-button:visible').length > 0;
            }, 'navigate to collections page');

            runs(function () {
                expect($('.g-collection-list-entry').length).toBe(0);
            });
        });
        it('create collection', girderTest.createCollection('test', '', 'image'));
        it('upload test file', function () {
            girderTest.waitForLoad();
            runs(function () {
                $('.g-folder-list-link:first').click();
            });
            girderTest.waitForLoad();
            runs(function () {
                girderTest.binaryUpload('plugins/larger_image/plugin_tests/test_files/grey10kx5kdeflate.tif');
            });
            girderTest.waitForLoad();
        });
        it('navigate to item and make a large image', function () {
            runs(function () {
                $('a.g-item-list-link').click();
            });
            girderTest.waitForLoad();
            waitsFor(function () {
                return $('.g-large-image-create').length !== 0;
            });
            runs(function () {
                $('.g-large-image-create').click();
            });
            girderTest.waitForLoad();
            runs(function () {
                $('.l-large-image').click();
            });
            girderTest.waitForLoad();
            // wait for job to complete
            waitsFor(function () {
                return $('.g-item-image-viewer-select').length !== 0;
            }, 15000);
            girderTest.waitForLoad();
        });
    });
});
