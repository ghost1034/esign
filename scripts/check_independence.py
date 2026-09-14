"""Reject external platform coupling in the tracked application and manifests."""
from pathlib import Path
import re
root = Path(__file__).resolve().parents[1]
patterns = [r'cpaautomation', r'bytereview', r'CPAA_', r'X-CPAA-', r'services\.analytics', r'@/.*(?:analytics|firmcrm|billing)', r'/api/(?:analytics|stripe|billing|sign/|guest/)', r'/dashboard', r'(?:file:|link:).*\.\./', r'/Users/[^/]+/projects/']
exclude = {'.git', '.next', '.venv', 'node_modules', '__pycache__', '.local', '.pytest_cache', 'test-results', 'playwright-report'}
failures = []
for p in root.rglob('*'):
    if any(part in exclude for part in p.relative_to(root).parts): continue
    if p.is_symlink(): failures.append(f'{p.relative_to(root)}: symlinks are not allowed'); continue
    if p.suffix not in {'.ts', '.tsx', '.js', '.mjs', '.py', '.json', '.sh', '.yml', '.yaml', '.md', '.toml', '.txt'} or p == Path(__file__): continue
    for number, line in enumerate(p.read_text().splitlines(), 1):
        if any(re.search(pattern, line, re.I) for pattern in patterns): failures.append(f'{p.relative_to(root)}:{number}')
if failures: raise SystemExit('Independence violations:\n' + '\n'.join(failures))
print('Independence check passed')
