# tests/conftest.py
import os, sys

# Put the repo root (directory that contains cca8_world_graph.py) on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
