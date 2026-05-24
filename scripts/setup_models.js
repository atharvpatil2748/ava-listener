const { ModelManager } = require('../node/model_manager');

async function main() {
    console.log("Setting up models...");
    const manager = new ModelManager();
    
    console.log("Validating manifest...");
    await manager.validate_manifest_urls();
    
    console.log("Checking and downloading missing models...");
    let lastId = null;
    const missing = await manager.verifyOrDownload((progress) => {
        if (lastId !== progress.id) {
            if (lastId !== null) console.log(""); // Newline for previous
            lastId = progress.id;
        }
        const percent = ((progress.downloaded / progress.total) * 100).toFixed(1);
        process.stdout.write(`\rDownloading ${progress.id}... ${percent}%`);
    });
    
    if (lastId !== null) console.log(""); // Final newline

    if (missing.length > 0) {
        console.log("Models successfully downloaded and verified.");
    } else {
        console.log("All models are already present and verified.");
    }
}

main().catch(err => {
    console.error("\nSetup failed:", err.message);
    process.exit(1);
});
