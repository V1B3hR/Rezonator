       IDENTIFICATION DIVISION.
       PROGRAM-ID. CBL002-ACCOUNT-LEDGER-CALC.
      *================================================================*
      * Financial transaction ledger calculation and settlement module. *
      * Evaluates debits, credits, interest, and maintenance fees.     *
      *================================================================*
       ENVIRONMENT DIVISION.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY "TRANREC.CPY".
       01  WS-LEDGER-ACCUMULATORS.
           05  WS-TOTAL-DEBITS         PIC S9(11)V99 VALUE 0.
           05  WS-TOTAL-CREDITS        PIC S9(11)V99 VALUE 0.
           05  WS-NET-SETTLEMENT       PIC S9(11)V99 VALUE 0.
           05  WS-TRAN-COUNT           PIC 9(08) VALUE 0.
           05  WS-REJECT-COUNT         PIC 9(08) VALUE 0.
       01  WS-RATES.
           05  WS-DEBIT-FEE-PCT        PIC V999 VALUE 0.015.
           05  WS-MIN-FEE              PIC 9(3)V99 VALUE 2.50.
           05  WS-MAX-FEE              PIC 9(3)V99 VALUE 75.00.
       01  WS-WORK-AMOUNTS.
           05  WS-CALC-FEE             PIC 9(7)V99 VALUE 0.
           05  WS-ADJUSTED-AMT         PIC 9(9)V99 VALUE 0.

       PROCEDURE DIVISION.
       0000-PROCESS-TRANSACTION.
           PERFORM 1000-VALIDATE-RECORD.
           IF TRAN-STATUS = 'P'
               PERFORM 2000-APPLY-SETTLEMENT
           ELSE
               PERFORM 3000-HANDLE-REJECTION
           END-IF.
           PERFORM 4000-COMPUTE-LEDGER-NET.
           STOP RUN.

       1000-VALIDATE-RECORD.
           IF TRAN-AMOUNT <= 0
               MOVE 'R' TO TRAN-STATUS
               ADD 1 TO WS-REJECT-COUNT
           ELSE
               MOVE 'P' TO TRAN-STATUS
               ADD 1 TO WS-TRAN-COUNT
           END-IF.

       2000-APPLY-SETTLEMENT.
           IF TRAN-TYPE = 'DR'
               PERFORM 2100-PROCESS-DEBIT
           ELSE
               IF TRAN-TYPE = 'CR'
                   PERFORM 2200-PROCESS-CREDIT
               ELSE
                   PERFORM 2300-PROCESS-FEE
               END-IF
           END-IF.

       2100-PROCESS-DEBIT.
           COMPUTE WS-CALC-FEE = TRAN-AMOUNT * WS-DEBIT-FEE-PCT.
           IF WS-CALC-FEE < WS-MIN-FEE
               MOVE WS-MIN-FEE TO WS-CALC-FEE
           END-IF.
           IF WS-CALC-FEE > WS-MAX-FEE
               MOVE WS-MAX-FEE TO WS-CALC-FEE
           END-IF.
           ADD TRAN-AMOUNT TO WS-TOTAL-DEBITS.
           ADD WS-CALC-FEE TO WS-TOTAL-DEBITS.
           MOVE 'D' TO TRAN-STATUS.

       2200-PROCESS-CREDIT.
           ADD TRAN-AMOUNT TO WS-TOTAL-CREDITS.
           MOVE 'D' TO TRAN-STATUS.

       2300-PROCESS-FEE.
           ADD TRAN-AMOUNT TO WS-TOTAL-DEBITS.
           MOVE 'D' TO TRAN-STATUS.

       3000-HANDLE-REJECTION.
           DISPLAY "TRANSACTION REJECTED: " TRAN-ID.

       4000-COMPUTE-LEDGER-NET.
           SUBTRACT WS-TOTAL-DEBITS FROM WS-TOTAL-CREDITS GIVING WS-NET-SETTLEMENT.
           DISPLAY "NET SETTLEMENT POSITION: " WS-NET-SETTLEMENT.
