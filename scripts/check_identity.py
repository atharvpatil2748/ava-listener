import os, sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

FORBIDDEN = ['arvsal', 'jarvis', 'friday']
SCAN_DIRS = [
    'ava-listener/core',
    'ava-listener/detection',
    'ava-listener/confidence',
    'ava-listener/decision',
    'ava-listener/audio',
    'ava-listener/asr',
    'ava-listener/integration',
    'ava-listener/runtime',
]

violations = []
for scan_dir in SCAN_DIRS:
    for root, dirs, files in os.walk(scan_dir):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if not f.endswith('.py'):
                continue
            path = os.path.join(root, f)
            with open(path, encoding='utf-8') as fh:
                in_triple = False
                for lineno, line in enumerate(fh.readlines(), 1):
                    stripped = line.strip()
                    # skip comment lines
                    if stripped.startswith('#'):
                        continue
                    # toggle triple-quote docstrings
                    cnt = stripped.count('"""')
                    if cnt >= 2:
                        pass  # docstring opens and closes on one line
                    elif cnt == 1:
                        in_triple = not in_triple
                    if in_triple:
                        continue
                    # check only executable lines
                    for name in FORBIDDEN:
                        if name in line.lower():
                            violations.append(f'{path}:{lineno}: {line.rstrip()}')

if violations:
    print(f'VIOLATIONS FOUND ({len(violations)}):')
    for v in violations[:20]:
        print(' ', v)
else:
    print('PASS: zero assistant name violations in engine-layer EXECUTABLE code')
