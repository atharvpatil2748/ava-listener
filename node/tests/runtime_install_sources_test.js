const path = require('path');
const fs = require('fs');
const { RuntimeManager } = require('../runtime_manager');

const baseDir = path.join(__dirname, '..');
const rm = new RuntimeManager({ baseDir });

// prepare local source dir
const localSource = path.join(__dirname, 'local_runtime_src');
if (!fs.existsSync(localSource)) fs.mkdirSync(localSource, { recursive: true });
fs.writeFileSync(path.join(localSource, 'python.exe'), 'DUMMY');

// create sources json
const sourcesJson = {
  runtime: {
    github: 'file:///nonexistent/github_runtime',
    mirror: 'file:///nonexistent/mirror_runtime',
    local: `file://${localSource}`
  }
};
const sourcesPath = path.join(__dirname, 'runtime_sources_test.json');
fs.writeFileSync(sourcesPath, JSON.stringify(sourcesJson, null, 2), 'utf8');

// ensure runtimeRoot is empty
if (fs.existsSync(rm.runtimeRoot)) fs.rmSync(rm.runtimeRoot, { recursive: true, force: true });
fs.mkdirSync(rm.runtimeRoot, { recursive: true });

try {
  const installed = rm.install_runtime({ sourcesFile: sourcesPath });
  console.log('install_runtime ->', installed);
  console.log('runtimeRoot exists ->', fs.existsSync(rm.runtimeRoot));
} catch (e) {
  console.error('install_runtime error ->', e.message);
}

// cleanup
try { fs.rmSync(localSource, { recursive: true, force: true }); } catch (e) {}
try { fs.unlinkSync(sourcesPath); } catch (e) {}
process.exit(0);
