"""Serve the website locally with the SAME security headers as production.

  python scripts/serve_web.py            # http://localhost:8000
  python scripts/serve_web.py --port 9000

Headers are read from web/_headers (the file Netlify / Cloudflare Pages use),
so what you test locally is what you deploy.
"""
import argparse
import functools
import http.server
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"


def read_headers(path):
    """Parse the `/*` block of a Netlify/Cloudflare-style _headers file."""
    headers, active = [], False
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith((" ", "\t")):
            active = line.strip() == "/*"
            continue
        if active and ":" in line:
            name, value = line.strip().split(":", 1)
            headers.append((name.strip(), value.strip()))
    return headers


class Handler(http.server.SimpleHTTPRequestHandler):
    extra_headers = []
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".webmanifest": "application/manifest+json",
        ".svg": "image/svg+xml",
    }

    def end_headers(self):
        for name, value in self.extra_headers:
            # Strict-Transport-Security is meaningless (and ignored) on plain http://localhost.
            if name.lower() != "strict-transport-security":
                self.send_header(name, value)
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--bind", default="127.0.0.1", help="use 0.0.0.0 to test from a phone on your Wi-Fi")
    args = parser.parse_args()

    Handler.extra_headers = read_headers(WEB / "_headers")
    handler = functools.partial(Handler, directory=str(WEB))
    with http.server.ThreadingHTTPServer((args.bind, args.port), handler) as server:
        print(f"Serving {WEB} at http://{'localhost' if args.bind == '127.0.0.1' else args.bind}:{args.port}")
        server.serve_forever()


if __name__ == "__main__":
    main()
