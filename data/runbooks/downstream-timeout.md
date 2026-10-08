# Runbook: Downstream service timeout / 503

## Symptoms
- `java.net.SocketTimeoutException: Read timed out` or `feign.RetryableException`
- `HTTP 503 Service Unavailable` from a dependent REST API, circuit breaker OPEN

## Root cause
A dependent service is slow or down, or network/DNS issues between services. Retries without
backoff can amplify load and cascade the failure.

## Resolution
1. Check the health and latency dashboards of the downstream service.
2. Confirm circuit breaker state and that fallbacks are returning sensible responses.
3. Contact the owning team; fail over or roll back the downstream deployment if it was recent.
4. Tune timeouts and retry backoff; avoid retry storms.
