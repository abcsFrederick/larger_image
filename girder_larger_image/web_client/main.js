import { registerPluginNamespace } from '@girder/core/pluginUtils';

import './views/fileList';

import * as largerImage from './index';

registerPluginNamespace('larger_image', largerImage);
