# Rezonator Documentation Directory

This folder contains the complete technical specifications, architectural blueprints, empirical evaluations, and mathematical foundations for the **Rezonator** software intelligence platform.

---

## 📑 Core Documentation Index

| Document | Topic | Status | Scope & Implementation |
|---|---|:---:|---|
| [`SOKOL_ARCHITECTURE.md`](SOKOL_ARCHITECTURE.md) | Sokół AI Observer & Memory Architecture | 🟢 **DELIVERED** | Two-layer model, epistemic boundaries (`OBSERVED`, `INFERRED`, `VERIFIED`), and delivery sequence. |
| [`SOKOL_PROJECT_MEMORY.md`](SOKOL_PROJECT_MEMORY.md) | Sokół Versioned Project Memory (`sokol.fact.v1`) | 🟢 **DELIVERED** | Content-addressed fact envelopes, node anchors (`NodeAnchor`), snapshot binding, and staleness invalidation. |
| [`SOKOL_EVIDENCE_EVENTS.md`](SOKOL_EVIDENCE_EVENTS.md) | Sokół Evidence Events Transport (`sokol.event.v1`) | 🟢 **DELIVERED** | Bounded in-memory JSONL export for source snapshots, deterministic analyses, and value-free interpreter runs. |
| [`CORPUS_EVALUATION_REPORT.md`](CORPUS_EVALUATION_REPORT.md) | Enterprise COBOL Corpus Evaluation | 🟢 **DELIVERED** | Empirical benchmark across 6 enterprise programs (339 LOC, 88.24% coverage, copybooks, CICS/DB2, cycle analysis). |
| [`SUPPORTED_SYNTAX.md`](SUPPORTED_SYNTAX.md) | Parser Grammar Matrix & Truthfulness Spec | 🟢 **DELIVERED** | Supported COBOL divisions, variables, procedure verbs, and truthful materialization of unhandled statements. |
| [`AUDIT_REPORT.md`](AUDIT_REPORT.md) | Auditable Report & Provenance Manifest | 🟢 **DELIVERED** | Schema for JSON/Markdown reports, SHA-256 graph digest, deterministic analysis fingerprint, and source anchors. |
| [`CONTEXT_SLICE_SPEC.md`](CONTEXT_SLICE_SPEC.md) | Bounded Context Slice Specification | 🟢 **DELIVERED** | Forward/backward/bidirectional static program slicing under token/line budgets with omission disclosures. |
| [`MATHEMATICAL_FOUNDATIONS.md`](MATHEMATICAL_FOUNDATIONS.md) | Spectral & Diffusion Physics Reference | 🟢 **DELIVERED** | Diamond Yant modal eigensolvers, NetLSD heat trace signature, and sparse CSR operator formulation. |
| [`REZONATOR_MATHEMATICAL_FOUNDATIONS.md`](REZONATOR_MATHEMATICAL_FOUNDATIONS.md) | Extended Mathematical Foundations | 🟢 **DELIVERED** | Detailed mathematical formulation of PINN diffusion, Laplacian operators, and spectral invariants. |

---

## 🏛️ System Architecture Layers

```
Layer 1: Deterministic Mathematical Core 🟢 DELIVERED
├── Front-End COBOL Parser (ast_graph_builder.py, cobol_parser.py)
├── Sparse Graph Field & CSR Laplacians (graph_field.py)
├── Diamond Yant Spectral & NetLSD Engine (diamond_yant.py)
├── Diffusion Impact Ranker (diffusion_ranker.py, pinn_diffusion.py)
├── Cycle Detector & SCC Analyzer (cycle_detector.py)
├── Program Slicer & Context Budgets (program_slicer.py)
├── Auditable Report & Provenance (audit_report.py, provenance.py)
└── Enterprise Corpus Evaluation Harness (corpus_evaluator.py)

Layer 2: Sokół Read-Only Observer & Memory
├── Evidence Events Contract (sokol.event.v1) 🟢 DELIVERED (evidence_events.py)
├── Versioned Project Memory (sokol.fact.v1) 🟢 DELIVERED (project_memory.py)
│   ├── Content-Addressed Envelopes (fact:sha256:...)
│   ├── Structural Node Anchors (NodeAnchor remapping)
│   ├── Strict Non-Transfer of VERIFIED Claims
│   └── Staleness Invalidation Engine
└── AI Observer Model Adapter 🟡 PLANNED (read-only, opt-in)
```

---

## 🔒 Privacy & Epistemic Boundaries

1. **Epistemic Distinctions:**
   - `OBSERVED`: Directly extracted from compiler AST or deterministic graph output.
   - `INFERRED`: AI hypothesis; **must cite at least one `evidence_id`**.
   - `VERIFIED`: Proven by an explicit test assertion or named human attestation; **must contain `verification_basis`**.
2. **Strict Staleness Invalidation:**
   - Any source snapshot change automatically invalidates `VERIFIED` facts to `STALE` with `staleness_reason = "snapshot_changed_reverification_required"`.
   - Modifying a referenced statement invalidates the anchor to `STALE` (`"anchor_unmappable"`).
3. **Data Protection:**
   - Neither evidence events nor project memory facts store raw multi-line source text or secret runtime variables.
