const path = require('path');
const fs = require('fs');

class PathManager {
    static get_package_root() {
        return path.resolve(__dirname, '..');
    }

    static get_runtime_entry() {
        const packageRoot = this.get_package_root();

        const runtimeEntry = path.join(
            packageRoot,
            "runtime",
            "main.py"
        );

        if (!fs.existsSync(runtimeEntry)) {
            throw new Error(
                `Runtime entry missing: ${runtimeEntry}`
            );
        }

        return runtimeEntry;
    }

    static get_profile_dir() {
        return path.join(this.get_package_root(), 'profiles');
    }

    static get_model_manifest_dir() {
        return path.join(this.get_package_root(), 'models', 'manifests');
    }
}

module.exports = { PathManager };
