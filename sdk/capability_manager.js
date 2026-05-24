class CapabilityUnavailableError extends Error {
    constructor(message) {
        super(message);
        this.name = 'CapabilityUnavailableError';
        this.code = 'CAPABILITY_UNAVAILABLE';
    }
}

class CapabilityManager {
    constructor(capabilities = {}) {
        this.capabilities = { ...capabilities };
    }

    has(name) {
        return !!this.capabilities[name];
    }

    require(name) {
        if (!this.has(name)) {
            throw new CapabilityUnavailableError(`Required capability '${name}' is not available in the current runtime.`);
        }
    }

    getCapabilities() {
        return { ...this.capabilities };
    }
}

module.exports = { CapabilityManager, CapabilityUnavailableError };
