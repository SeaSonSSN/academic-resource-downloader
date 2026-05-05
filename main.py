#!/usr/bin/env python3
"""Academic Resource Downloader - Entry Point"""
import os
import uvicorn

# Change to project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )