const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { promisify } = require('util');
const stream = require('stream');
const pipeline = promisify(stream.pipeline);
const fetch = global.fetch || require('node-fetch');

const os = require('os');

const { PathManager } = require('./path_manager');

class ModelManager {
    constructor(options = {}) {
        this.options = options;
        this.cacheRoot = options.cacheRoot || this.get_default_cache_dir();
        this.manifestPath = options.manifestPath || path.join(PathManager.get_model_manifest_dir(), 'manifest.json');
        this.baseDir = options.baseDir || PathManager.get_package_root();
        this.metadataRoot = options.metadataRoot || path.join(this.cacheRoot, 'metadata');
        this.installedModelsPath = path.join(this.metadataRoot, 'installed_models.json');
        this.checksumsPath = path.join(this.metadataRoot, 'checksums.json');
    }

    get_default_cache_dir() {
        const platform = os.platform();
        if (platform === 'win32') {
            return path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local'), 'AVAListener');
        }
        if (platform === 'darwin') {
            return path.join(os.homedir(), 'Library', 'Application Support', 'AVAListener');
        }
        return path.join(os.homedir(), '.local', 'share', 'avalistener');
    }

    async load_manifest() {
        if (!fs.existsSync(this.manifestPath)) {
            const manifestsDir = path.dirname(this.manifestPath);
            const modelsDir = path.dirname(manifestsDir);
            
            if (!fs.existsSync(modelsDir)) {
                fs.mkdirSync(modelsDir, { recursive: true });
            }
            if (!fs.existsSync(manifestsDir)) {
                fs.mkdirSync(manifestsDir, { recursive: true });
            }
            
            const defaultManifest = {
                "manifestVersion": 1,
                "models": [
                    {
                        "id": "encoder.onnx",
                        "version": "1",
                        "size": 70108816,
                        "sha256": "5022b2eca5b19d1bc104fcf33e26bc32604b7df553cd2e1f62e31dc7b05e9c87",
                        "sourceFilename": "encoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx",
                        "targetFilename": "encoder.onnx",
                        "downloadUrl": "https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-en-2023-06-26/resolve/main/encoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx"
                    },
                    {
                        "id": "decoder.onnx",
                        "version": "1",
                        "size": 540688,
                        "sha256": "780c63ee94c7cfa314211172e5d09b406c0da2beab5c40ea2f54cc95670b76a5",
                        "sourceFilename": "decoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx",
                        "targetFilename": "decoder.onnx",
                        "downloadUrl": "https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-en-2023-06-26/resolve/main/decoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx"
                    },
                    {
                        "id": "joiner.onnx",
                        "version": "1",
                        "size": 259416,
                        "sha256": "abd5e30f3f16fc510605c6029dba33f10e4386bd75c5bdc30cf94076864db10d",
                        "sourceFilename": "joiner-epoch-99-avg-1-chunk-16-left-128.int8.onnx",
                        "targetFilename": "joiner.onnx",
                        "downloadUrl": "https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-en-2023-06-26/resolve/main/joiner-epoch-99-avg-1-chunk-16-left-128.int8.onnx"
                    },
                    {
                        "id": "tokens.txt",
                        "version": "1",
                        "size": 5048,
                        "sha256": "49e3c2646595fd907228b3c6787069658f67b17377c60aeb8619c4551b2316fb",
                        "sourceFilename": "tokens.txt",
                        "targetFilename": "tokens.txt",
                        "downloadUrl": "https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-en-2023-06-26/resolve/main/tokens.txt"
                    },
                    {
                        "id": "silero_vad.onnx",
                        "version": "1",
                        "size": 2327524,
                        "sha256": "1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3",
                        "sourceFilename": "silero_vad.onnx",
                        "targetFilename": "silero_vad.onnx",
                        "downloadUrl": "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
                    }
                ]
            };
            fs.writeFileSync(this.manifestPath, JSON.stringify(defaultManifest, null, 2));
        }
        const manifestJSON = fs.readFileSync(this.manifestPath, 'utf8');
        return JSON.parse(manifestJSON);
    }

    get_model_path(filename) {
        return path.join(this.cacheRoot, 'models', filename);
    }

    get_manifest_dir() {
        return path.dirname(this.manifestPath);
    }

    get_installed_models_path() {
        return this.installedModelsPath;
    }

    get_checksums_path() {
        return this.checksumsPath;
    }

    async verify_model(modelEntry, manifestHash = 'unknown') {
        const modelPath = this.get_model_path(modelEntry.targetFilename || modelEntry.id);
        if (!fs.existsSync(modelPath)) {
            return false;
        }

        const stat = fs.statSync(modelPath);
        const cacheKey = `${manifestHash}_${stat.size}_${stat.mtimeMs}`;
        
        const loaded = this.load_checksums();
        const cache = loaded.cache || {};

        if (cache[modelEntry.id] && cache[modelEntry.id].key === cacheKey) {
            return cache[modelEntry.id].hash === modelEntry.sha256;
        } else {
            console.log(`[CACHE MISS] model=${modelEntry.id} key_wanted=${cacheKey} key_found=${cache[modelEntry.id]?.key}`);
        }

        const hash = await this.compute_sha256(modelPath);
        
        const latestLoaded = this.load_checksums();
        latestLoaded.cache = latestLoaded.cache || {};
        latestLoaded.cache[modelEntry.id] = { key: cacheKey, hash: hash };
        this.save_checksums(latestLoaded.files, latestLoaded.cache);

        return hash === modelEntry.sha256;
    }

    async download_model(modelEntry, onProgress = () => {}) {
        const url = modelEntry.downloadUrl || modelEntry.url;
        const targetFilename = modelEntry.targetFilename || modelEntry.id;
        const sourceFilename = modelEntry.sourceFilename || modelEntry.id;
        const targetPath = this.get_model_path(targetFilename);
        const tempPath = path.join(this.cacheRoot, 'temp', sourceFilename + '.' + Date.now() + '.tmp');
        const resolved = this.resolve_model_url(url);

        this.ensure_cache_dirs();

        try {
            console.log(`[DOWNLOAD] ${sourceFilename}`);
            if (fs.existsSync(tempPath)) {
                fs.unlinkSync(tempPath);
            }
            if (resolved.startsWith('file://')) {
                const sourcePath = resolved.replace('file://', '');
                if (!fs.existsSync(sourcePath)) {
                    throw new Error(`Local model source does not exist: ${sourcePath}`);
                }
                fs.copyFileSync(sourcePath, tempPath);
                onProgress({ id: modelEntry.id, downloaded: Number(modelEntry.size), total: Number(modelEntry.size) });
            } else {
                const response = await fetch(resolved);
                if (!response.ok) {
                    throw new Error(`Failed to download model ${modelEntry.id}: ${response.statusText}`);
                }

                const total = Number(response.headers.get('content-length') || 0);
                let downloaded = 0;
                const fileStream = fs.createWriteStream(tempPath);
                
                const { Readable } = require('stream');
                const webStream = response.body;
                // If it's a web stream (Node 18+), convert it; if it's already a node stream (node-fetch), just use it
                const nodeStream = typeof webStream.on === 'function' ? webStream : Readable.fromWeb(webStream);
                
                nodeStream.on('data', (chunk) => {
                    downloaded += chunk.length;
                    onProgress({ id: modelEntry.id, downloaded, total });
                });
                await pipeline(nodeStream, fileStream);
            }

            console.log(`[VERIFY SHA256]`);
            await this.verify_download(tempPath, modelEntry.sha256);
            console.log(`[NORMALIZE] ${sourceFilename} -> ${targetFilename}`);
            fs.renameSync(tempPath, targetPath);

            const stat = fs.statSync(targetPath);
            const cacheKey = `unknown_${stat.size}_${stat.mtimeMs}`; // manifestHash will be updated on next verify
            const loaded = this.load_checksums();
            loaded.cache = loaded.cache || {};
            loaded.cache[modelEntry.id] = { key: cacheKey, hash: modelEntry.sha256 };
            this.save_checksums(loaded.files, loaded.cache);

            this.save_model_metadata(modelEntry);
            return targetPath;
        } catch (err) {
            if (fs.existsSync(tempPath)) {
                fs.unlinkSync(tempPath);
            }
            throw err;
        }
    }

    async verify_download(filePath, expectedSha) {
        const sha = await this.compute_sha256(filePath);
        if (sha !== expectedSha) {
            fs.unlinkSync(filePath);
            throw new Error('Checksum mismatch for downloaded model');
        }
    }

    remove_corrupted(modelEntry) {
        const targetPath = this.get_model_path(modelEntry.targetFilename || modelEntry.id);
        if (fs.existsSync(targetPath)) {
            fs.unlinkSync(targetPath);
        }
        const tempPath = path.join(this.cacheRoot, 'temp', modelEntry.sourceFilename || modelEntry.id);
        if (fs.existsSync(tempPath)) {
            fs.unlinkSync(tempPath);
        }
    }

    async retry_download(modelEntry, attempts = 3, onProgress = () => {}) {
        let delay = 1000;
        for (let attempt = 1; attempt <= attempts; attempt += 1) {
            try {
                return await this.download_model(modelEntry, onProgress);
            } catch (err) {
                if (attempt === attempts) {
                    throw err;
                }
                await new Promise((resolve) => setTimeout(resolve, delay));
                delay *= 2;
            }
        }
    }

    async compute_sha256(filePath) {
        return new Promise((resolve, reject) => {
            const hash = crypto.createHash('sha256');
            const rs = fs.createReadStream(filePath);
            rs.on('error', reject);
            rs.on('data', (chunk) => hash.update(chunk));
            rs.on('end', () => resolve(hash.digest('hex')));
        });
    }

    ensure_cache_dirs() {
        const dirs = [path.join(this.cacheRoot, 'models'), path.join(this.cacheRoot, 'temp'), this.metadataRoot];
        for (const dir of dirs) {
            if (!fs.existsSync(dir)) {
                fs.mkdirSync(dir, { recursive: true });
            }
        }
    }

    resolve_model_url(url) {
        if (!url) throw new Error('Missing downloadUrl for model');
        if (url.startsWith('file://')) {
            return url;
        }
        if (url.startsWith('http://') || url.startsWith('https://')) {
            return url;
        }
        // Throw instead of returning package relative path, since we now strictly require remote or explicit file://
        throw new Error(`Unsupported model download URL scheme: ${url}`);
    }

    async validate_manifest_urls() {
        if (this._manifestValidated) return true;
        
        const manifest = await this.load_manifest();
        
        this.ensure_cache_dirs();
        const manifestHashPath = path.join(this.metadataRoot, 'manifest_hash.json');
        const manifestHash = crypto.createHash('sha256').update(JSON.stringify(manifest)).digest('hex');

        if (fs.existsSync(manifestHashPath)) {
            try {
                const cached = JSON.parse(fs.readFileSync(manifestHashPath, 'utf8'));
                if (cached.hash === manifestHash) {
                    this._manifestValidated = true;
                    return true;
                }
            } catch (e) {}
        }
        for (const model of manifest.models) {
            const url = model.downloadUrl;
            if (!url) {
                throw new Error(`Model ${model.id} is missing downloadUrl`);
            }
            if (!model.sha256) {
                throw new Error(`Model ${model.id} is missing sha256`);
            }
            if (!model.targetFilename) {
                throw new Error(`Model ${model.id} is missing targetFilename`);
            }
            if (url.startsWith('file://')) {
                continue; // Skip validation for local files during dev/test if any, though Phase 10 wants GitHub
            }
            
            // Validation passes for any http/https URLs that respond to HEAD
            try {
                const res = await fetch(url, { method: 'HEAD', redirect: 'follow' });
                if (res.status === 404) {
                    throw new Error(`Model ${model.id} URL returned 404 Not Found: ${url}`);
                }
                if (!res.ok) {
                    throw new Error(`Model ${model.id} URL returned ${res.status}: ${url}`);
                }
                
                const contentLength = res.headers.get('content-length');
                if (contentLength === '0' || contentLength === 0) {
                    throw new Error(`Model ${model.id} URL returned content-length 0: ${url}`);
                }
            } catch (err) {
                throw new Error(`Model ${model.id} URL validation failed: ${err.message}`);
            }
        }
        
        try { fs.writeFileSync(manifestHashPath, JSON.stringify({ hash: manifestHash }, null, 2)); } catch (e) {}
        this._manifestValidated = true;
        return true;
    }

    async verify_models() {
        this.ensure_cache_dirs();
        const manifest = await this.load_manifest();
        const manifestHash = crypto.createHash('sha256').update(JSON.stringify(manifest)).digest('hex');
        const missing = [];
        
        const results = await Promise.all(manifest.models.map(async (modelEntry) => {
            const ok = await this.verify_model(modelEntry, manifestHash);
            return { modelEntry, ok };
        }));

        for (const { modelEntry, ok } of results) {
            if (!ok) {
                missing.push(modelEntry);
                this.remove_corrupted(modelEntry);
            }
        }
        return missing;
    }

    async verifyOrDownload(onProgress = () => {}) {
        const manifest = await this.load_manifest();
        const manifestHash = crypto.createHash('sha256').update(JSON.stringify(manifest)).digest('hex');
        const missingModels = [];
        
        const results = await Promise.all(manifest.models.map(async (modelEntry) => {
            const valid = await this.verify_model(modelEntry, manifestHash);
            return { modelEntry, valid };
        }));

        for (const { modelEntry, valid } of results) {
            if (!valid) {
                missingModels.push(modelEntry);
            }
        }

        for (const modelEntry of missingModels) {
            await this.retry_download(modelEntry, 3, onProgress);
        }

        return missingModels.map((entry) => this.get_model_path(entry.targetFilename || entry.id));
    }

    load_installed_models() {
        if (!fs.existsSync(this.installedModelsPath)) {
            return { models: [] };
        }
        return JSON.parse(fs.readFileSync(this.installedModelsPath, 'utf8'));
    }

    save_installed_models(data) {
        fs.writeFileSync(this.installedModelsPath, JSON.stringify(data, null, 2), 'utf8');
    }

    load_checksums() {
        if (!fs.existsSync(this.checksumsPath)) {
            return { files: {}, cache: {} };
        }
        try {
            const data = JSON.parse(fs.readFileSync(this.checksumsPath, 'utf8'));
            return { files: data.files || {}, cache: data.cache || {} };
        } catch (e) {
            return { files: {}, cache: {} };
        }
    }

    save_checksums(files, cache) {
        fs.writeFileSync(this.checksumsPath, JSON.stringify({ files, cache }, null, 2), 'utf8');
    }

    save_model_metadata(modelEntry) {
        const installed = this.load_installed_models();
        const existing = installed.models.find((model) => model.id === modelEntry.id);
        const entry = {
            id: modelEntry.id,
            installedVersion: modelEntry.version,
            latestVersion: modelEntry.version,
            status: 'installed',
        };
        if (existing) {
            Object.assign(existing, entry);
        } else {
            installed.models.push(entry);
        }
        this.save_installed_models(installed);

        const loaded = this.load_checksums();
        loaded.files[path.join('models', modelEntry.id)] = modelEntry.sha256;
        this.save_checksums(loaded.files, loaded.cache);
    }
}

module.exports = { ModelManager };
