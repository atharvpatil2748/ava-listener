class RestartRequiredError extends Error {
    constructor(message) {
        super(message);
        this.name = 'RestartRequiredError';
        this.code = 'RESTART_REQUIRED';
    }
}

const HOT_RELOAD_FIELDS = new Set([
    "vad.sileroThreshold",
    "vad.aggressiveness",
    "confidence.defaultThreshold",
    "confidence.emaRiseAlpha",
    "confidence.emaDecayAlpha",
    "confidence.cooldownSeconds",
    "transcription.enableDebug"
]);

const RESTART_REQUIRED_FIELDS = new Set([
    "audio.device",
    "asr.provider",
    "asr.modelPath",
    "vad.provider",
    "transport.type",
    "asr.numThreads",
    "audio.sampleRate",
    "audio.blockSize"
]);

function validateConfigMutation(configPatch) {
    // DFS to extract dot-paths
    const paths = [];
    function walk(obj, currentPath = '') {
        for (const [key, value] of Object.entries(obj)) {
            const p = currentPath ? `${currentPath}.${key}` : key;
            if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                walk(value, p);
            } else {
                paths.push(p);
            }
        }
    }
    walk(configPatch);

    for (const path of paths) {
        if (!HOT_RELOAD_FIELDS.has(path)) {
            throw new RestartRequiredError(`Modifying field '${path}' requires a restart.`);
        }
    }
}

module.exports = { validateConfigMutation, RestartRequiredError };
