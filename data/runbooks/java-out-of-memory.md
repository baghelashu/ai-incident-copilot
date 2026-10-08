# Runbook: Java OutOfMemoryError

## Symptoms
- `java.lang.OutOfMemoryError: Java heap space` or `GC overhead limit exceeded`
- Long GC pauses, container restarts with exit code 137 (OOMKilled)

## Root cause
The JVM heap is too small for the workload or objects are being retained (memory leak), e.g.
unbounded caches, large result sets loaded into memory, or static collections that only grow.

## Resolution
1. Capture a heap dump (`-XX:+HeapDumpOnOutOfMemoryError`) and analyse it with Eclipse MAT.
2. Check for large queries without pagination and unbounded caches.
3. Short term: restart the service and increase `-Xmx` / container memory limit.
4. Long term: fix the retention path, add pagination/streaming, set cache eviction limits.
