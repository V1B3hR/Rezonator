      *================================================================*
      * SQLCA.CPY: Standard SQL Communications Area Mock               *
      * Used in embedded DB2 / relational queries and status handling. *
      *================================================================*
       01  SQLCA.
           05  SQLCAID                 PIC X(8)  VALUE 'SQLCA   '.
           05  SQLCABC                 PIC S9(9) VALUE 136.
           05  SQLCODE                 PIC S9(9) VALUE 0.
           05  SQLERRM.
               49  SQLERRML            PIC S9(4) VALUE 0.
               49  SQLERRMC            PIC X(70) VALUE SPACES.
           05  SQLERRP                 PIC X(8)  VALUE SPACES.
           05  SQLWARN0                PIC X(1)  VALUE SPACE.
           05  SQLSTATE                PIC X(5)  VALUE '00000'.
