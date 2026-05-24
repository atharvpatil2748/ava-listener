const assert = require('assert');
const { PackageValidator } = require('../../package_validator');
const path = require('path');
const fs = require('fs');

const pv = new PackageValidator(path.join(__dirname, '..', '..', '..'));
const tarballPath = pv.run_npm_pack();

assert.doesNotThrow(() => {
    pv.validate_package_size(tarballPath);
});

// Mock constraints to test hard limit
const originalConstraintsPath = pv.constraintsPath;
const mockConstraintsPath = path.join(__dirname, 'mock_constraints.json');
fs.writeFileSync(mockConstraintsPath, JSON.stringify({ softLimitMB: 0.0001, hardLimitMB: 0.0002 }), 'utf8');

try {
    pv.constraintsPath = mockConstraintsPath;
    assert.throws(() => {
        pv.validate_package_size(tarballPath);
    }, /exceeds hard limit/);
} finally {
    pv.constraintsPath = originalConstraintsPath;
    fs.unlinkSync(mockConstraintsPath);
    // Cleanup tarball
    fs.unlinkSync(tarballPath);
}

console.log('package_size_test passed');
