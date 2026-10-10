"""Run an audited exam on localhost. Python 3.10+, no third-party packages."""

import argparse
import hmac
import json
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from exam_game import ConflictError, ExamGame
from question_bank_data import validate_game_bank

ASSET_DIR = Path(__file__).resolve().parents[1] / "assets" / "exam-game"
ASSETS = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
          "/style.css": ("style.css", "text/css")}


class SessionLease:
    """An OS file lock prevents two servers from overwriting the same session."""
    def __init__(self, path):
        self.file = path.open("a+b")
        try:
            self.file.seek(0, 2)
            if self.file.tell() == 0:
                self.file.write(b"0")
                self.file.flush()
            self.file.seek(0)
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise ValueError("This game directory is already in use by another server") from None

    def close(self):
        self.file.close()


class GameServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, exam_path, port=0):
        exam_path = Path(exam_path).resolve()
        with exam_path.open(encoding="utf-8") as source:
            bank = json.load(source)
        validate_game_bank(bank)
        session_path = exam_path.with_name("session.json")
        if exam_path == session_path:
            raise ValueError("Name the exam file exam.json, not session.json")
        self.lease = SessionLease(exam_path.with_name("session.lock"))
        try:
            super().__init__(("127.0.0.1", port), GameHandler)
            self.game = ExamGame(bank, session_path)
        except Exception:
            self.lease.close()
            if hasattr(self, "socket"):
                self.socket.close()
            raise
        self.token = secrets.token_urlsafe(32)
        self.origin = f"http://127.0.0.1:{self.server_port}"

    def server_close(self):
        super().server_close()
        self.lease.close()


class GameHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _send(self, status, body, content_type="application/json"):
        if content_type == "application/json":
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def _local_request(self):
        if self.headers.get("Host") != urlsplit(self.server.origin).netloc:
            self._send(403, {"error": "Use the localhost address printed by the server"})
            return False
        origin = self.headers.get("Origin")
        if (origin is not None and origin != self.server.origin) or self.headers.get("Sec-Fetch-Site") == "cross-site":
            self._send(403, {"error": "Requests must originate from this local game"})
            return False
        return True

    def do_GET(self):
        if not self._local_request():
            return
        path = urlsplit(self.path).path
        if path == "/api/state":
            view = self.server.game.view()
            view["csrf_token"] = self.server.token
            self._send(200, view)
        elif path in ASSETS:
            filename, kind = ASSETS[path]
            try:
                self._send(200, (ASSET_DIR / filename).read_bytes(), kind)
            except OSError:
                self._send(500, {"error": "Game assets are missing; restore the installed skill assets"})
        else:
            self._send(404, {"error": "Not found"})

    def do_POST(self):
        # Consume a bounded body before replying. Closing a rejected request with
        # unread bytes can reset the connection before Windows clients read it.
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1048576:
                raise ValueError("Invalid request size")
            self.connection.settimeout(5)
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("Incomplete request body")
        except (ValueError, OSError) as error:
            self._send(400, {"error": str(error)})
            return
        if not self._local_request():
            return
        if urlsplit(self.path).path != "/api/action":
            self._send(404, {"error": "Not found"})
            return
        token = self.headers.get("X-CSRF-Token", "")
        if not hmac.compare_digest(token, self.server.token):
            self._send(403, {"error": "Refresh the page to reconnect to this game"})
            return
        if self.headers.get_content_type() != "application/json":
            self._send(415, {"error": "Actions must use application/json"})
            return
        try:
            request = json.loads(body.decode("utf-8"))
            self._send(200, self.server.game.action(request))
        except ConflictError as error:
            self._send(409, {"error": str(error), "state": self.server.game.view()})
        except (ValueError, TypeError, UnicodeError) as error:
            self._send(400, {"error": str(error)})
        except OSError:
            self._send(500, {"error": "Could not save the session. Check directory access and disk space, then retry."})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exam_json", help="Audited HTML bank; its directory must be writable")
    parser.add_argument("--port", type=int, default=0, help="Local port; 0 chooses an available port")
    parser.add_argument("--validate-only", action="store_true", help="Check the bank without starting or resetting a session")
    args = parser.parse_args()
    try:
        if not 0 <= args.port <= 65535:
            raise ValueError("Port must be between 0 and 65535")
        if args.validate_only:
            with Path(args.exam_json).open(encoding="utf-8") as source:
                validate_game_bank(json.load(source))
            print("HTML exam bank is structurally valid; factual audit remains the author's responsibility.")
            return
        with GameServer(args.exam_json, args.port) as server:
            print(f"Open {server.origin}", flush=True)
            print("Fresh session started. Share this browser screen; Ctrl+C stops the server.", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
    except (ValueError, OSError) as error:
        parser.exit(1, f"Cannot start exam: {error}\n")


if __name__ == "__main__":
    main()
