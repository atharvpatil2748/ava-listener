const fs = require('fs');
const path = require('path');

const rootDir = process.cwd();
const plan = [];

function classify(relPath, isDir) {
  const parts = relPath.split(path.sep).map(p => p.toLowerCase());
  const basename = path.basename(relPath).toLowerCase();
  
  if (parts.includes('.git')) return null;
  if (parts.includes('node_modules')) return { cat: 'E', reason: 'Local dependencies', gh: false, npm: false };
  if (parts.includes('.venv') || parts.includes('venv') || parts.includes('env')) return { cat: 'E', reason: 'Local virtual environment', gh: false, npm: false };
  if (parts.includes('__pycache__') || basename.endsWith('.pyc')) return { cat: 'E', reason: 'Python cache', gh: false, npm: false };
  if (basename === 'ava-listener-0.1.0.tgz' || basename.endsWith('.tgz')) return { cat: 'D', reason: 'Generated package tarball', gh: false, npm: false };
  if (basename.endsWith('.lock') && parts.includes('.ava_cache')) return { cat: 'E', reason: 'Runtime lock file', gh: false, npm: false };
  if (parts.includes('.ava_cache') || (parts.includes('models') && basename.endsWith('.onnx'))) return { cat: 'E', reason: 'Local models/cache', gh: false, npm: false };
  if (basename === '.ds_store') return { cat: 'F', reason: 'OS generated file', gh: false, npm: false };
  if (basename.endsWith('.log')) return { cat: 'D', reason: 'Runtime logs', gh: false, npm: false };
  if (parts.includes('verification_outputs')) return { cat: 'D', reason: 'Local output streams', gh: false, npm: false };
  if (basename === 'audit.js') return null;

  // Core folders
  if (parts[0] === 'node' && parts.includes('tests')) return { cat: 'C', reason: 'Test files', gh: true, npm: false };
  if (parts[0] === 'tests') return { cat: 'C', reason: 'Python tests', gh: true, npm: false };
  if (parts[0] === 'node') return { cat: 'A', reason: 'Node.js core source', gh: true, npm: true };
  if (parts[0] === 'runtime' || parts[0] === 'utils') return { cat: 'A', reason: 'Python core source', gh: true, npm: true };
  if (parts[0] === 'benchmarks') {
    if (basename.endsWith('.md') || basename === 'history.json' || basename === 'manifest.json' || basename === 'final_phase11_report.json' || basename === 'benchmark_table.json' || basename === 'resource_timeline.json' || basename === 'startup_optimization_report.json') {
      return { cat: 'A', reason: 'Baseline benchmark data', gh: true, npm: false };
    }
    return { cat: 'D', reason: 'Temporary benchmark artifact', gh: false, npm: false };
  }
  
  if (parts[0] === '.github') return { cat: 'A', reason: 'GitHub workflows and templates', gh: true, npm: false };
  
  // Root files
  if (basename === 'package.json') return { cat: 'B', reason: 'NPM package metadata', gh: true, npm: true };
  if (basename === 'package-lock.json') return { cat: 'A', reason: 'NPM lockfile', gh: true, npm: false };
  if (basename === 'requirements.txt') return { cat: 'B', reason: 'Python dependencies', gh: true, npm: true };
  if (basename.endsWith('.md') || basename === 'license') return { cat: 'A', reason: 'Documentation', gh: true, npm: true };
  if (basename.includes('gitignore') || basename.includes('npmignore')) return { cat: 'A', reason: 'Ignore configurations', gh: true, npm: true };

  return { cat: 'A', reason: 'Unclassified root/source', gh: true, npm: true };
}

function walk(dir) {
  const items = fs.readdirSync(dir);
  for (const item of items) {
    const fullPath = path.join(dir, item);
    const relPath = path.relative(rootDir, fullPath);
    const stat = fs.statSync(fullPath);
    const isDir = stat.isDirectory();
    
    const classification = classify(relPath, isDir);
    if (classification) {
      plan.push({
        path: relPath.replace(/\\/g, '/'),
        type: isDir ? 'directory' : 'file',
        category: classification.cat,
        reason: classification.reason,
        upload_to_github: classification.gh,
        include_in_npm_package: classification.npm
      });
      
      if (isDir && classification.cat !== 'E') {
        walk(fullPath);
      }
    }
  }
}

walk(rootDir);
fs.writeFileSync('repo_upload_plan.json', JSON.stringify(plan, null, 2));
