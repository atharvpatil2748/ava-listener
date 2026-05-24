# Contributing to AVA-Listener

We welcome contributions to AVA-Listener! Please follow these guidelines to ensure a smooth workflow.

## Development Workflow

1. **Fork and Clone**: Fork the repository and clone it to your local machine.
2. **Install Dependencies**: Run `npm install` in the root and ensure Python >= 3.10 is installed.
3. **Branch Naming**: Create a branch using the format `feature/your-feature-name` or `bugfix/issue-description`.
4. **Testing**: Run all benchmark and validation tests before submitting. Ensure that changes do not regress startup latency.
   ```bash
   node node/tests/phase11/startup_benchmark_test.js
   ```
5. **Pull Requests**: Submit a PR against the `main` branch. Provide a clear description of the changes and any evidence of benchmark improvements if modifying the runtime.

## Code Style

- **JavaScript**: Follow standard Node.js style guidelines. Use ES6 features where applicable.
- **Python**: Follow PEP 8 guidelines.

## Bug Reports and Feature Requests

Please use the provided GitHub issue templates when reporting bugs or requesting new features. Include detailed replication steps and system logs for bug reports.
