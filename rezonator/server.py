"""
HTTP Server & REST API for Błyskawica Mathy.
Serves static Web Studio files and provides JSON endpoints for analysis, comparison, and diffusion.
"""

import json
import hmac
import os
import socket
import struct
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from typing import cast, Optional, Set

from rezonator.cobol_parser import CobolParser
from rezonator.program_comparator import ProgramComparator
from rezonator.llm_synthesizer import LLMSynthesizer
from rezonator.audit_report import audit_report_to_markdown, build_audit_report
from rezonator.program_slicer import ProgramSlicer, context_slice_to_markdown
from rezonator.portfolio_manifest import (
    PortfolioManifest,
    ProgramEntry,
    JclEntry,
    DatasetEntry,
    Db2TableEntry,
)
from rezonator.portfolio_graph import PortfolioGraphBuilder
from rezonator.partition_recommender import PartitionRecommender
from rezonator.migration_verifier import (
    MigrationVerifier,
    DifferentialTestCase,
    DomainInvariant,
)
from rezonator.limits import ResourceLimitError, MAX_SOURCE_BYTES
from rezonator.rbac_guard import (
    EndpointSecurityEnforcer,
    AuthSecurityError,
    RateLimitExceededError,
)
from rezonator.crypto_signer import SbomGenerator


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")
EXAMPLES_DIR = os.path.join(BASE_DIR, "examples")
CORPUS_DIR = os.path.join(EXAMPLES_DIR, "corpus")
CORPUS_JCL_DIR = os.path.join(CORPUS_DIR, "jcl")
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

    def __init__(
        self,
        server_address,
        RequestHandlerClass,
        *,
        mode="local",
        auth_token=None,
        allowed_origins=None,
        security_enforcer: Optional[EndpointSecurityEnforcer] = None,
    ):
        self.mode = mode
        self.auth_token = auth_token
        self.security_enforcer = security_enforcer
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

    @property
    def rezonator_server(self) -> RezonatorHTTPServer:
        return cast(RezonatorHTTPServer, self.server)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def setup(self):
        super().setup()
        self.connection.settimeout(REQUEST_TIMEOUT_SECONDS)
        try:
            # On Windows Winsock, linger struct uses two unsigned shorts (4 bytes); on Unix two ints (8 bytes).
            linger_format = "hh" if sys.platform == "win32" else "ii"
            self.connection.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_LINGER,
                struct.pack(linger_format, 1, 5)
            )
        except (AttributeError, OSError):
            pass

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        return not origin or origin in self.rezonator_server.allowed_origins

    def _authorized(self) -> bool:
        if self.rezonator_server.mode == "local":
            return True
        authorization = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not authorization.startswith(prefix) or not self.rezonator_server.auth_token:
            return False
        return hmac.compare_digest(authorization[len(prefix):], self.rezonator_server.auth_token)

    def _check_request_access(self) -> bool:
        if not self._origin_allowed():
            self._send_error_json("Origin not allowed", 403)
            return False

        if self.rezonator_server.security_enforcer is not None:
            parsed = urlparse(self.path)
            auth_header = self.headers.get("Authorization")
            client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
            try:
                self.rezonator_server.security_enforcer.authorize_request(
                    path=parsed.path,
                    auth_header=auth_header,
                    client_ip=client_ip,
                )
            except AuthSecurityError as e:
                status_code = 403 if "Insufficient privileges" in str(e) else 401
                self.send_response(status_code)
                self.send_header("WWW-Authenticate", "Bearer")
                self.send_header("Content-Type", "application/json")
                err_bytes = json.dumps({"error": str(e)}).encode("utf-8")
                self.send_header("Content-Length", str(len(err_bytes)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(err_bytes)
                self.close_connection = True
                return False
            except RateLimitExceededError as e:
                self._send_error_json(str(e), 429)
                self.close_connection = True
                return False
            return True

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
            elif path == "/api/portfolio":
                self._handle_get_portfolio()
            elif path == "/api/sbom":
                query = parsed.query.lower()
                if "spdx" in query:
                    self._send_json(SbomGenerator.generate_spdx())
                else:
                    self._send_json(SbomGenerator.generate_cyclonedx())
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
            elif path == "/api/audit":
                self._handle_audit(data)
            elif path == "/api/slice":
                self._handle_slice(data)
            elif path == "/api/brief":
                self._handle_brief(data)
            elif path == "/api/portfolio":
                self._handle_portfolio(data)
            elif path == "/api/partition":
                self._handle_partition(data)
            elif path == "/api/migration":
                self._handle_migration(data)
            else:
                self._send_error_json(f"Endpoint not found: {path}", 404)
        except ResourceLimitError as exc:
            self._send_error_json(str(exc), exc.status_code)
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
            self._send_error_json(f"Invalid request: {str(exc)}", 400)
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

        comparator = ProgramComparator(lattice_size=32, copybooks=self._request_copybooks(data))
        result = comparator.analyze_single(code)
        # Keep the legacy response key for existing clients; this is not model output.
        result["llm_brief"] = LLMSynthesizer.generate_cognitive_brief(result)
        self._send_json(result)

    def _handle_compare(self, data: dict):
        code_a = data.get("code_a", "")
        code_b = data.get("code_b", "")

        if not code_a.strip() or not code_b.strip():
            self._send_error_json("Both code_a and code_b are required", 400)
            return

        comparator = ProgramComparator(lattice_size=32, copybooks=self._request_copybooks(data))
        result = comparator.compare(code_a, code_b)
        result["program_a_brief"] = LLMSynthesizer.generate_cognitive_brief(result["program_a_details"])
        result["program_b_brief"] = LLMSynthesizer.generate_cognitive_brief(result["program_b_details"])
        self._send_json(result)

    def _handle_brief(self, data: dict):
        code = data.get("code", "")
        if not code.strip():
            self._send_error_json("Code parameter is required", 400)
            return
        comparator = ProgramComparator(lattice_size=32, copybooks=self._request_copybooks(data))
        result = comparator.analyze_single(code)
        brief = LLMSynthesizer.generate_cognitive_brief(result)
        self._send_json({"brief": brief})

    def _handle_audit(self, data: dict):
        code = data.get("code", "")
        if not isinstance(code, str) or not code.strip():
            self._send_error_json("Code parameter is required", 400)
            return
        output_format = data.get("format", "json")
        if output_format not in ("json", "markdown"):
            self._send_error_json("format must be 'json' or 'markdown'", 400)
            return
        comparator = ProgramComparator(
            lattice_size=32,
            copybooks=self._request_copybooks(data),
        )
        report = build_audit_report(comparator.analyze_single(code))
        if output_format == "markdown":
            self._send_bytes(
                audit_report_to_markdown(report).encode("utf-8"),
                "text/markdown; charset=utf-8",
            )
        else:
            self._send_json(report)

    def _handle_slice(self, data: dict):
        code = data.get("code", "")
        if not isinstance(code, str) or not code.strip():
            self._send_error_json("Code parameter is required", 400)
            return

        output_format = data.get("format", "json")
        if output_format not in ("json", "markdown"):
            self._send_error_json("format must be 'json' or 'markdown'", 400)
            return

        copybooks = self._request_copybooks(data)
        parser = CobolParser(copybooks=copybooks)
        graph = parser.parse(code)
        slicer = ProgramSlicer(graph)

        seed_node = data.get("seed_node")
        seed_line = data.get("seed_line")
        seed_variable = data.get("seed_variable")

        direction = data.get("direction", "forward")
        max_lines = data.get("max_lines", 50)
        max_tokens = data.get("max_tokens", 1000)
        max_nodes = data.get("max_nodes")
        ranking_strategy = data.get("ranking_strategy", "bfs")

        if max_lines is not None and (not isinstance(max_lines, int) or max_lines <= 0):
            self._send_error_json("max_lines must be a positive integer", 400)
            return
        if max_tokens is not None and (not isinstance(max_tokens, int) or max_tokens <= 0):
            self._send_error_json("max_tokens must be a positive integer", 400)
            return
        if max_nodes is not None and (not isinstance(max_nodes, int) or max_nodes <= 0):
            self._send_error_json("max_nodes must be a positive integer", 400)
            return

        try:
            packet = slicer.extract_bounded_slice(
                seed_node_id=seed_node,
                seed_line=seed_line,
                seed_variable=seed_variable,
                direction=direction,
                max_lines=max_lines,
                max_tokens=max_tokens,
                max_nodes=max_nodes,
                ranking_strategy=ranking_strategy,
            )
        except ValueError as err:
            self._send_error_json(str(err), 400)
            return

        if output_format == "markdown":
            self._send_bytes(
                context_slice_to_markdown(packet).encode("utf-8"),
                "text/markdown; charset=utf-8",
            )
        else:
            self._send_json(packet)

    def _build_default_corpus_manifest(self) -> PortfolioManifest:
        program_files = [
            os.path.join(CORPUS_DIR, f)
            for f in sorted(os.listdir(CORPUS_DIR))
            if f.endswith(".cbl")
        ] if os.path.isdir(CORPUS_DIR) else []
        jcl_files = [
            os.path.join(CORPUS_JCL_DIR, f)
            for f in sorted(os.listdir(CORPUS_JCL_DIR))
            if f.endswith(".jcl")
        ] if os.path.isdir(CORPUS_JCL_DIR) else []
        return PortfolioManifest.from_files(
            program_paths=program_files,
            jcl_paths=jcl_files,
            name="CorpusEnterprisePortfolio",
            description="6-program enterprise portfolio with batch JCL workflows",
            known_tables=["ACCOUNTS", "AUDIT_LOG"],
            known_datasets=["CUST.MASTER.FILE", "CUST.OUTPUT.FILE"],
        )

    def _handle_portfolio(self, data: dict):
        output_format = data.get("format", "json")
        if output_format not in ("json", "markdown"):
            self._send_error_json("format must be 'json' or 'markdown'", 400)
            return

        if "manifest" in data and isinstance(data["manifest"], dict):
            manifest = PortfolioManifest.from_dict(data["manifest"])
        elif data.get("programs") or data.get("jobs"):
            progs = [ProgramEntry.from_dict(p) for p in data.get("programs", [])]
            jobs = [JclEntry.from_dict(j) for j in data.get("jobs", [])]
            dsns = [DatasetEntry.from_dict(d) for d in data.get("known_datasets", [])]
            tables = [Db2TableEntry.from_dict(t) for t in data.get("known_tables", [])]
            manifest = PortfolioManifest(
                name=data.get("name", "ad-hoc-portfolio"),
                programs=progs,
                jobs=jobs,
                known_datasets=dsns,
                known_tables=tables,
                description=data.get("description", ""),
            )
        else:
            manifest = self._build_default_corpus_manifest()

        builder = PortfolioGraphBuilder()
        graph = builder.build(manifest)

        if output_format == "markdown":
            self._send_bytes(
                graph.to_markdown_report().encode("utf-8"),
                "text/markdown; charset=utf-8",
            )
        else:
            self._send_json({
                "report": graph.generate_report(),
                "graph": graph.to_dict(),
            })

    def _handle_get_portfolio(self):
        manifest = self._build_default_corpus_manifest()
        builder = PortfolioGraphBuilder()
        graph = builder.build(manifest)
        self._send_json({
            "report": graph.generate_report(),
            "graph": graph.to_dict(),
        })

    def _handle_partition(self, data: dict):
        output_format = data.get("format", "json")
        if output_format not in ("json", "markdown"):
            self._send_error_json("format must be 'json' or 'markdown'", 400)
            return

        top_k = data.get("top_k", 3)
        if not isinstance(top_k, int) or top_k <= 0:
            self._send_error_json("top_k must be a positive integer", 400)
            return

        if "manifest" in data and isinstance(data["manifest"], dict):
            manifest = PortfolioManifest.from_dict(data["manifest"])
        elif data.get("programs") or data.get("jobs"):
            progs = [ProgramEntry.from_dict(p) for p in data.get("programs", [])]
            jobs = [JclEntry.from_dict(j) for j in data.get("jobs", [])]
            dsns = [DatasetEntry.from_dict(d) for d in data.get("known_datasets", [])]
            tables = [Db2TableEntry.from_dict(t) for t in data.get("known_tables", [])]
            manifest = PortfolioManifest(
                name=data.get("name", "ad-hoc-portfolio"),
                programs=progs,
                jobs=jobs,
                known_datasets=dsns,
                known_tables=tables,
                description=data.get("description", ""),
            )
        else:
            manifest = self._build_default_corpus_manifest()

        builder = PortfolioGraphBuilder()
        graph = builder.build(manifest)
        recommender = PartitionRecommender()
        candidates = recommender.recommend_portfolio_partitions(graph, top_k=top_k)

        if output_format == "markdown":
            self._send_bytes(
                recommender.to_markdown_report(candidates).encode("utf-8"),
                "text/markdown; charset=utf-8",
            )
        else:
            self._send_json({
                "schema_version": PartitionRecommender.SCHEMA_VERSION,
                "manifest_id": graph.manifest_id,
                "candidate_count": len(candidates),
                "candidates": [c.to_dict() for c in candidates],
            })

    def _handle_migration(self, data: dict):
        output_format = data.get("format", "json")
        if output_format not in ("json", "markdown"):
            self._send_error_json("format must be 'json' or 'markdown'", 400)
            return

        baseline_source = data.get("baseline_source") or data.get("source_a")
        candidate_source = data.get("candidate_source") or data.get("source_b")

        if not baseline_source or not candidate_source:
            self._send_error_json("baseline_source and candidate_source are required", 400)
            return

        copybooks = self._request_copybooks(data)
        test_cases_raw = data.get("test_cases", [])
        test_cases = [
            DifferentialTestCase(
                test_id=tc.get("test_id", f"tc-{idx:02d}"),
                description=tc.get("description", ""),
                input_overrides=tc.get("input_overrides", {}),
                expected_output_vars=tc.get("expected_output_vars"),
                invariants=tc.get("invariants", []),
            )
            for idx, tc in enumerate(test_cases_raw, 1)
        ] if test_cases_raw else None

        invariants_raw = data.get("invariants", [])
        invariants = [
            DomainInvariant(
                name=inv.get("name", f"inv-{idx:02d}"),
                expression=inv.get("expression", ""),
                description=inv.get("description", ""),
                severity=inv.get("severity", "CRITICAL"),
            )
            for idx, inv in enumerate(invariants_raw, 1)
        ] if invariants_raw else None

        verifier = MigrationVerifier(copybooks=copybooks)
        evidence = verifier.verify(
            baseline_source=baseline_source,
            candidate_source=candidate_source,
            test_cases=test_cases,
            invariants=invariants,
        )

        if output_format == "markdown":
            self._send_bytes(
                evidence.to_markdown_report().encode("utf-8"),
                "text/markdown; charset=utf-8",
            )
        else:
            self._send_json(evidence.to_dict())

    @staticmethod
    def _request_copybooks(data: dict):
        copybooks = data.get("copybooks")
        if copybooks is None:
            return None
        if not isinstance(copybooks, dict):
            raise ValueError("copybooks must be an object mapping names to source text")
        if any(not isinstance(name, str) or not isinstance(content, str)
               for name, content in copybooks.items()):
            raise ValueError("copybooks must map string names to string contents")
        return copybooks

    def _send_json(self, payload: dict, status: int = 200):
        body_bytes = json.dumps(payload).encode("utf-8")
        self._send_bytes(body_bytes, "application/json; charset=utf-8", status=status)

    def _send_bytes(self, body_bytes: bytes, content_type: str, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        origin = self.headers.get("Origin")
        if origin and origin in self.rezonator_server.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.send_header("Connection", "close")
        self.end_headers()
        chunk_size = 64 * 1024
        for offset in range(0, len(body_bytes), chunk_size):
            self.wfile.write(body_bytes[offset:offset + chunk_size])
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
        if origin and origin in self.rezonator_server.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True


MathyRequestHandler = RezonatorRequestHandler


def run_server(port: int = 8080, mode: str = "local", token: Optional[str] = None):
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
