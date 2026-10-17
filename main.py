"""
Root entrypoint to run the Autonomous Logistics Agent Backend.
Supports deployment platforms by dynamically honoring PORT and HOST environment variables.
"""

import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"Launching Autonomous Logistics Pipeline Server on http://{host}:{port} ...")
    uvicorn.run("api:app", host=host, port=port, reload=False)
