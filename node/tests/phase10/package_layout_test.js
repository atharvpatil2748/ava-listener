const assert = require('assert');
const { PackageValidator } = require('../../package_validator');
const path = require('path');

const pv = new PackageValidator(path.join(__dirname, '..', '..', '..'));

assert.doesNotThrow(() => {
    pv.validate_package_layout();
});

console.log('package_layout_test passed');
