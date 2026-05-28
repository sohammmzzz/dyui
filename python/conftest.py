import sys
from pathlib import Path

# Ensure the package root (this directory) is importable so tests can do
# ``import dyui`` and ``import examples.agent`` without installing the package.
sys.path.insert(0, str(Path(__file__).parent))
