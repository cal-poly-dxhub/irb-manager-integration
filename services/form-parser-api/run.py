#!/usr/bin/env python3
"""Run the Form Parser API server."""

import os
import sys

# Add src to path so we can import the package
src_path = os.path.join(os.path.dirname(__file__), "src")
sys.path.insert(0, src_path)

from form_parser_api.app import app

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the Form Parser API server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5001, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    app.run(host=args.host, port=args.port, debug=args.debug)
