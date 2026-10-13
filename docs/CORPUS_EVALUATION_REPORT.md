# Rezonator Enterprise COBOL Corpus Evaluation Report

**Status:** 🟢 **DELIVERED (Near-Term Pilot Gate)**

## 1. Executive Summary

- **Corpus Directory:** `examples\corpus`
- **Evaluated Programs:** 6
- **Total Non-Comment LOC:** 339
- **Total Procedure Division Statements:** 136
- **Supported Statements:** 120
- **Unsupported (Truthfully Modeled) Statements:** 16
- **Aggregate Parser Coverage Ratio:** 88.24%
- **Mean Per-Program Coverage Ratio:** 88.57%
- **Total Corpus Pipeline Execution Time:** 79.84 ms
- **Sokół Evidence Events Validation:** PASS (100% verified)

---

## 2. Program-Level Breakdown

| File | Program ID | LOC | Stmts | Supp. | Unsupp. | Coverage | Nodes | Edges | Cycles | Hazard | Time (ms) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|:---:|---:|
| `CBL001_BATCH_MASTER_FILE.cbl` | `CBL001-BATCH-MASTER-FILE` | 58 | 24 | 17 | 7 | 70.8% | 24 | 44 | 0 | NO | 35.1 |
| `CBL002_ACCOUNT_LEDGER_CALC.cbl` | `CBL002-ACCOUNT-LEDGER-CALC` | 69 | 31 | 29 | 2 | 93.5% | 31 | 73 | 0 | NO | 10.4 |
| `CBL003_CUSTOMER_PORTAL_CICS.cbl` | `CBL003-CUSTOMER-PORTAL-CICS` | 52 | 20 | 20 | 0 | 100.0% | 24 | 41 | 0 | NO | 8.2 |
| `CBL004_TRANSACTION_AUDIT_DB2.cbl` | `CBL004-TRANSACTION-AUDIT-DB2` | 52 | 16 | 15 | 1 | 93.8% | 18 | 36 | 0 | NO | 8.4 |
| `CBL005_PAYMENT_CLEARING_CYCLE.cbl` | `CBL005-PAYMENT-CLEARING-CYCLE` | 49 | 22 | 19 | 3 | 86.4% | 22 | 48 | 9 | ⚠️ YES | 9.3 |
| `CBL006_POLICY_RULES_TABLE.cbl` | `CBL006-POLICY-RULES-TABLE` | 59 | 23 | 20 | 3 | 87.0% | 23 | 51 | 0 | NO | 8.4 |

---

## 3. Unsupported Syntax Gap Inventory

Statements outside the directly modeled AST grammar are preserved as `unsupported_stmt` nodes with their verb, raw text, and line location. The table below catalogs unmodeled verbs across the corpus, identifying priorities for parser expansion:

| Statement Verb | Corpus Occurrences | Severity / Role | Roadmap Action |
|---|---:|---|---|
| `DISPLAY` | 10 | `coverage_gap` | Terminal I/O; emits informational text. Model as side-effect node. |
| `OPEN` | 2 | `coverage_gap` | File subsystem access; registers dataset handles. |
| `CLOSE` | 2 | `coverage_gap` | File subsystem termination; deregisters dataset handles. |
| `READ` | 1 | `coverage_gap` | File record ingestion; introduces def-use data sources. |
| `INITIALIZE` | 1 | `coverage_gap` | State variable initialization; generates DFG write definitions. |

---

## 4. Cycle Detection & Semantic Hazard Evaluation

- **Files with CFG Cycles:** 1 of 6
- **Files Flagged with Deadlock Hazard:** 1 of 6
- **Findings:** Cycles in CBL005 reflect bounded retry recursion. The cycle detector detects the topological recurrence, while heuristic hazard flags indicate potential nontermination requiring human verification of guard predicates.

> [!IMPORTANT]
> A topological cycle in the Control Flow Graph indicates recurring paragraph execution paths, > but does not by itself prove infinite loop nontermination. Guard condition evaluation remains > heuristic; human audit review must verify loop counter bounds (e.g. `WS-RETRY-COUNT < WS-MAX-RETRIES`).

---

## 5. Verification of Pilot Release Gate Criteria

1. **No Silent Drops:** Verified. All unhandled statements materialized as `unsupported_stmt` nodes.
2. **Sparse Graph Processing:** Verified. All programs processed as SciPy CSR operators without dense conversion.
3. **Cycle Distinctions:** Verified. Topological cycles separated from heuristic nontermination claims.
4. **Traceable Audit Findings:** Verified. All findings linked to line numbers and copybook origins.
5. **Context Slicing:** Verified. ProgramSlicer successfully extracted source-mapped packets under token budgets.
6. **Corpus Evaluation:** Completed on representative banking, CICS, DB2, and clearing batch programs.
7. **Sokół Evidence Contract:** Verified. Versioned envelopes round-trip through JSONL serializer without source text or variable leakage.
