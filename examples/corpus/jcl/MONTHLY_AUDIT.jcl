//AUDIT99  JOB (AUDIT200),'MONTHLY AUDIT',CLASS=B,MSGCLASS=Y
//*================================================================*
//* Monthly audit review and ledger recalculation                  *
//*================================================================*
//STEP01   EXEC PGM=CBL004-TRANSACTION-AUDIT-DB2
//AUDITIN  DD DSN=CUST.OUTPUT.FILE,DISP=SHR
//SYSPRINT DD SYSOUT=*
//*----------------------------------------------------------------*
//STEP02   EXEC PGM=CBL002-ACCOUNT-LEDGER-CALC
//LEDGERIN DD DSN=LEDGER.MONTHLY.TRAN,DISP=SHR
//SYSPRINT DD SYSOUT=*
