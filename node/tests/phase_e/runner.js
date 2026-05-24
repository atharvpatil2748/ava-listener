const { spawn, spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const { RuntimeManager } = require('../../runtime_manager');
const { ModelManager } = require('../../model_manager');
const baseDir = path.join(__dirname, '..', '..');
const rm = new RuntimeManager({ baseDir });
const mm = new ModelManager({ baseDir });

function runManualExample(timeoutMs = 15000) {
  return new Promise((resolve) => {
    const proc = spawn(process.execPath, [path.join(baseDir, 'examples', 'manual_sdk_test.js')], { cwd: baseDir });
    let out = '';
    let err = '';
    proc.stdout.on('data', (d) => { out += d.toString(); });
    proc.stderr.on('data', (d) => { err += d.toString(); });
    const timer = setTimeout(() => {
      proc.kill('SIGTERM');
      resolve({ timedOut: true, out, err });
    }, timeoutMs);
    proc.on('exit', (code) => {
      clearTimeout(timer);
      resolve({ code, out, err });
    });
  });
}

async function test_repeated_startup() {
  console.log('TEST: repeated_startup');
  const r1 = await runManualExample(12000);
  const ok1 = /\[READY\]/.test(r1.out);
  console.log('run1 ready=', ok1);
  const r2 = await runManualExample(12000);
  const ok2 = /\[READY\]/.test(r2.out);
  console.log('run2 ready=', ok2);
  return ok1 && ok2;
}

function test_interrupted_install() {
  console.log('TEST: interrupted_install');
  const bsPath = rm.get_bootstrap_state_path();
  const bad = { phase: 'install', status: 'failed', lastCompletedStep: 'install_runtime', timestamp: new Date().toISOString() };
  fs.writeFileSync(bsPath, JSON.stringify(bad, null, 2), 'utf8');
  const canResume = rm.can_resume_bootstrap(bad);
  if (!canResume) {
    rm.rollback_bootstrap_state(bad);
    const exists = fs.existsSync(bsPath);
    console.log('rolled back, bootstrap_state exists=', exists);
    return true;
  }
  console.log('can resume:', canResume);
  return false;
}

function test_corrupted_runtime() {
  console.log('TEST: corrupted_runtime');
  const runtimeRoot = rm.runtimeRoot;
  try { fs.mkdirSync(runtimeRoot, { recursive: true }); } catch (e) {}
  const badExe = path.join(runtimeRoot, process.platform === 'win32' ? 'python.exe' : 'bin/python');
  try { fs.mkdirSync(path.dirname(badExe), { recursive: true }); fs.writeFileSync(badExe, 'CORRUPT', 'utf8'); } catch (e) {}
  const verified = rm.verify_runtime();
  console.log('verify_runtime (should be false)=', verified);
  // attempt install from runtime_sources.json (may copy local if present)
  const installed = rm.install_runtime();
  console.log('install_runtime ->', installed);
  const reverify = rm.verify_runtime();
  console.log('reverify ->', reverify);
  return !verified && (installed ? reverify : true);
}

async function test_corrupted_model() {
  console.log('TEST: corrupted_model');
  const manifest = await mm.load_manifest();
  const model = manifest.models[0];
  const modelPath = mm.get_model_path(model.id);
  // ensure model exists then corrupt
  if (fs.existsSync(modelPath)) {
    fs.writeFileSync(modelPath, 'CORRUPTED', 'utf8');
  }
  const missing = await mm.verify_models();
  console.log('missing count after corruption=', missing.length);
  try {
    await mm.verifyOrDownload();
    console.log('verifyOrDownload attempted');
  } catch (e) {
    console.log('verifyOrDownload error', e.message);
  }
  const ok = await mm.verify_model(model);
  console.log('model verified after repair=', ok);
  return missing.length > 0;
}

function test_concurrent_startup_stress() {
  console.log('TEST: concurrent_startup_stress');
  const multiScript = path.join(__dirname, '..', 'tmp_bootstrap_multi_test.js');
  const res = spawnSync(process.execPath, [multiScript], { encoding: 'utf8' });
  console.log('multi test stdout:\n', res.stdout);
  return /SUMMARY acquired=\d+ failed=\d+/.test(res.stdout);
}

async function runAll() {
  const results = {};
  results.repeated_startup = await test_repeated_startup();
  results.interrupted_install = test_interrupted_install();
  results.corrupted_runtime = test_corrupted_runtime();
  results.corrupted_model = await test_corrupted_model();
  results.concurrent_startup_stress = test_concurrent_startup_stress();
  console.log('\nPHASE E RESULTS:', results);
}

runAll().catch(e => { console.error(e); process.exit(2); });
