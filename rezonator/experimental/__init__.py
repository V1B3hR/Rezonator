"""
EXPERIMENTAL — NOT PART OF THE ANALYSIS PIPELINE.

gr_geodesic.py was removed from the pipeline after the 2026-10-03 review:
its "event horizon trap" flag depended only on program size (r+ ~ 2M vs a fixed
start radius r0 = 35) and failed to flag the one genuinely non-terminating example
(ATM-DEADLOCK). It is kept here only pending an explicit decision to delete it.
Cycle / recursion detection is now done with strongly connected components in
mathy/cobol_parser.py.
"""
