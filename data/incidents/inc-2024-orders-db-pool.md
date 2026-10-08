# Past incident: Order service outage due to connection leak

## Summary
Order service returned HTTP 500 for 40 minutes during the evening peak.

## Root cause
A new reporting endpoint opened JDBC connections without closing them on an exception path,
leaking connections until HikariCP pool was exhausted (`Connection is not available, request timed out`).

## Resolution
Pods were restarted to release connections; the endpoint was fixed to use try-with-resources and
leak detection was enabled. Added an alert on `hikaricp.connections.pending > 0` for 5 minutes.
