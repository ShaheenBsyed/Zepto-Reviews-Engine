"""
api/index.py
=============
Vercel serverless function entry point for the Zepto AI Review Engine dashboard.

This file wraps the Flask application so it can be deployed as a serverless
function on Vercel. All requests are routed through this handler.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.output.dashboard import app

app = app
