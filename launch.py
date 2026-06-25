import os

import uvicorn

from app import app


if __name__ == "__main__":
    # Hugging Face may expose PORT internally; this app must bind to the standard Space port.
    # Use APP_PORT only if you intentionally need to override it.
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("APP_PORT", "7860")))
