const assert = require('assert');
const { PackageValidator } = require('../../package_validator');
const path = require('path');
const fs = require('fs');

const pv = new PackageValidator(path.join(__dirname, '..', '..', '..'));

const tarballPath = pv.run_npm_pack();
assert.ok(fs.existsSync(tarballPath));
assert.ok(tarballPath.endsWith('.tgz'));

// Optional: cleanup
// fs.unlinkSync(tarballPath);

console.log('npm_pack_test passed');
