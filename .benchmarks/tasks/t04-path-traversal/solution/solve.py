#!/usr/bin/env python3
"""Golden solution — demo solver for harness mechanics."""
import shutil, sys
FILES = ['assets.py']
if __name__ == '__main__':
    repo = sys.argv[1]
    src = __import__('pathlib').Path(__file__).parent
    for f in FILES:
        shutil.copy(src / f, __import__('pathlib').Path(repo) / f)
    print('golden solution applied')
