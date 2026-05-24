const path = require('path');
const fs = require('fs');
const { RuntimeManager } = require('../runtime_manager');

const baseDir = path.join(__dirname, '..');
const rm = new RuntimeManager({ baseDir });

// Ensure clean test artifacts
const runtimeRoot = rm.runtimeRoot;
if (!fs.existsSync(runtimeRoot)) fs.mkdirSync(runtimeRoot, { recursive: true });

// Create fake cached python file
const cachedPython = path.join(runtimeRoot, process.platform === 'win32' ? 'python.exe' : 'bin/python');
try { fs.writeFileSync(cachedPython, 'FAKEPY', { mode: 0o755 }); } catch (e) {}

// Create fake venv python
const venvPython = process.platform === 'win32'
  ? path.join(baseDir, '..', 'venv', 'Scripts', 'python.exe')
  : path.join(baseDir, '..', 'venv', 'bin', 'python');
try { fs.mkdirSync(path.dirname(venvPython), { recursive: true }); fs.writeFileSync(venvPython, 'FAKEVENV', { mode: 0o755 }); } catch (e) {}

console.log('get_cached_python ->', rm.get_cached_python());
console.log('get_venv_python ->', rm.get_venv_python());
console.log('get_system_python ->', rm.get_system_python());
try {
  console.log('get_python_exec ->', rm.get_python_exec());
} catch (e) {
  console.log('get_python_exec -> error:', e.message);
}

// Cleanup created fake files
try { fs.unlinkSync(cachedPython); } catch (e) {}
try { fs.unlinkSync(venvPython); } catch (e) {}
process.exit(0);
