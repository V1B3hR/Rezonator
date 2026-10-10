"""
HTTP Server & REST API for Błyskawica Mathy.
Serves static Web Studio files and provides JSON endpoints for analysis, comparison, and diffusion.
"""

import json
import hmac
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from rezonator.cobol_parser import CobolParser
from rezonator.program_comparator import ProgramComparator
from rezonator.llm_synthesizer import LLMSynthesizer
from rezonator.limits import ResourceLimitError, MAX_SOURCE_BYTES


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")
EXAMPLES_DIR = os.path.join(BASE_DIR, "examples")
MAX_PAYLOAD_BYTES = MAX_SOURCE_BYTES
REQUEST_TIMEOUT_SECONDS = 30
LOCAL_ALLOWED_ORIGINS = frozenset({
    "null",
    "http://127.0.0.1:8080",
    "http://localhost:8080",
})


class RezonatorHTTPServer(ThreadingHTTPServer):
    """Threaded local server with deterministic connection lifecycle."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, *, mode="local", auth_token=None, allowed_origins=None):
        self.mode = mode
        self.auth_token = auth_token
        super().__init__(server_address, RequestHandlerClass)
        if allowed_origins is None and mode == "local":
            port = self.server_address[1]
            self.allowed_origins = frozenset({
                *LOCAL_ALLOWED_ORIGINS,
                f"http://127.0.0.1:{port}",
                f"http://localhost:{port}",
            })
        else:
            self.allowed_origins = frozenset(allowed_origins or ())


HTTPServer = RezonatorHTTPServer


class RezonatorRequestHandler(SimpleHTTPRequestHandler):
    # Deliberately use request/response isolation. Persistent connections are
    # unnecessary for the local analysis API and complicate failure recovery.
    protocol_version = "HTTP/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def setup(self):
        super().setup()
        self.connection.settimeout(REQUEST_TIMEOUT_SECONDS)

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        return not origin or origin in self.server.allowed_origins

    def _authorized(self) -> bool:
        if self.server.mode == "local":
            return True
        authorization = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not authorization.startswith(prefix) or not self.server.auth_token:
            return False
        return hmac.compare_digest(authorization[len(prefix):], self.server.auth_token)

    def _check_request_access(self) -> bool:
        if not self._origin_allowed():
            self._send_error_json("Origin not allowed", 403)
            return False
        if not self._authorized():
            self.send_response(401)
            self.send_header("WWW-Authenticate", "Bearer")
            self.send_header("Content-Length", "0")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            return False
        return True

    def do_GET(self):
        if not self._check_request_access():
            return
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == "/api/examples":
                self._handle_get_examples()
            elif path == "/api/health":
                self._send_json({"status": "healthy", "service": "Rezonator Engine"})
            else:
                # Fall back to serving static files from web/
                super().do_GET()
        except Exception:
            self._send_error_json("Internal server error", 500)

    def do_POST(self):
        if not self._check_request_access():
            return
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            data = self._read_json_body()
            if not isinstance(data, dict):
                self._send_error_json("JSON payload must be an object", 400)
                return

            if path == "/api/analyze":
                self._handle_analyze(data)
            elif path == "/api/compare":
                self._handle_compare(data)
            elif path == "/api/brief":
                self._handle_brief(data)
            else:
                self._send_error_json(f"Endpoint not found: {path}", 404)
        except ResourceLimitError as exc:
            self._send_error_json(str(exc), exc.status_code)
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
            self._send_error_json(f"Invalid JSON payload: {str(exc)}", 400)
        except Exception:
            self._send_error_json("Internal server error", 500)

    def _read_json_body(self) -> dict:
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("Chunked transfer encoding is not supported")
        raw_length = self.headers.get("Content-Length", "0")
        try:
            content_length = int(raw_length)
        except (TypeError, ValueError):
            raise ValueError("Content-Length must be an integer")
        if content_length < 0:
            raise ValueError("Content-Length cannot be negative")
        if content_length > MAX_PAYLOAD_BYTES:
            raise ResourceLimitError(
                f"Payload exceeds {MAX_PAYLOAD_BYTES} bytes"
            )

        body = self.rfile.read(content_length) if content_length else b""
        if len(body) != content_length:
            raise ValueError("Request body ended before Content-Length")
        return json.loads(body.decode("utf-8")) if body else {}

    def _handle_get_examples(self):
        examples = {}
        if os.path.isdir(EXAMPLES_DIR):
            for fname in os.listdir(EXAMPLES_DIR):
                if fname.endswith(".cbl"):
                    fpath = os.path.join(EXAMPLES_DIR, fname)
                    with open(fpath, "r", encoding="utf-8") as f:
                        key = os.path.splitext(fname)[0]
                        examples[key] = {
                            "filename": fname,
                            "code": f.read()
                        }
        self._send_json(examples)

    def _handle_analyze(self, data: dict):
        code = data.get("code", "")
        if not code.strip():
            self._send_error_json("Code parameter is required", 400)
            return

        comparator = ProgramComparator(lattice_size=32)
        result = comparator.analyze_single(code)
        result["llm_brief"] = LLMSynthesizer.generate_cognitive_brief(result)
        self._send_json(result)

    def _handle_compare(self, data: dict):
        code_a = data.get("code_a", "")
        code_b = data.get("code_b", "")

        if not code_a.strip() or not code_b.strip():
            self._send_error_json("Both code_a and code_b are required", 400)
            return

        comparator = ProgramComparator(lattice_size=32)
        result = comparator.compare(code_a, code_b)
        result["program_a_brief"] = LLMSynthesizer.generate_cognitive_brief(result["program_a_details"])
        result["program_b_brief"] = LLMSynthesizer.generate_cognitive_brief(result["program_b_details"])
        self._send_json(result)

    def _handle_brief(self, data: dict):
        code = data.get("code", "")
        if not code.strip():
            self._send_error_json("Code parameter is required", 400)
            return
        comparator = ProgramComparator(lattice_size=32)
        result = comparator.analyze_single(code)
        brief = LLMSynthesizer.generate_cognitive_brief(result)
        self._send_json({"brief": brief})

    def _send_json(self, payload: dict, status: int = 200):
        body_bytes = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        origin = self.headers.get("Origin")
        if origin and origin in self.server.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body_bytes)
        self.wfile.flush()
        self.close_connection = True

    def _send_error_json(self, message: str, status: int = 400):
        self._send_json({"error": message, "status": status}, status=status)

    def do_OPTIONS(self):
        # Browsers do not include the bearer token in a CORS preflight. The
        # actual GET/POST request remains protected by _check_request_access.
        if not self._origin_allowed():
            self._send_error_json("Origin not allowed", 403)
            return
        self.send_response(200)
        origin = self.headers.get("Origin")
        if origin and origin in self.server.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True


MathyRequestHandler = RezonatorRequestHandler


def run_server(port: int = 8080, mode: str = "local", token: str = None):
    if mode not in {"local", "remote"}:
        raise ValueError("mode must be 'local' or 'remote'")
    if mode == "remote" and not token:
        raise ValueError("remote mode requires a bearer token")

    host = "127.0.0.1" if mode == "local" else "0.0.0.0"
    server_address = (host, port)
    httpd = RezonatorHTTPServer(
        server_address,
        RezonatorRequestHandler,
        mode=mode,
        auth_token=token,
    )
    display_host = "127.0.0.1" if mode == "local" else "0.0.0.0"
    print(f"\n[REZONATOR STUDIO ONLINE] -> http://{display_host}:{port} ({mode} mode)")
    print("Serving interactive visualizer, API, and live physics engines.\nPress Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()
