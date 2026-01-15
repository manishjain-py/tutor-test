#!/usr/bin/env python3
"""
Entry Point for Tutoring Agent POC

This script starts the FastAPI server using uvicorn.
It uses the factory pattern for dependency wiring.

Usage:
    python run.py

Environment Variables:
    - PORT: Server port (default: 8000)
    - HOST: Server host (default: 0.0.0.0)
    - DEBUG: Enable debug mode (default: true)
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def main():
    """Run the tutoring agent server."""
    import uvicorn
    from backend.config import settings
    from backend.logging_config import setup_logging

    # Setup logging first
    setup_logging()

    # Get config from settings or environment
    host = os.environ.get("HOST", settings.host)
    port = int(os.environ.get("PORT", settings.port))
    debug = os.environ.get("DEBUG", str(settings.debug)).lower() == "true"

    print(f"""
    ╔══════════════════════════════════════════════════════════╗
    ║           Tutoring Agent POC - Starting                  ║
    ╠══════════════════════════════════════════════════════════╣
    ║  Environment: {settings.env:<43} ║
    ║  Host: {host:<50} ║
    ║  Port: {port:<50} ║
    ║  Debug: {str(debug):<49} ║
    ╠══════════════════════════════════════════════════════════╣
    ║  Frontend: http://{host}:{port:<32} ║
    ║  API Docs: http://{host}:{port}/docs{' ' * 23}║
    ╚══════════════════════════════════════════════════════════╝
    """)

    # Run the server
    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info" if debug else "warning",
    )


if __name__ == "__main__":
    main()
