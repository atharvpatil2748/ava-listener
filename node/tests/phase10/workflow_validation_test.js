const assert = require('assert');
const fs = require('fs');
const path = require('path');

const workflowsDir = path.join(__dirname, '..', '..', '..', '.github', 'workflows');

// 1. Verify files exist
const nodeTests = path.join(workflowsDir, 'node-tests.yml');
const packageValidation = path.join(workflowsDir, 'package-validation.yml');
const releaseValidation = path.join(workflowsDir, 'release-validation.yml');

assert.ok(fs.existsSync(nodeTests), 'node-tests.yml is missing');
assert.ok(fs.existsSync(packageValidation), 'package-validation.yml is missing');
assert.ok(fs.existsSync(releaseValidation), 'release-validation.yml is missing');

// 2. Verify contents of node-tests.yml
const ntContent = fs.readFileSync(nodeTests, 'utf8');
assert.ok(ntContent.includes('matrix:'));
assert.ok(ntContent.includes('windows-latest'));
assert.ok(ntContent.includes('ubuntu-latest'));
assert.ok(ntContent.includes('macos-latest'));
assert.ok(ntContent.includes('node-version: [18.x, 20.x]'));
assert.ok(ntContent.includes('node node/tests/phase10/platform_resolution_test.js'));

// 3. Verify contents of package-validation.yml
const pvContent = fs.readFileSync(packageValidation, 'utf8');
assert.ok(pvContent.includes('npm_pack_test.js'));
assert.ok(pvContent.includes('node node/tests/phase10/package_size_test.js'));
assert.ok(pvContent.includes('node node/tests/phase10/fresh_install_test.js'));
assert.ok(pvContent.includes('upload-artifact'));

// 4. Verify contents of release-validation.yml
const rvContent = fs.readFileSync(releaseValidation, 'utf8');
assert.ok(rvContent.includes('node node/tests/phase10/release_manifest_test.js'));
assert.ok(rvContent.includes('node node/tests/phase10/checksum_generation_test.js'));

console.log('workflow_validation_test passed');
