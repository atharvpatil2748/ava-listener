const path = require('path');
const fs = require('fs');
const { RuntimeManager } = require('../../runtime_manager');

(async () => {
  const baseDir = path.join(__dirname, '..', '..');
  const tmpRuntimeSrc = path.join(__dirname, 'tmp_runtime_src');
  const localSrc = path.join(tmpRuntimeSrc, 'local_runtime');
  fs.mkdirSync(localSrc, { recursive: true });
  // create dummy python in local src
  const pyPath = path.join(localSrc, process.platform === 'win32' ? 'python.exe' : 'bin/python');
  fs.mkdirSync(path.dirname(pyPath), { recursive: true });
  fs.writeFileSync(pyPath, 'DUMMYPY', 'utf8');

  const sources = {
    runtime: {
      github: 'file:///nonexistent/github_runtime',
      mirror: 'file:///nonexistent/mirror_runtime',
      local: `file://${localSrc}`
    }
  };
  const sourcesPath = path.join(__dirname, 'tmp_runtime_sources_chain.json');
  fs.writeFileSync(sourcesPath, JSON.stringify(sources, null, 2), 'utf8');

  const rm = new RuntimeManager({ baseDir });
  // ensure runtimeRoot empty
  if (fs.existsSync(rm.runtimeRoot)) fs.rmSync(rm.runtimeRoot, { recursive: true, force: true });
  fs.mkdirSync(rm.runtimeRoot, { recursive: true });

  const installed = rm.install_runtime({ sourcesFile: sourcesPath });
  console.log('install_runtime ->', installed);
  const verified = rm.verify_runtime();
  console.log('verify_runtime ->', verified);
  process.exit((installed && verified) ? 0 : 2);
})();
