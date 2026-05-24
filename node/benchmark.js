const fs = require('fs');
const path = require('path');
const os = require('os');
const logger = require('./utils/logger');

class Benchmark {
    constructor() {
        this.metrics = {};
        this.timestamps = {};
    }

    mark(name) {
        this.timestamps[name] = process.hrtime.bigint();
        logger.info(`[BENCHMARK] Timestamp marked: ${name}`);
    }

    measure(metricName, startMark, endMark) {
        if (this.timestamps[startMark] && this.timestamps[endMark]) {
            const duration = Number(this.timestamps[endMark] - this.timestamps[startMark]) / 1e6;
            this.metrics[metricName] = duration;
            logger.info(`[BENCHMARK] ${metricName}: ${duration.toFixed(2)}ms`);
            return duration;
        }
        return null;
    }

    setMetric(metricName, value) {
        this.metrics[metricName] = value;
    }

    getMetric(metricName) {
        return this.metrics[metricName];
    }

    export(outputPath = 'benchmark_results.json') {
        try {
            fs.writeFileSync(outputPath, JSON.stringify(this.metrics, null, 2), 'utf8');
            logger.info(`[BENCHMARK] Results exported to ${outputPath}`);
        } catch (e) {
            logger.error(`[BENCHMARK] Failed to export results: ${e.message}`);
        }
    }
}

module.exports = new Benchmark();
