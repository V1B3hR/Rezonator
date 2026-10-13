# Multi-Program Application Portfolio Graph Specification (Filar F5)

🟢 **DELIVERED** · Status: Complete · Scope: Filar F5 (Application Portfolio Graph)

---

## 1. Executive Summary

**Filar F5** establishes the cross-program dependency and application portfolio analysis layer of Rezonator. Rather than assuming that a single repository contains an entire mainframe estate, analysis begins from an **explicit project manifest** (`sokol.portfolio.manifest.v1`), systematically resolving inter-program calls, batch JCL workflows, shared relational DB2 tables, and sequential/VSAM datasets into a unified dependency graph (`sokol.portfolio.graph.v1`).

### Key Capabilities Delivered:
1. **Portfolio Manifest Contract (`sokol.portfolio.manifest.v1`)**:
   - Explicit registration of COBOL programs, JCL jobs, known datasets, and DB2 tables.
   - Content-addressed checksum calculation and provenance tracking.
   - Strict catalog status tracking (`CATALOGED`, `UNKNOWN`, `UNRESOLVED`).

2. **Hermetic Mainframe JCL Parser (`rezonator/jcl_parser.py`)**:
   - Parses Job cards, Step executions (`EXEC PGM=` / `EXEC PROC=`), and Data Definition cards (`DD`).
   - Line continuation support (trailing commas) and comment stripping (`//*`).
   - Conditional execution modeling (`COND=(code,op[,step])`, `COND=EVEN`, `COND=ONLY`) with return-code evaluation.
   - Access intent classification from `DISP` parameter (`SHR` $\to$ `READ`, `NEW`/`MOD` $\to$ `WRITE`, `OLD` $\to$ `READ_WRITE`).
   - Identification of temporary (`&&TEMP`) and dummy (`DUMMY`, `NULLFILE`) datasets.

3. **Inter-Program Call and Resource Resolver (`rezonator/call_resolver.py`)**:
   - Static COBOL `CALL 'SUBPROG'` and CICS `LINK`/`XCTL PROGRAM('NAME')`: resolved to in-scope manifest programs (`RESOLVED`) or preserved as explicit external boundary targets (`UNRESOLVED_EXTERNAL`).
   - Dynamic COBOL `CALL WS-VAR`: strictly preserved as `DYNAMIC_UNRESOLVED` unknown edges without unverified guessing.
   - Parameter bindings: extracts `USING` arguments (stripping `BY REFERENCE`/`CONTENT`/`VALUE`) and CICS `COMMAREA`.
   - Embedded DB2 CRUD query extraction: `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `MERGE` mapped to table targets and read/write access modes.
   - COBOL file definitions: `SELECT ... ASSIGN TO ...` mapped to external dataset names.

4. **Unified Portfolio Graph & Blast-Radius Engine (`rezonator/portfolio_graph.py`)**:
   - Heterogeneous typed nodes: `program`, `job`, `step`, `dataset`, `db2_table`, and `external_program`.
   - Typed directed edges: `JOB_STEP`, `STEP_SEQUENCE`, `STEP_EXEC`, `CALL_RESOLVED`, `CALL_UNRESOLVED`, `CICS_LINK`, `PGM_SQL_READ`, `PGM_SQL_WRITE`, `STEP_READ_DSN`, `STEP_WRITE_DSN`.
   - Sparse SciPy CSR directed adjacency matrix representation.
   - **Multi-Program Blast Radius**: Computes direct 1-hop dependencies, transitive downstream reachability (impacted systems upon change), and upstream callers/triggers (systems requiring regression testing).
   - Cross-program coupling metrics: shared DB2 tables, shared datasets, pairwise coupling scores, and recursive inter-program call cycles.
   - Deterministic Markdown audit report generator (`to_markdown_report()`).

---

## 2. Mathematical Formulation

### 2.1 Graph Structure
The portfolio is modeled as a directed, attributed graph:

$$G = (V, E)$$

where the node set $V$ is partitioned into disjoint entity types:

$$V = V_{\text{PGM}} \cup V_{\text{JOB}} \cup V_{\text{STEP}} \cup V_{\text{DSN}} \cup V_{\text{TABLE}} \cup V_{\text{EXT}}$$

and the edge set $E \subseteq V \times V$ represents invocation, execution sequence, and resource access dependencies.

### 2.2 Sparse Adjacency Operator
The directed adjacency matrix $A \in \mathbb{R}^{|V| \times |V|}$ is maintained in SciPy CSR sparse format:

$$A_{ij} = \begin{cases} w_{ij} & \text{if } (v_i, v_j) \in E \\ 0 & \text{otherwise} \end{cases}$$

For $N \le 50\,000$ portfolio nodes, sparse storage ensures memory footprint remains under a few megabytes while supporting linear-time traversal.

### 2.3 Transitive Blast Radius Propagation
For any portfolio entity $v \in V$ (e.g. a modified program, an altered DB2 table schema, or an upgraded dataset format):

1. **Direct Downstream Set**:
   $$\text{Out}(v) = \{ u \in V \mid (v, u) \in E \}$$

2. **Transitive Downstream Impact (Blast Radius)**:
   $$\text{Reach}^+(v) = \{ u \in V \mid \exists \text{ path } v \rightsquigarrow u, u \ne v \}$$
   Measures all programs, batch steps, downstream datasets, and external interfaces affected if $v$ is modified.

3. **Transitive Upstream Dependencies (Callers / Invocations)**:
   $$\text{Reach}^-(v) = \{ u \in V \mid \exists \text{ path } u \rightsquigarrow v, u \ne v \}$$
   Measures all batch jobs, orchestrators, and upstream caller programs that trigger or depend on $v$.

4. **Impact Ratio**:
   $$\rho(v) = \frac{|\text{Reach}^+(v)|}{\max(1, |V| - 1)}$$

### 2.4 Cross-Program Resource Coupling Score
For any pair of distinct programs $(P_a, P_b) \in V_{\text{PGM}} \times V_{\text{PGM}}$, the coupling intensity $C(P_a, P_b)$ is computed as:

$$C(P_a, P_b) = 2 \cdot |T(P_a) \cap T(P_b)| + |D(P_a) \cap D(P_b)| + |E_{\text{call}}(P_a, P_b)| + |E_{\text{call}}(P_b, P_a)|$$

where $T(P)$ is the set of DB2 tables accessed by $P$, $D(P)$ is the set of datasets accessed by $P$, and $E_{\text{call}}$ denotes direct invocation edges.

---

## 3. Epistemic Discipline & Unknown Handling

In strict adherence to Rezonator's epistemic design rules:

| Entity / Edge | Epistemic Status | Principle |
| :--- | :--- | :--- |
| **Static CALL to in-scope program** | `OBSERVED` | Verified target present in explicit portfolio manifest |
| **Static CALL to out-of-scope program** | `UNRESOLVED` | Preserved as `EXT_PGM:{target}`; never silently dropped |
| **Dynamic CALL (`CALL WS-VAR`)** | `UNRESOLVED` | Classified as `DYNAMIC_UNRESOLVED`; no heuristic guessing |
| **DB2 table from SQL query** | `OBSERVED` | Named table syntactically extracted from SQL query |
| **Uncataloged dataset/table** | `UNKNOWN` | Missing catalog metadata explicitly tagged as `catalog_status="UNKNOWN"` |
| **JCL condition bypass** | `OBSERVED` | Evaluated against return code using formal JCL truth table |

---

## 4. Verification & Corpus Benchmark

Tested against both synthetic multi-tier pipelines and the 6-program enterprise banking corpus with batch JCL workflows:

```text
examples/corpus/
├── CBL001_BATCH_MASTER_FILE.cbl      (Batch sequential customer file processing)
├── CBL002_ACCOUNT_LEDGER_CALC.cbl     (Multi-rule balance calculation)
├── CBL003_CUSTOMER_PORTAL_CICS.cbl    (CICS terminal portal; LINK 'SECCHECK')
├── CBL004_TRANSACTION_AUDIT_DB2.cbl   (DB2 queries: ACCOUNTS, AUDIT_LOG)
├── CBL005_PAYMENT_CLEARING_CYCLE.cbl  (Batch clearing retry cycle)
├── CBL006_POLICY_RULES_TABLE.cbl      (Fee schedule evaluation)
└── jcl/
    ├── DAILY_SETTLEMENT.jcl           (SETTLE01: CBL001 -> CBL004 -> CBL005)
    └── MONTHLY_AUDIT.jcl              (AUDIT99: CBL004 -> CBL002)
```

### Verification Results (`tests/test_f5_portfolio_graph.py`):
- **14/14 tests passing in 0.006s**.
- Full test suite: **106/106 tests passing in 3.963s**.
- 100% backward compatibility maintained across `rezonator` and `mathy` entry points.
- Zero cyclic dependencies or hanging imports.

---

## 5. REST API & Web Studio Visualizer

### 5.1 Endpoints
- **`GET /api/portfolio`**: Returns structured analysis for the pre-packaged enterprise corpus (`examples/corpus/` + `examples/corpus/jcl/`).
- **`POST /api/portfolio`**:
  - Request body options:
    - `{"manifest": {...}, "format": "json"|"markdown"}`: Analyzes explicit manifest payload.
    - `{"programs": [...], "jobs": [...], "format": "json"|"markdown"}`: Analyzes ad-hoc multi-file payload.
    - `{"format": "markdown"}`: Generates executive Markdown audit report.
  - Returns `200 OK` with JSON graph/metrics or `text/markdown`.

### 5.2 Web Studio Interface (`web/`)
- **Portfolio Tab (`#tab-portfolio`)**: Interactive layered visualization of multi-program nodes:
  - Blue (`#3b82f6`): Programs
  - Purple (`#a855f7`): JCL Jobs
  - Green (`#10b981`): JCL Steps
  - Orange (`#f97316`): Datasets / DSN
  - Pink (`#ec4899`): DB2 Relational Tables
  - Red (`#ef4444`): External / Unresolved Target Modules
- **Interactive Blast Radius Inspector**: Clicking any node highlights:
  - Double cyan ring on targeted entity.
  - Glowing cyan borders on all transitive downstream impacted nodes.
  - Glowing amber borders on all upstream callers and orchestrators.
  - Live inspection metrics: Downstream impact count, upstream callers, impact ratio $\rho(v)$, and coupling hotspots.

