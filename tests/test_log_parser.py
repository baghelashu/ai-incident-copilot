from copilot.log_parser import cluster_errors, detect_anomalies, parse_logs, signature

SPRING = """2024-05-14 02:09:01.123 ERROR 4242 --- [exec-1] c.c.orders.web.OrderController : Failed to create order 123456
org.springframework.transaction.CannotCreateTransactionException: Could not open JPA EntityManager
\tat org.springframework.orm.jpa.JpaTransactionManager.doBegin(JpaTransactionManager.java:466)
2024-05-14 02:09:02.456 INFO 4242 --- [exec-2] c.c.orders.service.OrderService : Order 99 processed in 20ms
"""


def test_parses_spring_boot_lines_and_attaches_stacktrace():
    entries = parse_logs(SPRING)
    assert [e.level for e in entries] == ["ERROR", "INFO"]
    assert entries[0].logger == "c.c.orders.web.OrderController"
    assert len(entries[0].stacktrace) == 2
    assert entries[0].exception == "org.springframework.transaction.CannotCreateTransactionException"


def test_signature_masks_variable_parts():
    assert signature("Failed to create order 123456") == signature("Failed to create order 987")
    assert "<uuid>" in signature("id 123e4567-e89b-12d3-a456-426614174000 missing")


def test_clusters_group_same_error(order_log):
    clusters = cluster_errors(parse_logs(order_log))
    top = clusters[0]
    assert top.level == "ERROR"
    assert top.count > 50
    assert any("Connection is not available" in c.sample for c in clusters)


def test_detects_error_spike(order_log):
    anomalies = detect_anomalies(parse_logs(order_log))
    assert anomalies
    assert all(a.minute.startswith("2024-05-14 02:09") or a.minute.startswith("2024-05-14 02:10") for a in anomalies)


def test_syslog_error_hints(syslog):
    entries = parse_logs(syslog)
    errors = [e for e in entries if e.is_error]
    assert len(errors) >= 4
    assert all("No space left" in e.message for e in errors)
