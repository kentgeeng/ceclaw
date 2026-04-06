import http.server, json, urllib.request, socketserver, os

CHECKS = [
    ("gateway", "http://localhost:8000/ceclaw/status"),
    ("l1",      "http://localhost:8002/v1/models"),
    ("l2",      "http://192.168.1.91:8001/health"),
    ("searxng", "http://localhost:8888/healthz"),
]

socketserver.TCPServer.allow_reuse_address = True
_HERMES_SESSION_ID = None

def _get_or_create_session():
    global _HERMES_SESSION_ID
    if _HERMES_SESSION_ID:
        return _HERMES_SESSION_ID
    req = urllib.request.Request(
        'http://localhost:8642/api/sessions',
        data=b'{}',
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    r = urllib.request.urlopen(req, timeout=5)
    _HERMES_SESSION_ID = json.loads(r.read())['session']['id']
    return _HERMES_SESSION_ID
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
                    headers={"Authorization": "Bearer 97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759", "Content-Type": "application/json"},
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
                    headers={"Authorization": "Bearer 97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759", "Content-Type": "application/json"},
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
        elif self.path == '/api/hermes-exec':
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)
                data = json.loads(body)
                message = data.get('message', '')
                session_id = _get_or_create_session()
                # 若 session 失效則重建
                try:
                    chk = urllib.request.Request(
                        f'http://localhost:8642/api/sessions/{session_id}',
                        headers={'Content-Type': 'application/json'}
                    )
                    urllib.request.urlopen(chk, timeout=3)
                except:
                    import builtins
                    globals()['_HERMES_SESSION_ID'] = None
                    session_id = _get_or_create_session()
                req2 = urllib.request.Request(
                    f'http://localhost:8642/api/sessions/{session_id}/chat/stream',
                    data=json.dumps({'message': message, 'model': 'ceclaw'}).encode(),
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                r2 = urllib.request.urlopen(req2, timeout=60)
                text = ''
                tool_calls = []
                for line in r2:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data:'):
                        try:
                            d = json.loads(line[5:])
                            if 'delta' in d:
                                text += d['delta']
                            if d.get('tool_name') and d.get('args'):
                                tool_calls.append(d['tool_name'] + ': ' + str(d.get('args', {})))
                        except:
                            pass
                result = {'text': text, 'tool_calls': tool_calls, 'session_id': session_id}
            except Exception as e:
                result = {'text': '', 'tool_calls': [], 'error': str(e)}
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
