const { AVAListener } = require('../../node');
const path = require('path');
const { isolateTest, cleanupTest, recordCycleMetrics } = require('./test_isolation');

async function runCycles(cycles = 10) {
  await isolateTest('repeated_startup');
  try {
    const listener = new AVAListener({ profile: path.join(__dirname, '..', '..', 'profiles', 'jarvis.json') });
    let success = 0;

  for (let i = 0; i < cycles; i++) {
    console.log(`CYCLE ${i+1} start`);
    let ready = false;
    const readyPromise = new Promise((resolve) => {
      listener.once('ready', () => { ready = true; resolve(); });
    });

    try {
      await listener.start();
    } catch (e) {
      console.error('start error', e.message);
    }

    // wait up to 20s for ready
    await Promise.race([readyPromise, new Promise(r => setTimeout(r, 20000))]);
    console.log('state after start:', listener.getState());

    if (listener.getState() === 'READY' || listener.getState() === 'RUNNING') {
      success += 1;
    } else {
      console.warn('Did not reach READY/RUNNING in cycle', i+1);
    }

    // give a short time then stop
    await new Promise(r => setTimeout(r, 500));
    try {
      await listener.stop();
    } catch (e) {
      console.error('stop error', e && e.message);
    }

    // verify cleanup
    const stateAfter = listener.getState();
    console.log('state after stop:', stateAfter);
    if (stateAfter !== 'STOPPED') {
      console.warn('Lifecycle did not reach STOPPED state');
    }

    // small delay before next cycle
    await new Promise(r => setTimeout(r, 500));
    await recordCycleMetrics(i + 1, listener);
  }

  console.log(`CYCLES completed: ${cycles}, success: ${success}`);
  process.exitCode = (success === cycles ? 0 : 2);
  } finally {
      await cleanupTest('repeated_startup');
  }
}

runCycles(10).catch(e => { console.error(e); process.exit(2); });
