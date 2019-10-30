from pathlib import Path

# Pull all parsers up to the parent module
for file in Path(__file__).parent.glob('*Parser.py'):
    exec(f'from .{file.stem} import {file.stem}')