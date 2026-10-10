"""Cryptographic provenance metadata for Rezonator analysis results."""

from datetime import datetime, timezone
import hashlib
from typing import Dict

from rezonator import __version__

SOLVER_SEED = 42


def _sha256(source_code: str) -> str:
    return hashlib.sha256(source_code.encode("utf-8")).hexdigest()


def source_provenance(source_code: str) -> Dict[str, object]:
    """Return auditable metadata for one deterministic analysis input."""
    return {
        "source_sha256": _sha256(source_code),
        "rezonator_version": __version__,
        "solver_seed": SOLVER_SEED,
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def comparison_provenance(source_a: str, source_b: str) -> Dict[str, object]:
    """Return auditable metadata for a two-program comparison."""
    return {
        "source_a_sha256": _sha256(source_a),
        "source_b_sha256": _sha256(source_b),
        "rezonator_version": __version__,
        "solver_seed": SOLVER_SEED,
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
