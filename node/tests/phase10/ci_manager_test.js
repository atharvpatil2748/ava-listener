const assert = require('assert');
const { CIManager } = require('../../ci_manager');
const path = require('path');
const fs = require('fs');

const baseDir = path.join(__dirname, '..', '..', '..');
const ci = new CIManager(baseDir);

// Mock a passing test and a failing test script
const passingTest = 'temp_passing_test.js';
const failingTest = 'temp_failing_test.js';
fs.writeFileSync(path.join(baseDir, passingTest), 'console.log("pass");', 'utf8');
fs.writeFileSync(path.join(baseDir, failingTest), 'process.exit(1);', 'utf8');

try {
    const success = ci.runTestSuite([passingTest, failingTest]);
    assert.strictEqual(success, false);
    
    assert.strictEqual(ci.results.totalTests, 2);
    assert.strictEqual(ci.results.passedTests, 1);
    assert.strictEqual(ci.results.failedTests, 1);
    assert.strictEqual(ci.results.successRate, 50);
    assert.strictEqual(ci.results.failures.length, 1);
    assert.strictEqual(ci.results.failures[0].test, failingTest);
    
    const reportPath = path.join(baseDir, 'ci_report.json');
    assert.ok(fs.existsSync(reportPath));
    const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
    assert.strictEqual(report.totalTests, 2);
    assert.strictEqual(report.successRate, 50);

} finally {
    fs.unlinkSync(path.join(baseDir, passingTest));
    fs.unlinkSync(path.join(baseDir, failingTest));
    const reportPath = path.join(baseDir, 'ci_report.json');
    if (fs.existsSync(reportPath)) {
        fs.unlinkSync(reportPath);
    }
}

console.log('ci_manager_test passed');
