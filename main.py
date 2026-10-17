"""
Root entrypoint to run the Autonomous Logistics Agent Backend.
"""

import uvicorn

if __name__ == "__main__":
    print("Launching Autonomous Logistics Pipeline Server on http://127.0.0.1:8000 ...")
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)

