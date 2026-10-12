      *================================================================*
      * CUSTREC.CPY: Customer Master Record Layout                      *
      * Used in batch master file processing and billing routines.      *
      *================================================================*
       01  CUSTOMER-RECORD.
           05  CUST-ID                 PIC X(10).
           05  CUST-STATUS             PIC X(01).
               88  CUST-ACTIVE         VALUE 'A'.
               88  CUST-SUSPENDED      VALUE 'S'.
               88  CUST-CLOSED         VALUE 'C'.
           05  CUST-NAME               PIC X(35).
           05  CUST-BALANCE            PIC S9(9)V99.
           05  CUST-CREDIT-LIMIT       PIC 9(9)V99.
           05  CUST-LAST-PAY-DATE      PIC 9(08).
           05  CUST-TIER-CODE          PIC 9(02).
