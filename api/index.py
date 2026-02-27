import sys
import os

# Add the backend directory to python path so imports like `import database` work
backend_dir = os.path.join(os.path.dirname(__file__), '..', 'backend')
sys.path.append(os.path.abspath(backend_dir))

from backend.main import app

# Vercel requires the app to be named `app`
