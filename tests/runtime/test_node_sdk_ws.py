import asyncio
import sys
import os
import time
import subprocess

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from runtime.transport.websocket_server import WSServer

def run_tests():
    print("Starting WSServer...")
    server = WSServer(host="127.0.0.1", port=0)
    server.start_in_thread()
    time.sleep(0.5)
    
    port = server.port
    print(f"Server started at ws://127.0.0.1:{port}")

    node_script = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "sdk", "test_client.js")
    
    # Create the node test script dynamically if it doesn't exist
    with open(node_script, "w") as f:
        f.write("""
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
""")

    try:
        proc = subprocess.Popen(["node", node_script, str(port)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Wait for Node client to connect
        time.sleep(1)
        
        # Broadcast
        server.broadcast({"type": "wake", "payload": {"foo": "bar"}})
        
        stdout, stderr = proc.communicate(timeout=5)
        
        if proc.returncode != 0:
            print("FAIL")
            print("STDOUT:", stdout)
            print("STDERR:", stderr)
            sys.exit(1)
        else:
            print("PASS")
            print(stdout)
            
    finally:
        server.stop()

if __name__ == "__main__":
    run_tests()
