"""Minimal SPA static file server for TRILOK TRACE preview."""
import http.server
import os
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5173
DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist")
# Resolve to absolute path
DIRECTORY = os.path.abspath(DIRECTORY)

class SPAHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        # Serve the file if it exists, otherwise serve index.html (SPA fallback)
        path = self.translate_path(self.path)
        if not os.path.exists(path) or os.path.isdir(path) and not os.path.exists(os.path.join(path, "index.html")):
            self.path = "/index.html"
        return super().do_GET()

    def log_message(self, format, *args):
        pass  # Suppress logs

if __name__ == "__main__":
    with http.server.HTTPServer(("127.0.0.1", PORT), SPAHandler) as httpd:
        print(f"Serving TRILOK TRACE on http://127.0.0.1:{PORT}")
        httpd.serve_forever()
