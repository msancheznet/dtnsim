from pathlib import Path

# Pull all reports up to the parent module
for file in Path(__file__).parent.glob('*Report.py'):
    exec(f'from .{file.stem} import {file.stem}')