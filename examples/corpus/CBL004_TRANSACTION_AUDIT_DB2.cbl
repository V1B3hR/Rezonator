       IDENTIFICATION DIVISION.
       PROGRAM-ID. CBL004-TRANSACTION-AUDIT-DB2.
      *================================================================*
      * Relational DB2 database audit logging and compliance check.     *
      * Uses host variables, embedded SQL CRUD operations, and SQLCA.  *
      *================================================================*
       ENVIRONMENT DIVISION.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY "SQLCA.CPY".
       01  WS-AUDIT-HOST-VARS.
           05  WS-CUST-ID              PIC X(10) VALUE 'CUST000101'.
           05  WS-TRAN-ID              PIC X(12) VALUE 'TRN998877661'.
           05  WS-TRAN-AMT             PIC 9(9)V99 VALUE 15000.00.
           05  WS-ACCOUNT-STATUS       PIC X(01) VALUE 'A'.
           05  WS-AUDIT-FLAG           PIC X(01) VALUE 'N'.
           05  WS-COMPLIANCE-CODE      PIC X(04) VALUE 'NONE'.

       PROCEDURE DIVISION.
       0000-MAIN-AUDIT.
           PERFORM 1000-FETCH-ACCOUNT-STATE.
           IF SQLCODE = 0
               PERFORM 2000-EVALUATE-COMPLIANCE
               PERFORM 3000-RECORD-AUDIT-LOG
               PERFORM 4000-UPDATE-ACCOUNT-RECORD
           ELSE
               PERFORM 8000-HANDLE-SQL-ERROR
           END-IF.
           STOP RUN.

       1000-FETCH-ACCOUNT-STATE.
           EXEC SQL
               SELECT STATUS
               INTO :WS-ACCOUNT-STATUS
               FROM ACCOUNTS
               WHERE CUST_ID = :WS-CUST-ID
           END-EXEC.

       2000-EVALUATE-COMPLIANCE.
           IF WS-TRAN-AMT >= 10000.00
               MOVE 'Y' TO WS-AUDIT-FLAG
               MOVE 'HIGH' TO WS-COMPLIANCE-CODE
           ELSE
               MOVE 'N' TO WS-AUDIT-FLAG
               MOVE 'NORM' TO WS-COMPLIANCE-CODE
           END-IF.

       3000-RECORD-AUDIT-LOG.
           EXEC SQL
               INSERT INTO AUDIT_LOG (TRAN_ID, CUST_ID, AMOUNT, FLAG)
               VALUES (:WS-TRAN-ID, :WS-CUST-ID, :WS-TRAN-AMT, :WS-AUDIT-FLAG)
           END-EXEC.

       4000-UPDATE-ACCOUNT-RECORD.
           EXEC SQL
               UPDATE ACCOUNTS
               SET LAST_AUDIT = :WS-COMPLIANCE-CODE
               WHERE CUST_ID = :WS-CUST-ID
           END-EXEC.

       8000-HANDLE-SQL-ERROR.
           DISPLAY "DB2 ERROR ENCOUNTERED, SQLCODE = " SQLCODE.
