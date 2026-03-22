# strange-param-java

Minimal Java example that reproduces the idea of
`TripleNestedStructParameterMemberTypeMismatch` from YDB PR #35635:

- query declares `$items` with nested member `p:Int32`
- client sends `$items` where nested member `p:Uint32`
- YDB should return `BAD_REQUEST` with a readable first-incompatibility message

## Build

```bash
mvn -q -DskipTests package
```

## Run

```bash
mvn -q exec:java -Dexec.args="example1.xml"
```

Expected result: query failure with a parameter type mismatch, similar to:
`first incompatibility at root.z.c.p: expected Int32, actual Uint32`.
