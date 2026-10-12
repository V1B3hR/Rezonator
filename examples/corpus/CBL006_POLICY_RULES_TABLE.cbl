       IDENTIFICATION DIVISION.
       PROGRAM-ID. CBL006-POLICY-RULES-TABLE.
      *================================================================*
      * Insurance policy underwriting rules and table evaluation.      *
      * Features tabular data structures and complex Boolean branching.*
      *================================================================*
       ENVIRONMENT DIVISION.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-REQUEST.
           05  REQ-POLICY-ID           PIC X(10) VALUE 'POL-90210'.
           05  REQ-AGE                 PIC 9(03) VALUE 45.
           05  REQ-SMOKER              PIC X(01) VALUE 'N'.
           05  REQ-COVERAGE-AMT        PIC 9(09)V99 VALUE 500000.00.
           05  REQ-RISK-CLASS          PIC X(02) VALUE 'ST'.
       01  WS-UNDERWRITING-TABLE.
           05  TIER-ENTRY OCCURS 5 TIMES.
               10  TIER-CODE           PIC X(02) VALUE 'ST'.
               10  TIER-BASE-RATE      PIC V999 VALUE 0.004.
               10  TIER-MAX-COVERAGE   PIC 9(09)V99 VALUE 1000000.00.
       01  WS-RESULT-FACTORS.
           05  CALC-PREMIUM            PIC 9(07)V99 VALUE 0.
           05  RISK-SURCHARGE          PIC 9(07)V99 VALUE 0.
           05  FINAL-APPROVED-PREMIUM  PIC 9(07)V99 VALUE 0.
           05  APPROVAL-STATUS         PIC X(01) VALUE 'P'.

       PROCEDURE DIVISION.
       0000-EVALUATE-POLICY.
           PERFORM 1000-INITIALIZE-FACTORS.
           PERFORM 2000-CHECK-ELIGIBILITY.
           IF APPROVAL-STATUS = 'A'
               PERFORM 3000-CALCULATE-PREMIUM
               PERFORM 4000-APPLY-RISK-LOADINGS
           ELSE
               PERFORM 8000-DECLINE-APPLICATION
           END-IF.
           PERFORM 9000-FINALIZE-QUOTE.
           STOP RUN.

       1000-INITIALIZE-FACTORS.
           INITIALIZE WS-RESULT-FACTORS.
           MOVE 'P' TO APPROVAL-STATUS.

       2000-CHECK-ELIGIBILITY.
           IF REQ-AGE >= 18 AND REQ-AGE <= 75
               IF REQ-COVERAGE-AMT <= 1000000.00
                   MOVE 'A' TO APPROVAL-STATUS
               ELSE
                   MOVE 'D' TO APPROVAL-STATUS
               END-IF
           ELSE
               MOVE 'D' TO APPROVAL-STATUS
           END-IF.

       3000-CALCULATE-PREMIUM.
           COMPUTE CALC-PREMIUM = REQ-COVERAGE-AMT * 0.004.

       4000-APPLY-RISK-LOADINGS.
           IF REQ-SMOKER = 'Y' OR REQ-AGE > 60
               COMPUTE RISK-SURCHARGE = CALC-PREMIUM * 0.35
               ADD RISK-SURCHARGE TO CALC-PREMIUM
           END-IF.
           MOVE CALC-PREMIUM TO FINAL-APPROVED-PREMIUM.

       8000-DECLINE-APPLICATION.
           MOVE 0 TO FINAL-APPROVED-PREMIUM.
           DISPLAY "POLICY APPLICATION DECLINED: AGE/COVERAGE OUT OF BOUNDS".

       9000-FINALIZE-QUOTE.
           DISPLAY "FINAL QUOTE PREMIUM: " FINAL-APPROVED-PREMIUM.
