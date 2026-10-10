"""Security boundary tests for HTTP, runtime evaluation, limits, and provenance."""

import hashlib
import http.client
import threading
import unittest

from rezonator.cobol_runtime import CobolRuntime
from rezonator.limits import (
    MAX_DENSE_MATRIX_NODES,
    GraphLimitError,
    ResourceLimitError,
    MAX_SOURCE_BYTES,
)
from rezonator.provenance import source_provenance
from rezonator.graph_field import GraphField
from rezonator.server import HTTPServer, MAX_PAYLOAD_BYTES, RezonatorRequestHandler


class TestRuntimeSafety(unittest.TestCase):
    def test_expression_evaluator_supports_core_semantics_without_interpreter_escape(self):
        runtime = CobolRuntime()
        variables = {"WS-COUNT": 3, "WS-STATUS": "READY"}

        self.assertEqual(runtime._eval_expr("WS-COUNT + 2 * 4", variables), 11)
        self.assertTrue(runtime._eval_expr('WS-COUNT >= 3 AND WS-STATUS = "READY"', variables))
        self.assertEqual(
            runtime._eval_expr("__import__('os').system('echo unsafe')", variables),
            0,
        )

    def test_source_and_dense_graph_limits_fail_closed(self):
        with self.assertRaises(ResourceLimitError):
            from rezonator.limits import validate_source_size
            validate_source_size("X" * (MAX_SOURCE_BYTES + 1))

        nodes = [{"id": f"n{i}", "node_type": "stmt", "reads": [], "writes": []}
                 for i in range(MAX_DENSE_MATRIX_NODES + 1)]
        with self.assertRaises(GraphLimitError):
            GraphField({"nodes": nodes, "edges": [], "variables": []})


class TestProvenance(unittest.TestCase):
    def test_provenance_is_cryptographic_and_versioned(self):
        result = source_provenance("PROGRAM-ID. DEMO.")
        self.assertEqual(
            result["source_sha256"],
            hashlib.sha256("PROGRAM-ID. DEMO.".encode("utf-8")).hexdigest(),
        )
        self.assertEqual(result["solver_seed"], 42)
        self.assertTrue(result["rezonator_version"])
        self.assertTrue(result["timestamp_utc"].endswith("Z"))


class TestHttpSecurity(unittest.TestCase):
    def _start_server(self, **kwargs):
        server = HTTPServer(("127.0.0.1", 0), RezonatorRequestHandler, **kwargs)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server

    def _request(self, server, method, path, headers=None, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        payload = response.read()
        connection.close()
        return response, payload

    def test_cors_is_allowlisted(self):
        server = self._start_server()
        try:
            port = server.server_address[1]
            response, _ = self._request(
                server,
                "GET",
                "/api/health",
                headers={"Origin": f"http://localhost:{port}"},
            )
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("Access-Control-Allow-Origin"), f"http://localhost:{port}")

            response, _ = self._request(
                server,
                "GET",
                "/api/health",
                headers={"Origin": "https://evil.example"},
            )
            self.assertEqual(response.status, 403)
        finally:
            server.shutdown()
            server.server_close()

    def test_payload_limit_and_remote_bearer_token(self):
        server = self._start_server(
            mode="remote",
            auth_token="secret",
            allowed_origins={"http://localhost:8080"},
        )
        try:
            response, _ = self._request(
                server,
                "OPTIONS",
                "/api/health",
                headers={"Origin": "http://localhost:8080"},
            )
            self.assertEqual(response.status, 200)

            response, _ = self._request(server, "GET", "/api/health")
            self.assertEqual(response.status, 401)

            response, _ = self._request(
                server,
                "GET",
                "/api/health",
                headers={"Authorization": "Bearer secret"},
            )
            self.assertEqual(response.status, 200)

            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
            connection.putrequest("POST", "/api/analyze")
            connection.putheader("Content-Length", str(MAX_PAYLOAD_BYTES + 1))
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Authorization", "Bearer secret")
            connection.endheaders()
            response = connection.getresponse()
            self.assertEqual(response.status, 413)
            response.read()
            connection.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
