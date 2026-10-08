from langchain_core.language_models.fake_chat_models import FakeListChatModel

from copilot.agent import IncidentCopilot


def test_offline_report_points_to_pool_runbook(settings, order_log):
    result = IncidentCopilot(settings).run(order_log, "Why are orders failing?")
    assert result["anomalies"]
    assert result["context"][0]["source"] in {"runbooks/db-connection-pool-exhausted.md", "incidents/inc-2024-orders-db-pool.md"}
    assert "### Likely root cause" in result["report"]
    assert "HikariCP" in result["report"] or "connection" in result["report"].lower()


def test_disk_full_retrieves_disk_runbook(settings, syslog):
    result = IncidentCopilot(settings).run(syslog)
    assert result["context"][0]["source"] == "runbooks/disk-full.md"


def test_llm_mode_uses_model_output(settings, order_log):
    llm = FakeListChatModel(responses=["### Summary\nPool exhausted"])
    result = IncidentCopilot(settings, llm=llm).run(order_log)
    assert result["report"] == "### Summary\nPool exhausted"


def test_add_incident_is_searchable(settings):
    copilot = IncidentCopilot(settings)
    copilot.kb.add_incident("Kafka consumer lag on billing topic", "## Root cause\nConsumer group rebalancing loop.")
    hits = copilot.kb.search("kafka consumer lag rebalancing", k=1)
    assert hits[0][0].metadata["title"] == "Kafka consumer lag on billing topic"
