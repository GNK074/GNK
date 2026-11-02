#!/usr/bin/env python3
import os,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
env=dict(os.environ,PYTHONPATH=str(root/'backend'))
raise SystemExit(subprocess.call([sys.executable,'-m','pytest',str(root/'tests/integration/test_multi_user.py'),'-q'],env=env,cwd=root))
