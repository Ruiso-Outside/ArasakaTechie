"""Servidor de precos falso para testes e prints:  python tests/fake_price_server.py 8765
Responde como o server/techie/api.php, lendo tests/fixtures/."""
import json
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

FIX = Path(__file__).resolve().parent / "fixtures"


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "index" in q:
            f = FIX / "index.json"
        elif "part" in q:
            f = FIX / f"part-{q['part'][0]}.json"
        else:
            f = None
        if not f or not f.exists() or "/" in q.get("part", [""])[0]:
            body, code = json.dumps({"error": "nao encontrado"}).encode(), 404
        else:
            body, code = f.read_bytes(), 200
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def serve(port: int) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    return srv


if __name__ == "__main__":
    serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8765).serve_forever()
