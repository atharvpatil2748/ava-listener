const { AVAListener } = require('ava-listener');
console.log('[BOOTSTRAP]');
const listener = new AVAListener({ profileName: 'test_profile' });

listener.on('ready', () => {
    console.log('ARVSAL READY');
    process.exit(0);
});

listener.on('error', (err) => {
    console.error(err);
    process.exit(1);
});

listener.start().catch(err => {
    console.error(err);
    process.exit(1);
});
