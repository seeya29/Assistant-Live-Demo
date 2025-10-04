#!/usr/bin/env python3
\"\"\"
ASGI entry point for deployment
Compatible with Vercel, Railway, Heroku, and other platforms
\"\"\"

from assistant_api.main import app

# For Vercel and other platforms that expect 'app' or 'application'
application = app

if __name__ == \"__main__\":
    import uvicorn
    import os
    
    host = os.getenv(\"API_HOST\", \"0.0.0.0\")
    port = int(os.getenv(\"API_PORT\", \"8000\"))
    
    uvicorn.run(app, host=host, port=port)