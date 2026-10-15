"""
Quality Hardening: AST & Lexer Fuzzing, Mutation Resilience, and Invariant Verification.
Validates that Rezonator parsers (COBOL, JCL, Copybook) are fully resilient to
pathological inputs, malformed fixed-format columns, truncated statements, circular references,
and adversarial text without infinite loops or uncaught crashes.
"""

import string
import pytest
from hypothesis import given, settings, strategies as st

from rezonator.cobol_parser import CobolParser
from rezonator.jcl_parser import JclParser
from rezonator.copybooks import CopybookInliner, CopybookResolutionError
from rezonator.limits import ResourceLimitError


def test_malformed_fixed_format_columns_resilience():
    """Verify that random text in sequence (1-6) and identification (73-80) areas parses safely."""
    malformed_source = (
        "000100 IDENTIFICATION DIVISION.                                        TAG001\n"
        "000200 PROGRAM-ID. FUZZ01.                                             TAG002\n"
        "000300 ENVIRONMENT DIVISION.                                           TAG003\n"
        "000400 DATA DIVISION.                                                  TAG004\n"
        "000500 WORKING-STORAGE SECTION.                                        TAG005\n"
        "000600 01  WS-BALANCE PIC 9(7)V99 VALUE 1000.00.                        TAG006\n"
        "000700* Corrupted comment area with special chars: @#$%^&*()_+-=~`     TAG007\n"
        "000800 PROCEDURE DIVISION.                                             TAG008\n"
        "000900 0000-MAIN.                                                      TAG009\n"
        "001000     ADD 50 TO WS-BALANCE.                                        TAG010\n"
        "001100     STOP RUN.                                                    TAG011\n"
    )
    parser = CobolParser()
    graph = parser.parse(malformed_source)

    assert graph is not None
    assert "nodes" in graph
    assert "edges" in graph
    assert len(graph["nodes"]) >= 2
    assert "WS-BALANCE" in parser.variables


def test_truncated_and_unclosed_exec_blocks():
    """Verify that unclosed EXEC SQL and EXEC CICS blocks do not hang or crash."""
    truncated_sql = (
        "IDENTIFICATION DIVISION.\n"
        "PROGRAM-ID. UNCLOSED-SQL.\n"
        "PROCEDURE DIVISION.\n"
        "0000-MAIN.\n"
        "    EXEC SQL\n"
        "        SELECT BALANCE FROM ACCOUNTS\n"
        "    MOVE 10 TO WS-FLAG.\n"
        "    STOP RUN.\n"
    )
    parser = CobolParser()
    graph = parser.parse(truncated_sql)

    assert graph is not None
    assert len(graph["nodes"]) >= 1


def test_circular_copybook_expansion_safety():
    """Verify that circular copybook dependencies raise clean CopybookResolutionError and never recurse infinitely."""
    copybooks = {
        "CPYA": "01 REC-A PIC X(10).\n       COPY CPYB.",
        "CPYB": "01 REC-B PIC X(10).\n       COPY CPYC.",
        "CPYC": "01 REC-C PIC X(10).\n       COPY CPYA.",
    }
    source = (
        "IDENTIFICATION DIVISION.\n"
        "PROGRAM-ID. CIRCTEST.\n"
        "DATA DIVISION.\n"
        "WORKING-STORAGE SECTION.\n"
        "    COPY CPYA.\n"
        "PROCEDURE DIVISION.\n"
        "    STOP RUN.\n"
    )
    with pytest.raises(CopybookResolutionError) as exc_info:
        CopybookInliner(copybooks).inline(source)
    assert any(term in str(exc_info.value).lower() for term in ("circular", "cycle", "depth"))


def test_malformed_jcl_stream_resilience():
    """Verify that broken or truncated JCL cards are safely handled without crashes."""
    pathological_jcl = (
        "// broken line without job card\n"
        "//JOB01    JOB (9999),'TEST JOB\n"
        "//INVALID CARD HERE\n"
        "//STEP01   EXEC PGM=\n"
        "//DD1      DD DSN=,DISP=\n"
        "//STEP02   EXEC PROC=MYPROC,COND=(4,LT,\n"
        "/*\n"
        "//\n"
    )
    parser = JclParser()
    jobs = parser.parse(pathological_jcl)

    assert isinstance(jobs, list)
    if jobs:
        assert jobs[0].job_name == "JOB01"


@given(st.text(alphabet=string.ascii_letters + string.digits + " \t\n.-_()*/'\"", max_size=1000))
@settings(max_examples=40, deadline=2000)
def test_hypothesis_fuzzing_cobol_parser(random_cobol_text):
    """Property-based fuzzing: arbitrary text must never cause uncaught crashes or infinite loops."""
    parser = CobolParser()
    try:
        graph = parser.parse(random_cobol_text)
        assert isinstance(graph, dict)
        assert "nodes" in graph
        assert "edges" in graph
    except (ResourceLimitError, CopybookResolutionError):
        # Expected domain rejections
        pass


@given(st.text(alphabet=string.ascii_letters + string.digits + " \t\n=,()/'\"", max_size=1000))
@settings(max_examples=40, deadline=2000)
def test_hypothesis_fuzzing_jcl_parser(random_jcl_text):
    """Property-based fuzzing: arbitrary text fed into JclStreamParser must terminate cleanly."""
    parser = JclParser()
    try:
        jobs = parser.parse(random_jcl_text)
        assert isinstance(jobs, list)
    except ResourceLimitError:
        pass
