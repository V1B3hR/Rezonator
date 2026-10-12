       IDENTIFICATION DIVISION.
       PROGRAM-ID. CBL005-PAYMENT-CLEARING-CYCLE.
      *================================================================*
      * Payment clearing retry cycle and reconciliation module.        *
      * Tests cycle detection, SCC bounds, and termination guards.      *
      *================================================================*
       ENVIRONMENT DIVISION.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-CLEARING-CONTROLS.
           05  WS-BATCH-ID             PIC X(08) VALUE 'CLR20261'.
           05  WS-RETRY-COUNT          PIC 9(02) VALUE 0.
           05  WS-MAX-RETRIES          PIC 9(02) VALUE 3.
           05  WS-CLEARING-STATUS      PIC X(01) VALUE 'P'.
           05  WS-NETWORK-ACK          PIC X(01) VALUE 'N'.
       01  WS-BALANCE-TOTALS.
           05  WS-CLEARED-AMT          PIC 9(11)V99 VALUE 0.
           05  WS-HOLD-AMT             PIC 9(11)V99 VALUE 250000.00.

       PROCEDURE DIVISION.
       0000-CLEARING-MAIN.
           PERFORM 1000-INITIATE-SESSION.
           PERFORM 2000-EXECUTE-CLEARING-CYCLE.
           PERFORM 3000-FINALIZE-SESSION.
           STOP RUN.

       1000-INITIATE-SESSION.
           MOVE 0 TO WS-RETRY-COUNT.
           MOVE 'P' TO WS-CLEARING-STATUS.
           MOVE 'N' TO WS-NETWORK-ACK.

       2000-EXECUTE-CLEARING-CYCLE.
           ADD 1 TO WS-RETRY-COUNT.
           IF WS-NETWORK-ACK = 'Y'
               MOVE 'C' TO WS-CLEARING-STATUS
               ADD WS-HOLD-AMT TO WS-CLEARED-AMT
           ELSE
               IF WS-RETRY-COUNT < WS-MAX-RETRIES
                   PERFORM 2100-POLL-NETWORK
                   PERFORM 2000-EXECUTE-CLEARING-CYCLE
               ELSE
                   MOVE 'F' TO WS-CLEARING-STATUS
                   PERFORM 2200-ESCALATE-FAILURE
               END-IF
           END-IF.

       2100-POLL-NETWORK.
           IF WS-RETRY-COUNT = 2
               MOVE 'Y' TO WS-NETWORK-ACK
           ELSE
               MOVE 'N' TO WS-NETWORK-ACK
           END-IF.

       2200-ESCALATE-FAILURE.
           DISPLAY "MAX CLEARING RETRIES EXCEEDED FOR BATCH: " WS-BATCH-ID.

       3000-FINALIZE-SESSION.
           DISPLAY "FINAL CLEARING STATUS: " WS-CLEARING-STATUS.
           DISPLAY "TOTAL CLEARED AMOUNT: " WS-CLEARED-AMT.
