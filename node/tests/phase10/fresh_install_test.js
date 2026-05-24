const assert = require('assert');
const { PackageValidator } = require('../../package_validator');
const path = require('path');
const fs = require('fs');

const pv = new PackageValidator(path.join(__dirname, '..', '..', '..'));
const tarballPath = pv.run_npm_pack();

assert.doesNotThrow(() => {
    pv.validate_fresh_install(tarballPath);
});

// Cleanup
if (fs.existsSync(tarballPath)) {
    fs.unlinkSync(tarballPath);
}

console.log('fresh_install_test passed');
