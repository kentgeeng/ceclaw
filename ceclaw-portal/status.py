import http.server, json, urllib.request, socketserver, os

CHECKS = [
    ("gateway", "http://localhost:8000/ceclaw/status"),
    ("l1",      "http://localhost:8002/v1/models"),
    ("l2",      "http://192.168.1.91:8001/health"),
    ("searxng", "http://localhost:8888/healthz"),
]

TCPServer.allow_reuse_address = True
class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/status':
            result = {}
            for name, url in CHECKS:
                try:
                    r = urllib.request.urlopen(url, timeout=3)
                    result[name] = r.status < 400
                except:
                    result[name] = False
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Access-Control-Allow-Origin','*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        elif self.path == '/api/knowledge-items':
            try:
                req = urllib.request.Request(
                    "http://localhost:8000/api/knowledge/pending",
                    headers={"Authorization": "Bearer 97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759"}
                )
                r = urllib.request.urlopen(req, timeout=3)
                result = json.loads(r.read())
            except:
                result = {"items": [], "count": -1}
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        elif self.path == '/api/knowledge-pending':
            try:
                req = urllib.request.Request(
                    "http://localhost:8000/api/knowledge/pending",
                    headers={"Authorization": "Bearer 97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759"}
                )
                r = urllib.request.urlopen(req, timeout=3)
                data = json.loads(r.read())
                result = {"count": data.get("count", 0)}
            except:
                result = {"count": -1}
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Access-Control-Allow-Origin','*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        else:
            self.directory = os.path.expanduser('~/ceclaw-portal')
            super().do_GET()

    def do_POST(self):
        if self.path == '/api/knowledge-submit':
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)
                req = urllib.request.Request(
                    "http://localhost:8000/api/knowledge/submit",
                    data=body,
                    headers={
                        "Authorization": "Bearer 97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759",
                        "Content-Type": "application/json"
                    },
                    method="POST"
                )
                r = urllib.request.urlopen(req, timeout=10)
                result = json.loads(r.read())
            except Exception as e:
                result = {"error": str(e)}
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        elif self.path == '/api/knowledge-approve':
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)
                req = urllib.request.Request(
                    "http://localhost:8000/api/knowledge/approve",
                    data=body,
                    headers={
                        "Authorization": "Bearer 97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759",
                        "Content-Type": "application/json"
                    },
                    method="POST"
                )
                r = urllib.request.urlopen(req, timeout=10)
                result = json.loads(r.read())
            except Exception as e:
                result = {"error": str(e)}
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
    def log_message(self, *a): pass

with socketserver.TCPServer(("0.0.0.0", 9000), Handler) as s:
    s.serve_forever()
