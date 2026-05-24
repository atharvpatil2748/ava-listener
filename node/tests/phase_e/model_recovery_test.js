const path = require('path');
const fs = require('fs');
const { ModelManager } = require('../../model_manager');

(async () => {
  const baseDir = path.join(__dirname, '..', '..');
  const tmpCache = path.join(__dirname, 'tmp_model_recovery_cache');
  const tmpModels = path.join(__dirname, 'tmp_model_sources');
  if (!fs.existsSync(tmpModels)) fs.mkdirSync(tmpModels, { recursive: true });
  if (!fs.existsSync(tmpCache)) fs.mkdirSync(tmpCache, { recursive: true });

  // create source model file
  const modelContent = 'RECOVERY_MODEL';
  const modelPath = path.join(tmpModels, 'recover.model');
  fs.writeFileSync(modelPath, modelContent, 'utf8');
  const modelSha = require('crypto').createHash('sha256').update(modelContent).digest('hex');

  const manifest = { manifestVersion: 1, models: [{ id: 'recover.model', version: '1', size: String(Buffer.byteLength(modelContent)), sha256: modelSha, url: `file://${modelPath}` }] };
  const manifestPath = path.join(__dirname, 'tmp_manifest_recovery.json');
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), 'utf8');

  const mm = new ModelManager({ baseDir, manifestPath, cacheRoot: tmpCache });

  // simulate corrupted cached model
  const cachedModelPath = mm.get_model_path('recover.model');
  fs.mkdirSync(path.dirname(cachedModelPath), { recursive: true });
  fs.writeFileSync(cachedModelPath, 'CORRUPTED', 'utf8');

  // run verification+recovery
  try {
    const missing = await mm.verify_models();
    console.log('initial missing count', missing.length);
    await mm.verifyOrDownload((p) => console.log('progress', p));
    const ok = await mm.verify_model(manifest.models[0]);
    console.log('post-recovery verified=', ok);
    process.exit(ok ? 0 : 2);
  } catch (e) {
    console.error('ERR', e.message);
    process.exit(2);
  }
})();
