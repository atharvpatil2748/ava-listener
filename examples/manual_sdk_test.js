const { AVAListener } = require("../node");
const path = require("path");

async function run() {

    const listener = new AVAListener({
        profile: path.join(
            __dirname,
            "../profiles/jarvis.json"
        ),

        debug: false,

        startPaused: false
    });

    listener.on("ready",()=>{
        console.log("[READY]");
    });

    listener.on("wake",(e)=>{
        console.log("[WAKE]", e);
    });

    listener.on("partialTranscript",(e)=>{
        console.log("[PARTIAL]", e);
    });

    listener.on("health",(e)=>{
        console.log("[HEALTH]", e);
    });

    await listener.start();

    console.log(
        JSON.stringify(
            await listener.getEffectiveConfig(),
            null,
            2
        )
    );

    if (listener.getState() === "PAUSED") {
        await listener.resume();
    }

    console.log("Say something...");

    setTimeout(async ()=>{

        await listener.destroy();
        process.exit(0);

    }, 60000);

}

run().catch(console.error);