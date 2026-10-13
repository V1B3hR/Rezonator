"""
Portfolio Manifest Contract (sokol.portfolio.manifest.v1).
Provides an explicit catalog of programs, JCL jobs, datasets, and DB2 tables
for multi-program application portfolio analysis.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


@dataclass
class ProgramEntry:
    program_id: str
    source_path: Optional[str] = None
    source_text: Optional[str] = None
    copybooks: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.program_id = self.program_id.strip().upper()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "program_id": self.program_id,
            "source_path": self.source_path,
            "source_text": self.source_text,
            "copybooks": dict(self.copybooks),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProgramEntry:
        return cls(
            program_id=data["program_id"],
            source_path=data.get("source_path"),
            source_text=data.get("source_text"),
            copybooks=dict(data.get("copybooks") or {}),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class JclEntry:
    job_id: str
    source_path: Optional[str] = None
    source_text: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.job_id = self.job_id.strip().upper()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "source_path": self.source_path,
            "source_text": self.source_text,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> JclEntry:
        return cls(
            job_id=data["job_id"],
            source_path=data.get("source_path"),
            source_text=data.get("source_text"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class DatasetEntry:
    dsn: str
    record_format: Optional[str] = None
    is_vsam: bool = False
    catalog_status: str = "CATALOGED"  # "CATALOGED", "UNKNOWN", "UNRESOLVED"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.dsn = self.dsn.strip().upper()
        if self.catalog_status not in ("CATALOGED", "UNKNOWN", "UNRESOLVED"):
            self.catalog_status = "UNKNOWN"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dsn": self.dsn,
            "record_format": self.record_format,
            "is_vsam": self.is_vsam,
            "catalog_status": self.catalog_status,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DatasetEntry:
        return cls(
            dsn=data["dsn"],
            record_format=data.get("record_format"),
            is_vsam=bool(data.get("is_vsam", False)),
            catalog_status=str(data.get("catalog_status", "CATALOGED")),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class Db2TableEntry:
    table_name: str
    schema: Optional[str] = None
    catalog_status: str = "CATALOGED"  # "CATALOGED", "UNKNOWN"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.table_name = self.table_name.strip().upper()
        if self.schema:
            self.schema = self.schema.strip().upper()
        if self.catalog_status not in ("CATALOGED", "UNKNOWN"):
            self.catalog_status = "UNKNOWN"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_name": self.table_name,
            "schema": self.schema,
            "catalog_status": self.catalog_status,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Db2TableEntry:
        return cls(
            table_name=data["table_name"],
            schema=data.get("schema"),
            catalog_status=str(data.get("catalog_status", "CATALOGED")),
            metadata=dict(data.get("metadata") or {}),
        )


class PortfolioManifest:
    """
    Explicit Portfolio Manifest (sokol.portfolio.manifest.v1).
    Encapsulates a bounded collection of COBOL programs, JCL jobs, datasets, and DB2 tables
    without assuming an uncurated monolithic repository.
    """

    SCHEMA_VERSION = "sokol.portfolio.manifest.v1"

    def __init__(
        self,
        name: str,
        manifest_id: Optional[str] = None,
        programs: Optional[List[ProgramEntry]] = None,
        jobs: Optional[List[JclEntry]] = None,
        known_datasets: Optional[List[DatasetEntry]] = None,
        known_tables: Optional[List[Db2TableEntry]] = None,
        description: str = "",
    ):
        self.name = name.strip()
        self.description = description.strip()
        self.programs: List[ProgramEntry] = list(programs or [])
        self.jobs: List[JclEntry] = list(jobs or [])
        self.known_datasets: List[DatasetEntry] = list(known_datasets or [])
        self.known_tables: List[Db2TableEntry] = list(known_tables or [])
        self.manifest_id = manifest_id or f"manifest:{self._generate_id_suffix()}"

    def _generate_id_suffix(self) -> str:
        data = {
            "name": self.name,
            "programs": [p.program_id for p in self.programs],
            "jobs": [j.job_id for j in self.jobs],
        }
        return hashlib.sha256(_canonical_json(data)).hexdigest()[:16]

    def compute_checksum(self) -> str:
        """Computes deterministic SHA-256 fingerprint of the manifest contents."""
        payload = self.to_dict(include_source_text=False)
        return hashlib.sha256(_canonical_json(payload)).hexdigest()

    def get_program(self, program_id: str) -> Optional[ProgramEntry]:
        pid = program_id.strip().upper()
        for p in self.programs:
            if p.program_id == pid:
                return p
        return None

    def get_job(self, job_id: str) -> Optional[JclEntry]:
        jid = job_id.strip().upper()
        for j in self.jobs:
            if j.job_id == jid:
                return j
        return None

    def get_dataset(self, dsn: str) -> Optional[DatasetEntry]:
        target = dsn.strip().upper()
        for d in self.known_datasets:
            if d.dsn == target:
                return d
        return None

    def get_table(self, table_name: str) -> Optional[Db2TableEntry]:
        target = table_name.strip().upper()
        for t in self.known_tables:
            if t.table_name == target:
                return t
        return None

    def to_dict(self, include_source_text: bool = True) -> Dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "manifest_id": self.manifest_id,
            "name": self.name,
            "description": self.description,
            "programs": [
                {k: v for k, v in p.to_dict().items() if include_source_text or k != "source_text"}
                for p in sorted(self.programs, key=lambda x: x.program_id)
            ],
            "jobs": [
                {k: v for k, v in j.to_dict().items() if include_source_text or k != "source_text"}
                for j in sorted(self.jobs, key=lambda x: x.job_id)
            ],
            "known_datasets": [
                d.to_dict() for d in sorted(self.known_datasets, key=lambda x: x.dsn)
            ],
            "known_tables": [
                t.to_dict() for t in sorted(self.known_tables, key=lambda x: x.table_name)
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PortfolioManifest:
        schema = data.get("schema_version")
        if schema and schema != cls.SCHEMA_VERSION:
            raise ValueError(f"Unsupported schema version: {schema}, expected {cls.SCHEMA_VERSION}")

        programs = [ProgramEntry.from_dict(p) for p in data.get("programs", [])]
        jobs = [JclEntry.from_dict(j) for j in data.get("jobs", [])]
        datasets = [DatasetEntry.from_dict(d) for d in data.get("known_datasets", [])]
        tables = [Db2TableEntry.from_dict(t) for t in data.get("known_tables", [])]

        return cls(
            name=data.get("name", "unnamed-portfolio"),
            manifest_id=data.get("manifest_id"),
            programs=programs,
            jobs=jobs,
            known_datasets=datasets,
            known_tables=tables,
            description=data.get("description", ""),
        )

    @classmethod
    def from_files(
        cls,
        program_paths: List[str],
        jcl_paths: Optional[List[str]] = None,
        copybook_dirs: Optional[List[str]] = None,
        name: str = "portfolio-from-files",
        description: str = "",
        known_datasets: Optional[List[str]] = None,
        known_tables: Optional[List[str]] = None,
    ) -> PortfolioManifest:
        """Constructs a manifest from file paths on the filesystem."""
        programs: List[ProgramEntry] = []
        for path in program_paths:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            m = re.search(r'PROGRAM-ID\.\s+([A-Za-z0-9_-]+)', content, re.IGNORECASE)
            pid = m.group(1).upper() if m else os.path.splitext(os.path.basename(path))[0].upper()
            programs.append(ProgramEntry(
                program_id=pid,
                source_path=path,
                source_text=content,
                metadata={"file_size": len(content), "filename": os.path.basename(path)},
            ))

        jobs: List[JclEntry] = []
        for path in (jcl_paths or []):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            m = re.search(r'//([A-Za-z0-9_-]+)\s+JOB\b', content, re.IGNORECASE)
            jid = m.group(1).upper() if m else os.path.splitext(os.path.basename(path))[0].upper()
            jobs.append(JclEntry(
                job_id=jid,
                source_path=path,
                source_text=content,
                metadata={"file_size": len(content), "filename": os.path.basename(path)},
            ))

        dataset_entries = [
            DatasetEntry(dsn=d, catalog_status="CATALOGED") for d in (known_datasets or [])
        ]
        table_entries = [
            Db2TableEntry(table_name=t, catalog_status="CATALOGED") for t in (known_tables or [])
        ]

        return cls(
            name=name,
            programs=programs,
            jobs=jobs,
            known_datasets=dataset_entries,
            known_tables=table_entries,
            description=description,
        )
