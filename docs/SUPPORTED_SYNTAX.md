# Rezonator Supported-Syntax Matrix & Parser Truthfulness Specification

This document defines the formal grammar subset, dialect support, and truthfulness contract implemented by Rezonator's deterministic COBOL front-end (`rezonator/ast_graph_builder.py`).

---

## 1. Scope & Design Philosophy

Rezonator is designed for mathematical software analysis, spectral graph decomposition, and pre-migration structural auditing. Its front-end operates under three strict integrity principles:

1. **No Silent Drops (Truthful Modeling):** Every statement in the Procedure Division must either be formally parsed into a semantic AST node or explicitly materialized as an `unsupported_stmt` node with its verb, raw code, and source line. No statement is ever silently discarded.
2. **Complete Source Provenance:** Source line numbers and copybook expansion origins (`file`, `line`) are tracked across every AST statement, variable definition, and graph node.
3. **Linear-Time Graph & Cycle Bounds:** Control flow is analyzed via linear-time Strongly Connected Component (SCC) algorithms ($O(V + E)$) with bounded cycle extraction, ensuring bounded execution even on pathological or highly connected control graphs.

---

## 2. Supported Program Divisions & Sections

| Construct | Status | Notes |
|---|---|---|
| `IDENTIFICATION DIVISION.` | **Supported** | Extracts `PROGRAM-ID. <name>` |
| `ENVIRONMENT DIVISION.` | **Ignored** | Passed through without creating graph nodes |
| `DATA DIVISION.` | **Supported** | Enters data item extraction scope |
| `WORKING-STORAGE SECTION.` | **Supported** | Parses declared state variables |
| `LOCAL-STORAGE SECTION.` | **Planned (Increment B)** | Currently treated as unmodeled data section |
| `LINKAGE SECTION.` | **Planned (Increment B)** | Currently treated as unmodeled data section |
| `PROCEDURE DIVISION.` | **Supported** | Parses paragraphs, statements, and control transfers |

---

## 3. Data Division Declarations

Variables declared in the `WORKING-STORAGE SECTION.` are modeled as program state definitions:

| Construct | Syntax Example | Model & Representation |
|---|---|---|
| Level Numbers | `01`, `05`, `10`, `77` | Recorded in `level` field |
| Alphanumeric PIC | `PIC X(10)`, `PIC A(5)` | Preserved as normalized picture string |
| Numeric PIC | `PIC 9(7)`, `PIC 9(5)V99`, `PIC S9(4)` | Preserved with sign and implied decimals |
| Initial VALUE | `VALUE "DEFAULT"` or `VALUE 1000.00` | Normalized literal value stripped of quotes |
| Copybook Variables | `COPY <member>.` | Inlined with `source_origin` pointing to copybook file |

---

## 4. Procedure Division Statements Directly Modeled

The following verbs are parsed directly into dedicated AST classes and graph node types:

| Verb / Subsystem | AST Node Class | Graph Node Type | Control / Data Flow Semantics |
|---|---|---|---|
| `PERFORM <paragraph>` | `PerformStatement` | `perform` | Creates sequential flow, `cfg_call` to target entry, and `cfg_return` from target exits |
| `IF <cond> ... ELSE ... END-IF` | `IfStatement` | `branch` | Parses simple and compound (`AND`/`OR`) conditions; creates `cfg_branch_true` and `cfg_branch_false` edges |
| `MOVE <src> TO <dest> [, <dest2>]` | `MoveStatement` | `stmt` | Creates sequential CFG edge; generates `dfg_def_use` data flow edges from previous writers to readers |
| `ADD <op> TO <dest> [GIVING <res>]` | `AddStatement` | `stmt` | Creates sequential CFG edge; marks operands as reads and destination as write |
| `SUBTRACT <op> FROM <base> [GIVING <res>]` | `SubtractStatement` | `stmt` | Creates sequential CFG edge; marks operands as reads and destination as write |
| `COMPUTE <dest> = <expr>` | `ComputeStatement` | `stmt` | Extracts variables from expression as reads; marks destination as write |
| `STOP RUN` | `StopStatement` | `stop` | Terminal barrier; halts forward sequential fallthrough |
| `GOBACK` | `GobackStatement` | `stop` | Terminal barrier; halts forward sequential fallthrough |
| `EXEC SQL <statement> END-EXEC` | `ExecSqlStatement` | `db_access` | Extracts SQL CRUD operation (`SELECT`, `INSERT`, `UPDATE`, `DELETE`), referenced DB2 tables (`db_table` nodes), and host variable reads/writes |
| `EXEC CICS <command> END-EXEC` | `ExecCicsStatement` | `external` | Extracts CICS command and external resources (`cics_resource` nodes) with `cfg_external` edge |

---

## 5. Copybook Expansion & Source Origin Mapping

Rezonator provides hermetic copybook expansion via `rezonator/copybook.py`:
- Inlines `COPY <name>` clauses from a dictionary of copybooks or a directory search path.
- Tracks `SourceOrigin(file, line)` for every line of inlined code.
- Variables and statements originated from a copybook retain an explicit `source_origin` dict:
  ```json
  "source_origin": {
    "file": "TRANREC.CPY",
    "line": 14
  }
  ```

---

## 6. Truthful Handling of Unsupported & Dialect Statements

Any statement whose verb is not among the directly modeled constructs (e.g. `DISPLAY`, `ACCEPT`, `CALL`, `OPEN`, `CLOSE`, `READ`, `WRITE`, `REWRITE`, `DELETE`, `INITIALIZE`, `SEARCH`, `EVALUATE`, `STRING`, `UNSTRING`, `SET`, `INSPECT`) is **not** silently omitted:

1. **AST Representation:** Instantiated as an `UnhandledStatement` preserving:
   - `verb`: The uppercase leading token (e.g. `"DISPLAY"`, `"CALL"`).
   - `raw_text`: The full normalized statement text.
   - `line`: The starting line number in the source file.
   - `source_origin`: The original copybook file and line if expanded.
2. **Graph Materialization:**
   - Created as a node with `node_type = "unsupported_stmt"` and `id = "<paragraph>:L<line>_UNSUPPORTED_<verb>"`.
   - Linked via normal sequential control flow (`cfg_seq`) to ensure unbroken path reachability.
   - Scanned conservatively for mentions of declared `WORKING-STORAGE` variables; all referenced variables are added to `reads`, ensuring def-use chains (`dfg_def_use`) from previous writers are preserved.
3. **Audit & Coverage Reporting:**
   The graph payload includes a dedicated `parser_coverage` section and an `unsupported_statements` inventory:
   ```json
   {
     "parser_coverage": {
       "total_statements": 42,
       "supported_statements": 38,
       "unsupported_statements": 4,
       "coverage_ratio": 0.9048
     },
     "unsupported_statements": [
       {
         "id": "1000-PROCESS:L28_UNSUPPORTED_DISPLAY",
         "verb": "DISPLAY",
         "code": "DISPLAY \"TRANSACTION ACCEPTED\"",
         "paragraph": "1000-PROCESS",
         "location": {"line": 28, "column": 0},
         "source_origin": null
       }
     ]
   }
   ```

---

## 7. Control Flow & Cycle Analysis Specification

Control-flow analysis is performed by `CycleDetector` (`rezonator/cycle_detector.py`):

1. **Strongly Connected Components (Tarjan's Algorithm):**
   - Runs in linear time $O(V + E)$ via `networkx.strongly_connected_components`.
   - Identifies non-trivial SCCs (components with $> 1$ node or self-loops).
   - A graph with zero non-trivial SCCs is certified as a DAG (`DIRECTED_ACYCLIC_FLOW`).
2. **Terminal Reachability Analysis:**
   - Evaluates whether nodes in an SCC can reach at least one terminal node (`STOP RUN` / `GOBACK`).
   - SCCs with no path to any terminal node are classified as **trapped sink components** (`trapped_scc_count`).
3. **Bounded Cycle Extraction:**
   - Simple-cycle enumeration inside non-trivial SCCs is strictly bounded:
     - `MAX_CYCLES_PER_SCC = 25`
     - `TOTAL_CYCLE_BUDGET = 100`
   - If the cycle budget is reached, `cycle_budget_exhausted: True` is flagged, preventing exponential execution on dense graphs.
4. **Data-Flow Invariant Guard Analysis:**
   - For extracted cycles, variables tested in branch conditions (`branch_guard_vars`) are compared with variables written in the cycle (`writes`).
   - Cycles where condition variables are never modified are reported as `is_invariant_hazard: True`.
5. **Epistemic Labeling:**
   - The analysis reports structural graph facts (`has_cycles`, `scc_count`, `trapped_scc_count`, `invariant_hazard_count`).
   - It does not claim formal mathematical termination proofs of arbitrary Turing-complete COBOL execution.

---

## 8. Comparator Verdicts

Structural comparisons (`rezonator/program_comparator.py`) use neutral graph-theoretic descriptions:

| Old Label | Current Neutral Verdict | Meaning |
|---|---|---|
| `SAFE_MODULAR_EXTENSION` | `STRUCTURAL_MODULAR_EXTENSION` | High NetLSD topological similarity ($< 0.08$) with conservative node/edge additions. (Not a behavioral safety certificate.) |
| `DEFECT_RESOLVED` | `HAZARD_REDUCED` | Program B eliminates a cycle hazard or trapped SCC present in Program A. |
| `CRITICAL_REGRESSION` | `CRITICAL_REGRESSION` | Program B introduces an infinite loop or trapped SCC not present in Program A. |
| `IDENTICAL_TOPOLOGY` | `IDENTICAL_TOPOLOGY` | Spectral distance $< 0.001$, representing structural graph isomorphism under renaming. |
