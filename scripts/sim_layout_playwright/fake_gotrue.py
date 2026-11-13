# Fake GoTrue + PostgREST for the app audit harness (see docs/audits/2026-11-ui-audit-2.md, Audit 5).
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
SAVED_LEAGUE = {"user_id": "11111111-1111-1111-1111-111111111111", "league_id": "1221647449446162432", "league_name": "Donk Dynasty", "is_default": True, "season": "2026", "platform": "sleeper"}


class H(BaseHTTPRequestHandler):
    def _send(self, body, code=200):
        data = json.dumps(body).encode()
        self.send_response(code); self.send_header("content-type","application/json"); self.send_header("access-control-allow-origin","*"); self.send_header("content-length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        if self.path.startswith("/auth/v1/user"):
            return self._send({"id":"11111111-1111-1111-1111-111111111111","email":"t@example.com","aud":"authenticated","role":"authenticated","app_metadata":{},"user_metadata":{},"created_at":"2026-01-01T00:00:00Z"})
        # FAKE_LINKED=1: a linked account (Sleeper username + one saved league); FAKE_ENTITLEMENT=pro for the paid tier.
        if os.environ.get("FAKE_LINKED") == "1":
            uid = "11111111-1111-1111-1111-111111111111"
            if self.path.startswith("/rest/v1/profiles"):
                return self._send([{"user_id": uid, "email": "t@example.com", "display_name": "Test", "sleeper_username": "donk", "entitlement": os.environ.get("FAKE_ENTITLEMENT", "free")}])
            if self.path.startswith("/rest/v1/saved_leagues"):
                return self._send([SAVED_LEAGUE])
        return self._send([])
    def do_POST(self): self.rfile.read(int(self.headers.get("content-length",0) or 0)); self._send([])
    do_PATCH = do_POST; do_DELETE = do_POST; do_PUT = do_POST
    def log_message(self,*a): pass
HTTPServer(("127.0.0.1", 9999), H).serve_forever()
