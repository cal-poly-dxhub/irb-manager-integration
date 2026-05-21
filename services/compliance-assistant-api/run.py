#!/usr/bin/env python3
"""Run the Compliance Assistant API server."""

import os
import sys

src_path = os.path.join(os.path.dirname(__file__), "src")
sys.path.insert(0, src_path)

from compliance_assistant_api.app import app

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the Compliance Assistant API server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5002, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    app.run(host=args.host, port=args.port, debug=args.debug)
