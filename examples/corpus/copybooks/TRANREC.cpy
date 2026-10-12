      *================================================================*
      * TRANREC.CPY: Financial Transaction Record Layout               *
      * Used in ledger settlement and batch posting cycles.             *
      *================================================================*
       01  TRANSACTION-RECORD.
           05  TRAN-ID                 PIC X(12).
           05  TRAN-ACCOUNT-ID         PIC X(10).
           05  TRAN-TYPE               PIC X(02).
               88  TRAN-DEBIT          VALUE 'DR'.
               88  TRAN-CREDIT         VALUE 'CR'.
               88  TRAN-FEE            VALUE 'FE'.
           05  TRAN-AMOUNT             PIC 9(9)V99.
           05  TRAN-TIMESTAMP          PIC 9(14).
           05  TRAN-STATUS             PIC X(01).
               88  TRAN-PENDING        VALUE 'P'.
               88  TRAN-POSTED         VALUE 'D'.
               88  TRAN-REJECTED       VALUE 'R'.
