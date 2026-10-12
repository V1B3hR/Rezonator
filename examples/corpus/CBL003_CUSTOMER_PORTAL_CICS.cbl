       IDENTIFICATION DIVISION.
       PROGRAM-ID. CBL003-CUSTOMER-PORTAL-CICS.
      *================================================================*
      * CICS online customer inquiry and navigation transaction.       *
      * Handles 3270 screen map interaction and program linking.       *
      *================================================================*
       ENVIRONMENT DIVISION.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY "DFHAID.CPY".
       01  WS-COMMUNICATION.
           05  WS-TRAN-ID              PIC X(04) VALUE 'CP01'.
           05  WS-USER-ID              PIC X(08) VALUE 'USR001'.
           05  WS-AUTH-LEVEL           PIC 9(02) VALUE 1.
           05  WS-MAP-STATUS           PIC X(01) VALUE 'N'.
           05  WS-RESPONSE-CODE        PIC S9(08) VALUE 0.
       01  WS-MAP-FIELDS.
           05  MAP-ACCT-IN             PIC X(10) VALUE SPACES.
           05  MAP-MSG-OUT             PIC X(60) VALUE SPACES.

       PROCEDURE DIVISION.
       0000-PROCESS-PORTAL.
           PERFORM 1000-RECEIVE-SCREEN.
           IF WS-RESPONSE-CODE = 0
               PERFORM 2000-AUTHORIZE-USER
               PERFORM 3000-PROCESS-COMMAND
           ELSE
               PERFORM 8000-HANDLE-MAP-ERROR
           END-IF.
           PERFORM 9000-SEND-AND-RETURN.
           GOBACK.

       1000-RECEIVE-SCREEN.
           EXEC CICS RECEIVE MAP('CUSTM01')
               END-EXEC.
           MOVE 0 TO WS-RESPONSE-CODE.

       2000-AUTHORIZE-USER.
           EXEC CICS LINK PROGRAM('SECCHECK')
               END-EXEC.
           IF WS-AUTH-LEVEL >= 1
               MOVE 'Y' TO WS-MAP-STATUS
           ELSE
               MOVE 'N' TO WS-MAP-STATUS
               MOVE 'UNAUTHORIZED ACTION REQUESTED' TO MAP-MSG-OUT
           END-IF.

       3000-PROCESS-COMMAND.
           IF WS-MAP-STATUS = 'Y'
               EXEC CICS SYNCPOINT
                   END-EXEC
               MOVE 'TRANSACTION COMPLETED SUCCESSFULLY' TO MAP-MSG-OUT
           END-IF.

       8000-HANDLE-MAP-ERROR.
           MOVE 'TERMINAL INPUT TRANSMISSION ERROR' TO MAP-MSG-OUT.

       9000-SEND-AND-RETURN.
           EXEC CICS SEND MAP('CUSTM01')
               END-EXEC.
           EXEC CICS RETURN
               END-EXEC.
