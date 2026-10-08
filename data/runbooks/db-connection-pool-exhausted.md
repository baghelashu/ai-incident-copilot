# Runbook: Database connection pool exhausted (HikariCP)

## Symptoms
- `SQLTransientConnectionException: HikariPool-1 - Connection is not available, request timed out after 30000ms`
- `CannotCreateTransactionException` / `JDBCConnectionException` in Spring Boot services
- API latency spikes followed by HTTP 500/503 errors

## Root cause
All connections in the HikariCP pool are busy. Usual causes: long-running or locked SQL queries,
connection leaks (connections not closed in a finally/try-with-resources block), a pool size too
small for traffic, or the database itself being slow or at its max connection limit.

## Resolution
1. Check active vs idle connections (`/actuator/metrics/hikaricp.connections.active`).
2. Find long-running / blocked queries on the database and kill the blocker if safe.
3. Enable `spring.datasource.hikari.leak-detection-threshold=20000` to locate leaks.
4. Short term: restart the affected pods to release connections; scale out if traffic driven.
5. Long term: fix leaking code paths, add query timeouts, tune `maximum-pool-size`.
