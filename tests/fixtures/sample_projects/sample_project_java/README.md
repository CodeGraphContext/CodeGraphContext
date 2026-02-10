# Java sample project (for `tests/`)

A tiny, dependency-free Java project (~10 files) used to exercise CodeGraphContext’s indexer.  
It mirrors the Python sample by showcasing relationships: packages, interface→impl, abstract class,
enum, generics, exceptions, custom annotation, inner class, lambdas/streams, basic I/O, and a tiny thread.

## Layout
tests/sample_project_java/

├─ README.md

└─ src/com/example/app/

├─ Main.java

├─ model/Role.java

├─ model/User.java

├─ service/GreetingService.java

├─ service/AbstractGreeter.java

├─ service/impl/GreetingServiceImpl.java

├─ util/CollectionUtils.java

├─ util/IOHelper.java

├─ annotations/Logged.java

└─ misc/Outer.java


## Quick run (no build tool)
From this folder:
```bash
# compile
find src -name "*.java" > sources.txt
javac -d out @sources.txt

# run
java -cp out com.example.app.Main

```


## Expected Output
Hello, Priya (ADMIN)
sumSquares=55
firstLine=# java sample project
outer+inner
