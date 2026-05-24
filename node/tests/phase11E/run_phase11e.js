const { execSync } = require('child_process');
const path = require('path');

function runTest(file, args = []) {
    console.log(`\n=====================================================`);
    console.log(`Running ${file} ${args.join(' ')}`);
    console.log(`=====================================================\n`);
    try {
        execSync(`node ${path.join(__dirname, file)} ${args.join(' ')}`, { stdio: 'inherit' });
    } catch (e) {
        console.error(`\n[!] Test ${file} failed.`);
        process.exit(1);
    }
}

console.log("Starting Phase 11E Verification Suite...");
const args = process.argv.slice(2);

runTest('start_stop_stress_test.js', args);
runTest('recovery_stress_test.js', args);
runTest('long_idle_test.js', args);
runTest('generate_readme.js', args);

console.log("\nAll Phase 11E tests passed and README metrics generated!");
