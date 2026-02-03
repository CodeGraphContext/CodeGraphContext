# C sample project

A tiny, dependency-free C project (~10 files) used to exercise CodeGraphContext’s indexer.  
It mirrors the other language samples by showcasing common C patterns: headers/includes, typedefs, enums,
structs, extern vs static variables, inline functions, function pointer typedefs, macros/conditional compilation, and a Makefile.

## Layout

tests/sample_project_c/

├─ README.md

├─ Makefile

├─ include/

│ ├─ config.h

│ ├─ platform.h

│ ├─ util.h

│ ├─ module.h

│ └─ math/vec.h

└─ src/

├─ main.c

├─ util.c

├─ module.c

└─ math/vec.c


## Quick run
From this folder:
```bash
make
./cgc_sample
```

## Expected Output

On macOS/Linux (POSIX):
```bash
CgcSample 0.1.0 (posix) r=XX sum=(5,7,9)
```

On Windows:
```bash
CgcSample 0.1.0 (win) r=XX sum=(5,7,9)
```

