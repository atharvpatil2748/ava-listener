const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const { ModelManager } = require('../model_manager');

const baseDir = path.join(__dirname, '..');
const tmpModelsDir = path.join(__dirname, 'tmp_models');
if (!fs.existsSync(tmpModelsDir)) fs.mkdirSync(tmpModelsDir, { recursive: true });

function sha256(data) { return crypto.createHash('sha256').update(data).digest('hex'); }

// create a valid model file
const validContent = 'VALID_MODEL_CONTENT';
const validSha = sha256(validContent);
const validFile = path.join(tmpModelsDir, 'valid.model');
fs.writeFileSync(validFile, validContent, 'utf8');

// manifest pointing to local file
const manifest = {
  manifestVersion: 1,
  models: [
    {
      id: 'valid.model',
      version: '1',
      size: String(Buffer.byteLength(validContent)),
      sha256: validSha,
      url: `file://${validFile}`
    }
  ]
};

const manifestPath = path.join(__dirname, 'tmp_manifest.json');
fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), 'utf8');

const mm = new ModelManager({ baseDir, manifestPath, cacheRoot: path.join(__dirname, 'tmp_cache') });
(async () => {
  try {
    // verifyOrDownload should download the valid model
    const paths = await mm.verifyOrDownload((p) => console.log('progress', p));
    console.log('downloadedPaths', paths);

    // Now tamper file to simulate invalid sha
    const modelPath = mm.get_model_path('valid.model');
    fs.writeFileSync(modelPath, 'CORRUPTED', 'utf8');
    try {
      await mm.verify_download(modelPath, validSha);
      console.log('verify_download:unexpected success');
    } catch (e) {
      console.log('verify_download:expected failure ->', e.message);
    }

    // Simulate partial download recovery: create .download with bad content
    const tempDownload = `${modelPath}.download`;
    fs.writeFileSync(tempDownload, 'PARTIAL', 'utf8');
    try {
      await mm.verify_download(tempDownload, validSha);
      console.log('partial verify:unexpected success');
    } catch (e) {
      console.log('partial verify:expected failure and file removed');
      console.log('exists after verify:', fs.existsSync(tempDownload));
    }

    console.log('model verification tests completed');
    process.exit(0);
  } catch (e) {
    console.error('ERR', e.message);
    process.exit(2);
  }
})();
