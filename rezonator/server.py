"""
HTTP Server & REST API for Błyskawica Mathy.
Serves static Web Studio files and provides JSON endpoints for analysis, comparison, and diffusion.
"""

import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

from rezonator.cobol_parser import CobolParser
from rezonator.program_comparator import ProgramComparator
from rezonator.llm_synthesizer import LLMSynthesizer


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")
EXAMPLES_DIR = os.path.join(BASE_DIR, "examples")


class RezonatorRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/examples":
            self._handle_get_examples()
        elif path == "/api/health":
            self._send_json({"status": "healthy", "service": "Rezonator Engine"})
        else:
            # Fall back to serving static files from web/
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else ""

        try:
            data = json.loads(body) if body else {}
        except Exception as e:
            self._send_error_json(f"Invalid JSON payload: {str(e)}", 400)
            return

        if path == "/api/analyze":
            self._handle_analyze(data)
        elif path == "/api/compare":
            self._handle_compare(data)
        elif path == "/api/brief":
            self._handle_brief(data)
        else:
            self._send_error_json(f"Endpoint not found: {path}", 404)

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
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def _send_error_json(self, message: str, status: int = 400):
        self._send_json({"error": message, "status": status}, status=status)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


MathyRequestHandler = RezonatorRequestHandler


def run_server(port: int = 8080):
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, RezonatorRequestHandler)
    print(f"\n[REZONATOR STUDIO ONLINE] -> http://127.0.0.1:{port}")
    print("Serving interactive visualizer, API, and live physics engines.\nPress Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()
