const fs = require('fs');
const path = require('path');

const rootDir = process.cwd();
const manifest = [];
const structure = {};

function classify(relPath, isDir) {
  const parts = relPath.split(path.sep).map(p => p.toLowerCase());
  const basename = path.basename(relPath).toLowerCase();
  
  if (parts.includes('.git')) return null;
  if (parts.includes('node_modules')) return 'Generated artifacts';
  if (parts.includes('.venv') || parts.includes('venv') || parts.includes('env')) return 'Local-machine artifacts';
  if (parts.includes('__pycache__') || basename.endsWith('.pyc')) return 'Generated artifacts';
  if (basename.endsWith('.tgz')) return 'Generated artifacts';
  if (parts.includes('cache') || parts.includes('.ava_cache')) return 'Generated artifacts';
  if (parts.includes('models') && basename.endsWith('.onnx')) return 'External model assets';
  if (parts.includes('models') && basename.endsWith('.txt')) return 'External model assets';
  if (basename === '.ds_store') return 'Local-machine artifacts';
  if (basename.endsWith('.log')) return 'Development-only artifacts';
  if (parts.includes('verification_outputs')) return 'Generated artifacts';
  if (parts.includes('temp')) return 'Temporary files';
  
  if (parts[0] === 'node' && parts.includes('tests')) return 'Tests';
  if (parts[0] === 'tests') return 'Tests';
  if (parts[0] === 'node') return 'Package source';
  if (parts[0] === 'runtime' || parts[0] === 'utils') return 'Production runtime';
  if (parts[0] === 'benchmarks') {
    if (basename.endsWith('.md') && basename === 'baseline.md') return 'Benchmarks';
    if (basename === 'benchmarks') return 'Benchmarks';
    if (basename.endsWith('.json')) return 'Generated artifacts';
    return 'Temporary files';
  }
  
  if (parts[0] === '.github') return 'CI/CD';
  
  if (basename === 'package.json') return 'Package source';
  if (basename === 'package-lock.json') return 'Generated artifacts';
  if (basename === 'requirements.txt') return 'Package source';
  if (basename === 'bootstrap.js') return 'Runtime bootstrap';
  if (basename === 'engine.py') return 'Production runtime';
  
  if (basename.endsWith('checkpoint.md') || basename.endsWith('audit.md') || basename.endsWith('report.md') || basename === 'phase_gap_matrix.md' || basename === 'promotion_decision.md') {
      return 'Development-only artifacts';
  }
  
  if (basename.endsWith('.md') || basename === 'license') return 'Documentation';
  if (basename.includes('gitignore') || basename.includes('gitattributes') || basename.includes('npmignore')) return 'CI/CD';

  return 'Development-only artifacts';
}

function walk(dir, structNode) {
  const items = fs.readdirSync(dir);
  for (const item of items) {
    const fullPath = path.join(dir, item);
    const relPath = path.relative(rootDir, fullPath);
    const stat = fs.statSync(fullPath);
    const isDir = stat.isDirectory();
    
    const category = classify(relPath, isDir);
    if (!category) continue;
    
    manifest.push({
      path: relPath.replace(/\\/g, '/'),
      type: isDir ? 'directory' : 'file',
      category: category,
      includeInGit: !['Generated artifacts', 'Local-machine artifacts', 'Temporary files', 'External model assets'].includes(category)
    });
    
    if (isDir) {
      structNode[item] = {};
      walk(fullPath, structNode[item]);
    } else {
      structNode[item] = category;
    }
  }
}

walk(rootDir, structure);

fs.writeFileSync('upload_manifest.json', JSON.stringify(manifest, null, 2));

function generateMarkdown(node, indent = 0) {
  let md = '';
  const spaces = '  '.repeat(indent);
  for (const key of Object.keys(node).sort()) {
    if (typeof node[key] === 'object') {
      md += `${spaces}- **${key}/**\n`;
      md += generateMarkdown(node[key], indent + 1);
    } else {
      md += `${spaces}- ${key} \`[${node[key]}]\`\n`;
    }
  }
  return md;
}

const repoStruct = `# Repository Structure\n\n${generateMarkdown(structure)}`;
fs.writeFileSync('repository_structure.md', repoStruct);
console.log("Done generating manifest and structure.");
