      *================================================================*
      * DFHAID.CPY: Standard CICS Attention Identifier Mock            *
      * Used for 3270 terminal key mappings (Enter, Clear, PF keys).   *
      *================================================================*
       01  DFHAID.
           05  DFHENTER                PIC X(1) VALUE "'".
           05  DFHCLEAR                PIC X(1) VALUE "_".
           05  DFHPF1                  PIC X(1) VALUE "1".
           05  DFHPF3                  PIC X(1) VALUE "3".
           05  DFHPF12                 PIC X(1) VALUE "<".
