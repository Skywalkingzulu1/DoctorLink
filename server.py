#!/usr/bin/env python3
"""
Simple static file server for Doctors on Wheels.
Serves the static HTML/JS/CSS files directly without any backend.
"""

import http.server
import socketserver
import os

PORT = 9000


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"))
print(f"Serving Doctors on Wheels at http://localhost:{PORT}")
print("Open your browser to use the app!")

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    httpd.serve_forever()
