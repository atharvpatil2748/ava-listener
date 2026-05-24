async function withRetry(operation, maxAttempts = 5, baseDelay = 200) {
    let attempt = 0;
    while (attempt < maxAttempts) {
        try {
            return await operation();
        } catch (err) {
            attempt++;
            if (attempt >= maxAttempts) throw err;
            const delay = baseDelay * Math.pow(2, attempt - 1);
            await new Promise(r => setTimeout(r, delay));
        }
    }
}

module.exports = { withRetry };
