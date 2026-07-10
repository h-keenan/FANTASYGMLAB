import py_compile
import re
from pathlib import Path

py_compile.compile('app.py', doraise=True)
print('app.py compiled')
text = Path('app.py').read_text(encoding='utf-8')
keys = re.findall(r'key\s*=\s*(?:f?"([^\"]+)"|f?\'([^\']+)\'|([A-Za-z_][A-Za-z0-9_]*))', text)
flat = [next(filter(None, k)) for k in keys]
dups = {k: flat.count(k) for k in set(flat) if flat.count(k) > 1}
print('duplicate keys:', dups)
