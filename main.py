#!/usr/bin/env python3
"""Academic Resource Downloader - Entry Point"""
import os
import traceback

# Change to project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    try:
        import uvicorn
        uvicorn.run(
            "backend.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True
        )
    except Exception:
        print("Error occurred:")
        traceback.print_exc()
        input("\nPress Enter to exit...")