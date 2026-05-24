#!/usr/bin/env node
const path = require('path');
const fs = require('fs');
const { RuntimeManager } = require('./runtime_manager');
const { ModelManager } = require('./model_manager');

function validatePackageLayout() {
    const root = path.join(__dirname, '..');
    const required = ['node', 'runtime', 'models', 'profiles'];
    let ok = true;

    // Automatically create model directories so fresh clones do not fail
    const modelsDir = path.join(root, 'models');
    const manifestsDir = path.join(modelsDir, 'manifests');
    if (!fs.existsSync(modelsDir)) {
        fs.mkdirSync(modelsDir, { recursive: true });
    }
    if (!fs.existsSync(manifestsDir)) {
        fs.mkdirSync(manifestsDir, { recursive: true });
    }

    for (const entry of required) {
        const p = path.join(root, entry);
        if (!fs.existsSync(p)) {
            console.error(`Missing required package entry: ${entry}`);
            ok = false;
        }
    }

    if (!ok) {
        process.exit(1);
    }

    console.log('Package layout validation passed.');
}

async function main() {
    const args = process.argv.slice(2);
    if (args.includes('--validate-layout')) {
        validatePackageLayout();
        return;
    }

    console.log('Bootstrap CLI is a placeholder. Runtime startup is handled from AVAListener.start().');
}

main().catch((err) => {
    console.error(err);
    process.exit(1);
});
