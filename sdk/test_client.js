
const AVAListenerClient = require('./client');

async function run() {
    const port = parseInt(process.argv[2], 10);
    const client = new AVAListenerClient(port, '127.0.0.1');

    client.on('error', (err) => {
        console.error('Client Error:', err);
        process.exit(1);
    });

    client.on('wake', (payload) => {
        console.log('Received wake in Node!');
        client.disconnect();
        process.exit(0);
    });

    await client.connect();
    console.log('Node connected');
    
    // Server will broadcast wake to us, client will auto-ack
}

run().catch(err => {
    console.error(err);
    process.exit(1);
});
