"""
Comprehensive Integration & Verification Suite for Rezonator Engine.
Tests:
1. COBOL Lexer & AST parser (Area A/B keywords, IF/ELSE/END-IF blocks)
2. GraphField Laplacian construction & Fan Chung normalized Laplacian
3. Diamond Yant modal eigensolver & NetLSD multi-scale heat trace
4. PINN Heat Diffusion engine (analytical & forward directed impact propagation)
5. CycleDetector (Tarjan SCC, recursion detection, deadlock verification)
6. ProgramComparator (NetLSD differentiation, refactoring fidelity, deadlock regression)
7. HTTP Server API endpoints (hermetic via in-process server thread)
"""

import json
import os
import threading
import time
import unittest
import urllib.request
import urllib.error
import numpy as np

from rezonator.cobol_parser import CobolParser
from rezonator.graph_field import GraphField
from rezonator.diamond_yant import DiamondYantSpectralEngine
from rezonator.pinn_diffusion import PINNGraphDiffusionEngine
from rezonator.cycle_detector import CycleDetector
from rezonator.program_comparator import ProgramComparator
from rezonator.llm_synthesizer import LLMSynthesizer
from rezonator.server import HTTPServer, MathyRequestHandler


class TestRezonatorEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.examples_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples")
        with open(os.path.join(cls.examples_dir, "bank_demo_v1.cbl"), "r", encoding="utf-8") as f:
            cls.code_v1 = f.read()
        with open(os.path.join(cls.examples_dir, "bank_demo_v2.cbl"), "r", encoding="utf-8") as f:
            cls.code_v2 = f.read()
        with open(os.path.join(cls.examples_dir, "atm_deadlock.cbl"), "r", encoding="utf-8") as f:
            cls.code_deadlock = f.read()

        # Start hermetic test server on test port 8089
        cls.test_port = 0
        try:
            cls.server = HTTPServer(("127.0.0.1", cls.test_port), MathyRequestHandler)
            cls.test_port = cls.server.server_address[1]
            cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
            cls.server_thread.start()
            time.sleep(0.1)
        except Exception:
            cls.server = None

    @classmethod
    def tearDownClass(cls):
        if cls.server:
            cls.server.shutdown()
            cls.server.server_close()

    def test_01_cobol_parser(self):
        parser = CobolParser()
        res = parser.parse(self.code_v1)
        self.assertEqual(res["program_id"], "BANK-DEMO-V1")
        self.assertGreater(len(res["nodes"]), 10)
        self.assertGreater(len(res["edges"]), 15)
        self.assertGreater(len(res["variables"]), 2)

        # Ensure END-IF was not parsed as a paragraph header
        paragraphs = {n["paragraph"] for n in res["nodes"]}
        self.assertNotIn("END-IF", paragraphs)

    def test_02_graph_laplacian(self):
        parser = CobolParser()
        parsed = parser.parse(self.code_v1)
        field = GraphField(parsed, symmetrize=True, include_variables=True)

        # Symmetry test: L == L.T
        self.assertTrue(np.allclose(field.L, field.L.T, atol=1e-8))
        # Row sums of Laplacian should be approximately 0
        row_sums = np.sum(field.L, axis=1)
        self.assertTrue(np.allclose(row_sums, np.zeros_like(row_sums), atol=1e-5))

        # Normalized Laplacian must be symmetric and eigenvalues in [0, 2]
        self.assertTrue(np.allclose(field.L_norm, field.L_norm.T, atol=1e-8))
        evals_norm = np.linalg.eigvalsh(field.L_norm)
        self.assertTrue(all(ev >= -1e-6 and ev <= 2.0001 for ev in evals_norm))

    def test_03_diamond_yant_netlsd_spectrum(self):
        parser = CobolParser()
        parsed = parser.parse(self.code_v1)
        field = GraphField(parsed, symmetrize=True, include_variables=True)
        yant = DiamondYantSpectralEngine(lattice_size=16)

        spectrum = yant.compute_spectrum(field.L, L_norm=field.L_norm, num_modes=8)
        self.assertIn("eigenvalues", spectrum)
        self.assertIn("fiedler_value", spectrum)
        self.assertIn("netlsd_signature", spectrum)
        self.assertGreater(len(spectrum["netlsd_signature"]), 0)

        # Eigenvalues must be non-negative
        self.assertTrue(all(ev >= -1e-6 for ev in spectrum["eigenvalues"]))

        chladni = yant.generate_chladni_surface(spectrum)
        matrix = np.array(chladni["chladni_matrix"])
        self.assertEqual(matrix.shape, (16, 16))
        self.assertLessEqual(np.max(np.abs(matrix)), 1.01)

    def test_04_diffusion_and_directed_impact(self):
        parser = CobolParser()
        parsed = parser.parse(self.code_v1)
        field = GraphField(parsed, symmetrize=True, include_variables=True)
        diffusion_engine = PINNGraphDiffusionEngine(alpha=0.5)

        # Symmetric diffusion
        u0 = np.zeros(field.num_nodes)
        u0[0] = 1.0
        diff = diffusion_engine.solve_analytical(field.L, u0, time_steps=10)
        self.assertEqual(len(diff["times"]), 10)
        self.assertEqual(len(diff["trajectory"]), 10)
        self.assertGreater(diff["diffusion_half_life"], 0.0)

        # Forward directed impact propagation
        impact = diffusion_engine.solve_directed_impact(field.A_dir, source_idx=0, t=1.5)
        self.assertIn("impact_ranking", impact)
        self.assertGreater(impact["reachable_count"], 5)
        # Entry node must have high impact
        self.assertGreater(impact["max_impact"], 0.1)

    def test_05_cycle_and_deadlock_detection(self):
        # 1. Bank demo V1 has no cycles and terminates safely
        p1 = CobolParser().parse(self.code_v1)
        d1 = CycleDetector(p1).analyze()
        self.assertFalse(d1["has_deadlock"])
        self.assertFalse(d1["is_recursive"])
        self.assertEqual(d1["cycle_count"], 0)
        self.assertTrue(d1["reaches_terminal"])

        # 2. ATM Deadlock has a recursive perform and infinite loop hazard
        pd = CobolParser().parse(self.code_deadlock)
        dd = CycleDetector(pd).analyze()
        self.assertTrue(dd["has_deadlock"])
        self.assertTrue(dd["is_recursive"])
        self.assertGreaterEqual(dd["cycle_count"], 1)
        self.assertEqual(dd["risk_verdict"], "CRITICAL_INFINITE_LOOP")

    def test_06_program_comparator_netlsd(self):
        comparator = ProgramComparator(lattice_size=16)

        # V1 vs V1 (isomorphism)
        cmp_self = comparator.compare(self.code_v1, self.code_v1)
        self.assertAlmostEqual(cmp_self["metrics"]["spectral_distance_netlsd"], 0.0, places=4)
        self.assertEqual(cmp_self["metrics"]["refactoring_health_score"], 100.0)

        # V1 vs V2 (safe refactoring)
        cmp_12 = comparator.compare(self.code_v1, self.code_v2)
        m12 = cmp_12["metrics"]
        self.assertGreater(m12["spectral_distance_netlsd"], 0.01)
        self.assertLess(m12["spectral_distance_netlsd"], 0.10)
        self.assertGreater(m12["refactoring_health_score"], 80.0)
        self.assertFalse(m12["deadlock_introduced"])

        # V1 vs Deadlock (critical regression detection)
        cmp_dead = comparator.compare(self.code_v1, self.code_deadlock)
        m_dead = cmp_dead["metrics"]
        self.assertTrue(m_dead["deadlock_introduced"])
        self.assertEqual(m_dead["refactoring_health_score"], 0.0)
        self.assertIn("CRITICAL_REGRESSION", cmp_dead["verdict"])

    def test_07_http_api_endpoints(self):
        if not self.server:
            self.skipTest("Hermetic HTTP test server could not be bound.")

        base_url = f"http://127.0.0.1:{self.test_port}"

        # 1. Health
        req = urllib.request.urlopen(f"{base_url}/api/health")
        self.assertEqual(req.status, 200)
        health = json.loads(req.read().decode())
        self.assertEqual(health["status"], "healthy")

        # 2. Examples
        req = urllib.request.urlopen(f"{base_url}/api/examples")
        self.assertEqual(req.status, 200)
        examples = json.loads(req.read().decode())
        self.assertIn("bank_demo_v1", examples)
        self.assertIn("bank_demo_v2", examples)

        # 3. Analyze
        payload = json.dumps({"code": self.code_v1}).encode()
        post_req = urllib.request.Request(
            f"{base_url}/api/analyze",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(post_req)
        self.assertEqual(resp.status, 200)
        analysis = json.loads(resp.read().decode())
        self.assertEqual(analysis["program_id"], "BANK-DEMO-V1")
        self.assertIn("spectrum", analysis)
        self.assertIn("chladni", analysis)
        self.assertIn("diffusion", analysis)
        self.assertIn("cycles", analysis)

        # 4. Compare
        payload_cmp = json.dumps({
            "code_a": self.code_v1,
            "code_b": self.code_v2
        }).encode()
        post_cmp = urllib.request.Request(
            f"{base_url}/api/compare",
            data=payload_cmp,
            headers={"Content-Type": "application/json"}
        )
        resp_cmp = urllib.request.urlopen(post_cmp)
        self.assertEqual(resp_cmp.status, 200)
        cmp_res = json.loads(resp_cmp.read().decode())
        self.assertIn("metrics", cmp_res)
        self.assertIn("verdict", cmp_res)


if __name__ == "__main__":
    unittest.main()
