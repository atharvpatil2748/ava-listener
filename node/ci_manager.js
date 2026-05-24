const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

class CIManager {
    constructor(baseDir = path.join(__dirname, '..')) {
        this.baseDir = baseDir;
        this.reportPath = path.join(this.baseDir, 'ci_report.json');
        this.results = {
            totalTests: 0,
            passedTests: 0,
            failedTests: 0,
            failures: [],
            successRate: 0,
            timestamp: new Date().toISOString()
        };
    }

    runTest(testFile) {
        this.results.totalTests++;
        const testPath = path.join(this.baseDir, testFile);
        const res = spawnSync('node', [testPath], { cwd: this.baseDir, encoding: 'utf8' });
        
        if (res.status === 0 && !res.error) {
            this.results.passedTests++;
            return true;
        } else {
            this.results.failedTests++;
            this.results.failures.push({
                test: testFile,
                error: res.error ? res.error.message : null,
                stderr: res.stderr,
                stdout: res.stdout,
                exitCode: res.status
            });
            return false;
        }
    }

    runTestSuite(tests) {
        for (const test of tests) {
            this.runTest(test);
        }
        this.calculateMetrics();
        this.emitReport();
        return this.results.failedTests === 0;
    }

    calculateMetrics() {
        if (this.results.totalTests === 0) {
            this.results.successRate = 0;
        } else {
            this.results.successRate = (this.results.passedTests / this.results.totalTests) * 100;
        }
    }

    emitReport() {
        fs.writeFileSync(this.reportPath, JSON.stringify(this.results, null, 2), 'utf8');
        return this.reportPath;
    }
}

module.exports = { CIManager };
