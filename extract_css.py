import json
import base64
import zlib
import re

html_path = '/home/cybrosys/Downloads/Odoo Subscriptions Portal(1).html'

with open(html_path, 'r') as f:
    html_content = f.read()

# Find the manifest
manifest_match = re.search(r'<script type="__bundler/manifest">(.*?)</script>', html_content, re.DOTALL)

if manifest_match:
    manifest = json.loads(manifest_match.group(1))
    
    # Extract assets
    for uuid, entry in manifest.items():
        data = base64.b64decode(entry['data'])
        if entry.get('compressed'):
            # Decompress gzip
            # zlib.decompress with wbits=31 handles gzip
            data = zlib.decompress(data, 31)
        
        if entry['mime'] == 'text/css':
            print(f"--- CSS {uuid} ---")
            print(data.decode('utf-8'))
            print("\n")
else:
    print("No manifest found.")
