import hashlib, os, json

models_dir = r'c:\Users\athar\Desktop\AVA-Listener\ava-listener\models'
manifest = []

files = ['encoder.onnx', 'decoder.onnx', 'joiner.onnx', 'tokens.txt', 'silero_vad.onnx']
for fname in files:
    p = os.path.join(models_dir, fname)
    if os.path.exists(p):
        sha256 = hashlib.sha256(open(p, 'rb').read()).hexdigest()
        size = os.path.getsize(p)
        manifest.append({
            'name': fname,
            'path': p.replace('\\', '/'),
            'sha256': sha256,
            'size_bytes': size,
            'load_status': 'OK'
        })
    else:
        manifest.append({
            'name': fname,
            'path': p,
            'sha256': None,
            'size_bytes': 0,
            'load_status': 'MISSING'
        })

out = os.path.join(r'c:\Users\athar\Desktop\AVA-Listener\ava-listener', 'models_manifest.json')
json.dump({'models': manifest}, open(out, 'w'), indent=2)
print('models_manifest.json written')
for m in manifest:
    sha_preview = m['sha256'][:16] + '...' if m['sha256'] else 'N/A'
    print(f"  {m['name']:<30}  {m['size_bytes']//1024:>8} KB  {sha_preview}")
