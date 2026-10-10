"""Deterministic Enterprise COBOL COPYBOOK expansion."""

from pathlib import Path
import re
from dataclasses import dataclass
from typing import List, Mapping, Optional, Sequence, Tuple


class CopybookResolutionError(ValueError):
    """Raised when a COPYBOOK cannot be resolved or contains a cycle."""


@dataclass(frozen=True)
class SourceOrigin:
    """Source-level provenance for one line of the expanded COBOL stream."""

    source: str
    line: int
    copybook_stack: Tuple[str, ...] = ()
    replacements: Tuple[Tuple[str, str], ...] = ()

    def to_dict(self):
        return {
            "source": self.source,
            "line": self.line,
            "copybook_stack": list(self.copybook_stack),
            "replacements": [
                {"old": old, "new": new}
                for old, new in self.replacements
            ],
        }


@dataclass(frozen=True)
class InlinedSource:
    """Expanded source plus one provenance record per emitted line."""

    text: str
    line_origins: Tuple[SourceOrigin, ...]


class CopybookInliner:
    """Expands nested COPY statements without changing the caller's source."""

    _COPY_RE = re.compile(
        r"(?im)^(?P<indent>\s*)(?:\d{6}\s+)?COPY\s+"
        r"(?P<name>(?:['\"][^'\"]+['\"]|[A-Za-z0-9_$#@.-]+))"
        r"(?:\s+REPLACING\s+(?P<replacing>.*?))?\s*\.\s*$"
    )
    _REPLACEMENT_RE = re.compile(r"==(?P<old>.*?)==\s+BY\s+==(?P<new>.*?)==", re.DOTALL)

    def __init__(
        self,
        copybooks: Optional[Mapping[str, str]] = None,
        search_paths: Optional[Sequence[str]] = None,
        max_depth: int = 64,
    ):
        self.copybooks = {
            self._normalize_name(name): content
            for name, content in (copybooks or {}).items()
        }
        self.search_paths = tuple(Path(path) for path in (search_paths or ()))
        self.max_depth = max_depth

    def inline(self, source_code: str) -> str:
        """Return source with all resolvable COPY statements expanded."""
        return self.inline_with_provenance(source_code).text

    def inline_with_provenance(self, source_code: str) -> InlinedSource:
        """Expand COPY statements and preserve line-level source provenance."""
        lines, origins = self._inline_lines(
            source_code,
            source_name="main",
            active=(),
            depth=0,
            inherited_replacements=(),
        )
        return InlinedSource("\n".join(lines), tuple(origins))

    def _inline_lines(
        self,
        text: str,
        source_name: str,
        active: Tuple[str, ...],
        depth: int,
        inherited_replacements: Tuple[Tuple[str, str], ...],
    ) -> Tuple[List[str], List[SourceOrigin]]:
        if depth > self.max_depth:
            raise CopybookResolutionError(
                f"COPYBOOK nesting exceeds max_depth={self.max_depth}: {' -> '.join(active)}"
            )

        output_lines: List[str] = []
        output_origins: List[SourceOrigin] = []
        for line_number, raw_line in enumerate(text.splitlines(), 1):
            match = self._COPY_RE.fullmatch(raw_line.rstrip("\r\n"))
            if not match:
                output_lines.append(raw_line)
                output_origins.append(
                    SourceOrigin(
                        source=source_name,
                        line=line_number,
                        copybook_stack=active,
                        replacements=inherited_replacements,
                    )
                )
                continue

            requested_name = self._normalize_name(match.group("name"))
            resolved_name, content = self._resolve(requested_name)
            if resolved_name in active:
                chain = " -> ".join((*active, resolved_name))
                raise CopybookResolutionError(f"Circular COPYBOOK reference detected: {chain}")

            replacements = tuple(self._parse_replacements(match.group("replacing") or ""))
            for old, new in replacements:
                content = content.replace(old, new)

            nested_lines, nested_origins = self._inline_lines(
                content,
                source_name=resolved_name,
                active=(*active, resolved_name),
                depth=depth + 1,
                inherited_replacements=(*inherited_replacements, *replacements),
            )
            indent = match.group("indent")
            if indent:
                nested_lines = [
                    nested_lines[0],
                    *[indent + nested_line for nested_line in nested_lines[1:]],
                ] if nested_lines else []
            output_lines.extend(nested_lines)
            output_origins.extend(nested_origins)

        return output_lines, output_origins

    def _resolve(self, name: str) -> Tuple[str, str]:
        for mapping_name in (name, f"{name}.CPY"):
            normalized_name = self._normalize_name(mapping_name)
            if normalized_name in self.copybooks:
                return normalized_name, self.copybooks[normalized_name]

        for candidate_name in (name, f"{name}.CPY", f"{name}.cpy"):
            for directory in self.search_paths:
                candidate = directory / candidate_name
                if candidate.is_file():
                    return self._normalize_name(candidate.name), candidate.read_text(encoding="utf-8")

        searched = ", ".join(str(path) for path in self.search_paths) or "<mapping only>"
        raise CopybookResolutionError(
            f"COPYBOOK '{name}' not found. Search paths: {searched}"
        )

    @classmethod
    def _parse_replacements(cls, replacing: str):
        matches = list(cls._REPLACEMENT_RE.finditer(replacing))
        if replacing.strip() and not matches:
            raise CopybookResolutionError(
                "Unsupported COPYBOOK REPLACING syntax; expected ==old== BY ==new=="
            )
        return [(match.group("old"), match.group("new")) for match in matches]

    @staticmethod
    def _normalize_name(name: str) -> str:
        return name.strip().strip("'\"").upper()
