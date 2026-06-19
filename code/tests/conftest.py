"""
Pytest configuration shared by all tests.

- Forces MOCK_MODE so unit tests NEVER hit the network / spend quota.
- Adds the `code/` dir to sys.path so `import config`, `import schema`, etc.
  resolve the same way they do for main.py.
"""
import os
import sys
from pathlib import Path

# Must be set BEFORE config is imported anywhere (config caches MOCK_MODE).
os.environ["LLM_MOCK"] = "1"

CODE_DIR = Path(__file__).resolve().parent.parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
