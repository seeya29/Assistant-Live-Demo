"""
Legacy shim: import unified Assistant API app
This preserves compatibility with commands like `uvicorn api.main:app`.
"""

from assistant_api.main import app

# For platforms that expect 'app' or 'application'
application = app