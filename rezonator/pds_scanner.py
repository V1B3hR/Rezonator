"""
Mainframe PDS & Directory Scanner (sokol.pds_scanner.v1).
Recursively discovers, classifies, and ingests enterprise COBOL programs,
copybooks, JCL batch streams, DB2 tables, and datasets into a unified PortfolioManifest.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from rezonator.portfolio_manifest import (
    DatasetEntry,
    Db2TableEntry,
    JclEntry,
    PortfolioManifest,
    ProgramEntry,
)


@dataclass
class ScannedFileInfo:
    path: str
    filename: str
    file_type: str  # "COBOL", "COPYBOOK", "JCL", "UNKNOWN"
    size_bytes: int
    lines_count: int
    detected_id: Optional[str] = None
    referenced_copybooks: List[str] = field(default_factory=list)
    referenced_tables: List[str] = field(default_factory=list)
    referenced_datasets: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "filename": self.filename,
            "file_type": self.file_type,
            "size_bytes": self.size_bytes,
            "lines_count": self.lines_count,
            "detected_id": self.detected_id,
            "referenced_copybooks": list(self.referenced_copybooks),
            "referenced_tables": list(self.referenced_tables),
            "referenced_datasets": list(self.referenced_datasets),
        }


@dataclass
class ScanResult:
    manifest: PortfolioManifest
    scan_stats: Dict[str, Any]
    scanned_files: List[ScannedFileInfo] = field(default_factory=list)
    unresolved_copybooks: List[str] = field(default_factory=list)
    scan_duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict(include_source_text=False),
            "scan_stats": dict(self.scan_stats),
            "scanned_files": [f.to_dict() for f in self.scanned_files],
            "unresolved_copybooks": list(self.unresolved_copybooks),
            "scan_duration_ms": round(self.scan_duration_ms, 2),
        }

    def to_markdown(self) -> str:
        s = self.scan_stats
        lines = [
            f"# Enterprise Portfolio Discovery Dossier: {self.manifest.name}",
            "",
            "> **Epistemic Invariant:** Automatic discovery extracts static syntactic anchors and datasets; "
            "it does not guarantee dialect completeness or execute batch steps.",
            "",
            "## 1. Discovery Summary",
            "",
            f"- **Scanned Directory Root:** `{s.get('root_dir', 'N/A')}`",
            f"- **Scan Duration:** `{self.scan_duration_ms:.2f} ms`",
            f"- **Total Files Examined:** `{s.get('total_files', 0)}`",
            f"- **Total Source Lines (LOC):** `{s.get('total_loc', 0):,}`",
            f"- **COBOL Programs Discovered:** `{s.get('cobol_programs', 0)}`",
            f"- **Copybooks Discovered:** `{s.get('copybooks', 0)}`",
            f"- **JCL Batch Streams Discovered:** `{s.get('jcl_jobs', 0)}`",
            f"- **Referenced DB2 Tables Discovered:** `{s.get('db2_tables', 0)}`",
            f"- **Referenced Datasets Discovered:** `{s.get('datasets', 0)}`",
            "",
            "---",
            "",
            "## 2. Inventory Breakdown",
            "",
            "| ID | Type | Path / Filename | Size (bytes) | LOC | Referenced Resources |",
            "| :--- | :---: | :--- | :---: | :---: | :--- |",
        ]

        for f in self.scanned_files:
            if f.file_type == "UNKNOWN":
                continue
            res_preview = []
            if f.referenced_tables:
                res_preview.append(f"DB2: {', '.join(f.referenced_tables[:2])}")
            if f.referenced_datasets:
                res_preview.append(f"DSN: {', '.join(f.referenced_datasets[:2])}")
            if f.referenced_copybooks:
                res_preview.append(f"CPY: {', '.join(f.referenced_copybooks[:2])}")
            res_str = "; ".join(res_preview) if res_preview else "*None*"

            lines.append(
                f"| `{f.detected_id or 'UNKNOWN'}` | `{f.file_type}` | `{f.filename}` | "
                f"`{f.size_bytes:,}` | `{f.lines_count:,}` | {res_str} |"
            )

        if self.unresolved_copybooks:
            lines.extend([
                "",
                "---",
                "",
                "## 3. Unresolved Copybook References",
                "",
                "⚠️ **The following copybooks are referenced via `COPY` statements but were not found in the scanned directories:**",
                "",
            ])
            for cpy in sorted(self.unresolved_copybooks):
                lines.append(f"- `COPY {cpy}`")

        return "\n".join(lines)


class PdsDirectoryScanner:
    """
    Automated directory and PDS partition scanner.
    Analyzes codebases with hundreds of COBOL, copybook, and JCL assets,
    auto-resolving dependencies into a ready-to-analyze PortfolioManifest.
    """

    COBOL_EXTENSIONS = {".cbl", ".cob", ".cobol", ".pco", ".sqb"}
    COPYBOOK_EXTENSIONS = {".cpy", ".copy", ".inc"}
    JCL_EXTENSIONS = {".jcl", ".job", ".cntl"}

    RE_PROGRAM_ID = re.compile(r'PROGRAM-ID\.\s+([A-Za-z0-9_-]+)', re.IGNORECASE)
    RE_JCL_JOB = re.compile(r'//([A-Za-z0-9_-]+)\s+JOB\b', re.IGNORECASE)
    RE_COPY = re.compile(r'\bCOPY\s+([A-Za-z0-9_-]+)', re.IGNORECASE)
    RE_SQL_TABLE = re.compile(r'\b(?:FROM|INTO|UPDATE)\s+([A-Za-z0-9_]+)(?:\.([A-Za-z0-9_]+))?', re.IGNORECASE)
    RE_JCL_DSN = re.compile(r'DSN=([A-Za-z0-9_.-]+)', re.IGNORECASE)

    def __init__(
        self,
        max_file_size_bytes: int = 5 * 1024 * 1024,  # 5 MB safety ceiling per file
        exclude_dirs: Optional[Set[str]] = None,
    ):
        self.max_file_size_bytes = max_file_size_bytes
        self.exclude_dirs = exclude_dirs or {".git", ".svn", "__pycache__", "build", "dist", ".pytest_cache"}

    def scan_directory(
        self,
        root_dir: str,
        manifest_name: str = "Enterprise-Portfolio",
        description: str = "",
        auto_index_copybooks: bool = True,
    ) -> ScanResult:
        """
        Recursively scans root_dir, discovers and parses all COBOL, JCL, and Copybook files,
        and constructs an integrated PortfolioManifest.
        """
        start_time = time.perf_counter()
        scanned_files: List[ScannedFileInfo] = []
        copybooks_by_name: Dict[str, str] = {}  # NAME -> file content
        copybook_paths: Dict[str, str] = {}  # NAME -> path
        raw_programs: List[Tuple[ScannedFileInfo, str]] = []
        raw_jobs: List[Tuple[ScannedFileInfo, str]] = []

        discovered_tables: Set[str] = set()
        discovered_datasets: Set[str] = set()
        all_referenced_copybooks: Set[str] = set()

        total_files = 0
        total_loc = 0

        # Phase 1: Walk directory and classify all files
        for dirpath, dirnames, filenames in os.walk(root_dir):
            dirnames[:] = [d for d in dirnames if d not in self.exclude_dirs]

            for fname in sorted(filenames):
                total_files += 1
                fpath = os.path.join(dirpath, fname)
                try:
                    fsize = os.path.getsize(fpath)
                    if fsize > self.max_file_size_bytes or fsize == 0:
                        continue

                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                except Exception:
                    continue

                lines = content.splitlines()
                loc = len(lines)
                total_loc += loc

                classification, detected_id = self._classify_file(fname, dirpath, content)
                file_info = ScannedFileInfo(
                    path=fpath,
                    filename=fname,
                    file_type=classification,
                    size_bytes=fsize,
                    lines_count=loc,
                    detected_id=detected_id,
                )

                if classification == "COPYBOOK":
                    cpy_name = (detected_id or os.path.splitext(fname)[0]).upper()
                    copybooks_by_name[cpy_name] = content
                    copybook_paths[cpy_name] = fpath
                    scanned_files.append(file_info)

                elif classification == "COBOL":
                    # Extract references
                    ref_copybooks = [m.group(1).upper() for m in self.RE_COPY.finditer(content)]
                    all_referenced_copybooks.update(ref_copybooks)
                    file_info.referenced_copybooks = ref_copybooks

                    # Extract DB2 tables
                    ref_tables = self._extract_db2_tables(content)
                    discovered_tables.update(ref_tables)
                    file_info.referenced_tables = ref_tables

                    raw_programs.append((file_info, content))
                    scanned_files.append(file_info)

                elif classification == "JCL":
                    # Extract DSNs
                    ref_dsns = [m.group(1).upper() for m in self.RE_JCL_DSN.finditer(content)]
                    discovered_datasets.update(ref_dsns)
                    file_info.referenced_datasets = ref_dsns

                    raw_jobs.append((file_info, content))
                    scanned_files.append(file_info)

                else:
                    scanned_files.append(file_info)

        # Phase 2: Assemble ProgramEntries and resolve inlined copybooks
        program_entries: List[ProgramEntry] = []
        for file_info, content in raw_programs:
            pid = file_info.detected_id or os.path.splitext(file_info.filename)[0].upper()

            # Attach matching copybooks to this program
            prog_copybooks: Dict[str, str] = {}
            if auto_index_copybooks:
                for cpy_ref in file_info.referenced_copybooks:
                    if cpy_ref in copybooks_by_name:
                        prog_copybooks[cpy_ref] = copybooks_by_name[cpy_ref]

            program_entries.append(ProgramEntry(
                program_id=pid,
                source_path=file_info.path,
                source_text=content,
                copybooks=prog_copybooks,
                metadata={
                    "filename": file_info.filename,
                    "loc": file_info.lines_count,
                    "referenced_copybooks": file_info.referenced_copybooks,
                    "referenced_tables": file_info.referenced_tables,
                },
            ))

        # Phase 3: Assemble JclEntries
        job_entries: List[JclEntry] = []
        for file_info, content in raw_jobs:
            jid = file_info.detected_id or os.path.splitext(file_info.filename)[0].upper()
            job_entries.append(JclEntry(
                job_id=jid,
                source_path=file_info.path,
                source_text=content,
                metadata={
                    "filename": file_info.filename,
                    "loc": file_info.lines_count,
                    "referenced_datasets": file_info.referenced_datasets,
                },
            ))

        # Phase 4: Assemble Dataset & Table entries
        table_entries = [
            Db2TableEntry(table_name=tbl, catalog_status="CATALOGED")
            for tbl in sorted(discovered_tables)
        ]
        dataset_entries = [
            DatasetEntry(dsn=dsn, catalog_status="CATALOGED")
            for dsn in sorted(discovered_datasets)
        ]

        # Phase 5: Determine unresolved copybooks
        unresolved = sorted(list(all_referenced_copybooks - set(copybooks_by_name.keys())))

        # Construct final PortfolioManifest
        manifest = PortfolioManifest(
            name=manifest_name,
            programs=program_entries,
            jobs=job_entries,
            known_datasets=dataset_entries,
            known_tables=table_entries,
            description=description or f"Auto-discovered from {root_dir}",
        )

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        stats = {
            "root_dir": os.path.abspath(root_dir),
            "total_files": total_files,
            "total_loc": total_loc,
            "cobol_programs": len(program_entries),
            "copybooks": len(copybooks_by_name),
            "jcl_jobs": len(job_entries),
            "db2_tables": len(table_entries),
            "datasets": len(dataset_entries),
            "unresolved_copybook_count": len(unresolved),
        }

        return ScanResult(
            manifest=manifest,
            scan_stats=stats,
            scanned_files=scanned_files,
            unresolved_copybooks=unresolved,
            scan_duration_ms=duration_ms,
        )

    def _classify_file(self, fname: str, dirpath: str, content: str) -> Tuple[str, Optional[str]]:
        """Classifies a file by extension and internal syntax patterns."""
        base_name, ext = os.path.splitext(fname)
        ext_lower = ext.lower()
        d_lower = os.path.basename(dirpath).lower()

        # Check for JCL job
        m_job = self.RE_JCL_JOB.search(content)
        if ext_lower in self.JCL_EXTENSIONS or d_lower in ("jcl", "cntl", "jobs") or m_job:
            job_id = m_job.group(1).upper() if m_job else base_name.upper()
            return "JCL", job_id

        # Check for COBOL program
        m_prog = self.RE_PROGRAM_ID.search(content)
        if m_prog:
            return "COBOL", m_prog.group(1).upper()

        if ext_lower in self.COBOL_EXTENSIONS or d_lower in ("cbl", "cob", "cobol", "src", "pgm"):
            if "PROCEDURE DIVISION" in content.upper() or "IDENTIFICATION DIVISION" in content.upper():
                return "COBOL", base_name.upper()

        # Check for Copybook
        if ext_lower in self.COPYBOOK_EXTENSIONS or d_lower in ("cpy", "copy", "copybooks", "inc"):
            return "COPYBOOK", base_name.upper()

        # Data division record snippet heuristic without procedure division
        if re.search(r'^\s*(?:01|05|10|77)\s+[A-Za-z0-9_-]+', content, re.MULTILINE):
            if "PROCEDURE DIVISION" not in content.upper() and "IDENTIFICATION DIVISION" not in content.upper():
                return "COPYBOOK", base_name.upper()

        return "UNKNOWN", None

    def _extract_db2_tables(self, content: str) -> List[str]:
        """Extracts unique DB2 table names from embedded EXEC SQL blocks."""
        tables: Set[str] = set()
        # Find all EXEC SQL ... END-EXEC blocks
        sql_blocks = re.findall(r'EXEC\s+SQL(.*?)END-EXEC', content, re.DOTALL | re.IGNORECASE)
        for block in sql_blocks:
            for match in self.RE_SQL_TABLE.finditer(block):
                tbl = match.group(2) if match.group(2) else match.group(1)
                tbl_clean = tbl.strip().upper()
                # Ignore SQL keywords falsely matched
                if tbl_clean not in {"SET", "VALUES", "WHERE", "ORDER", "GROUP", "HAVING", "CURSOR"}:
                    tables.add(tbl_clean)
        return sorted(list(tables))
