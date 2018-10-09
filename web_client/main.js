import { registerPluginNamespace } from 'girder/pluginUtils';

import './views/fileList';

import * as largerImage from 'girder_plugins/larger_image';
registerPluginNamespace('larger_image', largerImage);
