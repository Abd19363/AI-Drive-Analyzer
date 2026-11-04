import os
import sys
from pathlib import Path

# Add the backend directory (which contains the 'app' package) to the Python module search path
backend_path = Path(__file__).parent
if str(backend_path) not in sys.path:
    sys.path.append(str(backend_path))

# Optional: load environment variables from the .env file in the backend folder
from dotenv import load_dotenv
load_dotenv(dotenv_path=backend_path / ".env")

# Run the FastAPI application using uvicorn
if __name__ == "__main__":
    # uvicorn will look for the ASGI app at app.main:app
    # The '--reload' flag enables auto‑reload during development
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

