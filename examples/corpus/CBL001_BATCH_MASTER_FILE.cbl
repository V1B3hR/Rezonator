       IDENTIFICATION DIVISION.
       PROGRAM-ID. CBL001-BATCH-MASTER-FILE.
      *================================================================*
      * Enterprise batch customer master file update routine.          *
      * Reads records, applies threshold logic, writes updated balances.*
      *================================================================*
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT CUST-IN-FILE ASSIGN TO 'CUSTIN.DAT'.
           SELECT CUST-OUT-FILE ASSIGN TO 'CUSTOUT.DAT'.

       DATA DIVISION.
       FILE SECTION.
       FD  CUST-IN-FILE.
       01  CUST-IN-REC                 PIC X(80).

       WORKING-STORAGE SECTION.
       COPY "CUSTREC.CPY".
       01  WS-FILE-STATUS.
           05  WS-EOF-FLAG             PIC X(01) VALUE 'N'.
           05  WS-REC-COUNT            PIC 9(07) VALUE 0.
           05  WS-HIGH-BAL-COUNT       PIC 9(07) VALUE 0.
       01  WS-THRESHOLDS.
           05  WS-CREDIT-THRESHOLD     PIC 9(9)V99 VALUE 50000.00.
           05  WS-SURCHARGE-RATE       PIC V999 VALUE 0.025.
       01  WS-CALC-FIELDS.
           05  WS-FEE-AMOUNT           PIC 9(7)V99 VALUE 0.
           05  WS-NEW-BALANCE          PIC S9(9)V99 VALUE 0.

       PROCEDURE DIVISION.
       0000-MAIN.
           PERFORM 1000-INITIALIZE.
           PERFORM 2000-PROCESS-RECORD.
           PERFORM 3000-UPDATE-TOTALS.
           PERFORM 9000-CLOSE-FILES.
           STOP RUN.

       1000-INITIALIZE.
           OPEN INPUT CUST-IN-FILE.
           OPEN OUTPUT CUST-OUT-FILE.
           MOVE 'N' TO WS-EOF-FLAG.
           MOVE 0 TO WS-REC-COUNT.
           MOVE 0 TO WS-HIGH-BAL-COUNT.

       2000-PROCESS-RECORD.
           READ CUST-IN-FILE.
           IF CUST-ACTIVE
               PERFORM 2100-CHECK-CREDIT-LIMIT
           ELSE
               MOVE 0 TO WS-FEE-AMOUNT
           END-IF.

       2100-CHECK-CREDIT-LIMIT.
           IF CUST-BALANCE > WS-CREDIT-THRESHOLD
               ADD 1 TO WS-HIGH-BAL-COUNT
               COMPUTE WS-FEE-AMOUNT = CUST-BALANCE * WS-SURCHARGE-RATE
               ADD WS-FEE-AMOUNT TO CUST-BALANCE
           ELSE
               MOVE 0 TO WS-FEE-AMOUNT
           END-IF.
           ADD 1 TO WS-REC-COUNT.

       3000-UPDATE-TOTALS.
           DISPLAY "PROCESSED RECORDS:" WS-REC-COUNT.
           DISPLAY "HIGH BALANCE FLAGS:" WS-HIGH-BAL-COUNT.

       9000-CLOSE-FILES.
           CLOSE CUST-IN-FILE.
           CLOSE CUST-OUT-FILE.
