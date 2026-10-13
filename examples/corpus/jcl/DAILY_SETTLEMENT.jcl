//SETTLE01 JOB (ACCT101),'DAILY SETTLEMENT',CLASS=A,MSGCLASS=X
//*================================================================*
//* Batch customer settlement and audit workflow                   *
//*================================================================*
//STEP01   EXEC PGM=CBL001-BATCH-MASTER-FILE
//CUSTIN   DD DSN=CUST.MASTER.FILE,DISP=SHR
//CUSTOUT  DD DSN=CUST.OUTPUT.FILE,
//            DISP=(NEW,CATLG,DELETE),
//            SPACE=(CYL,(10,5),RLSE),
//            UNIT=SYSDA
//SYSPRINT DD SYSOUT=*
//*----------------------------------------------------------------*
//STEP02   EXEC PGM=CBL004-TRANSACTION-AUDIT-DB2,
//            COND=(4,LT)
//AUDITIN  DD DSN=CUST.OUTPUT.FILE,DISP=SHR
//SYSPRINT DD SYSOUT=*
//*----------------------------------------------------------------*
//STEP03   EXEC PGM=CBL005-PAYMENT-CLEARING-CYCLE,
//            COND=(0,NE,STEP02)
//CLRREP   DD DSN=CLEARING.DAILY.REPORT,DISP=(NEW,CATLG)
//SYSPRINT DD SYSOUT=*
