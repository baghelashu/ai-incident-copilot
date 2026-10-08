"""Parse Spring Boot / syslog / generic logs, group errors by signature and flag anomalies."""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime

SPRING = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)\s+"
    r"(?P<level>TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL)\s+\d*\s*---\s+\[(?P<thread>[^\]]*)\]\s+"
    r"(?P<logger>\S+)\s*:\s*(?P<msg>.*)$"
)
GENERIC = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)\s*\[?(?P<level>TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL)\]?\s+"
    r"(?:(?P<logger>[\w.$]+)\s*[:\-]\s*)?(?P<msg>.*)$"
)
SYSLOG = re.compile(
    r"^(?P<ts>[A-Z][a-z]{2}\s+\d{1,2}\s\d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+(?P<logger>[\w\-./]+)(?:\[\d+\])?:\s*(?P<msg>.*)$"
)
EXCEPTION = re.compile(r"\b((?:[a-z_$][\w$]*\.)+[A-Z][\w$]*(?:Exception|Error))\b|\b([A-Z]\w*(?:Exception|Error))\b")
SYSLOG_ERROR_HINTS = re.compile(r"\b(error|fail(?:ed|ure)?|denied|oom|killed|panic|critical|no space)\b", re.I)

_MASKS = [
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "<uuid>"),
    (re.compile(r"\b0x[0-9a-f]+\b", re.I), "<hex>"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b"), "<ip>"),
    (re.compile(r"(['\"]).*?\1"), "<str>"),
    (re.compile(r"\b\d+(?:\.\d+)?(?:ms|s|MB|GB|KB)?\b"), "<n>"),
]


@dataclass
class LogEntry:
    timestamp: datetime | None
    level: str
    logger: str
    message: str
    line_no: int
    stacktrace: list[str] = field(default_factory=list)

    @property
    def is_error(self) -> bool:
        return self.level in {"ERROR", "FATAL"}

    @property
    def exception(self) -> str | None:
        for text in [self.message, *self.stacktrace[:3]]:
            match = EXCEPTION.search(text)
            if match:
                return match.group(1) or match.group(2)
        return None


@dataclass
class ErrorCluster:
    signature: str
    level: str
    logger: str
    exception: str | None
    count: int
    first_seen: str | None
    last_seen: str | None
    sample: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Anomaly:
    minute: str
    error_count: int
    baseline: float
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def _parse_ts(raw: str) -> datetime | None:
    raw = raw.replace(",", ".").replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%b %d %H:%M:%S"):
        try:
            ts = datetime.strptime(" ".join(raw.split()), fmt)
            return ts.replace(year=datetime.now().year) if ts.year == 1900 else ts
        except ValueError:
            continue
    return None


def parse_logs(text: str) -> list[LogEntry]:
    entries: list[LogEntry] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        match = SPRING.match(line) or GENERIC.match(line)
        if match:
            level = match.group("level").replace("WARNING", "WARN")
            entries.append(
                LogEntry(_parse_ts(match.group("ts")), level, match.group("logger") or "-", match.group("msg").strip(), line_no)
            )
            continue
        match = SYSLOG.match(line)
        if match:
            msg = match.group("msg").strip()
            level = "ERROR" if SYSLOG_ERROR_HINTS.search(msg) else "INFO"
            entries.append(LogEntry(_parse_ts(match.group("ts")), level, match.group("logger"), msg, line_no))
            continue
        if entries:
            entries[-1].stacktrace.append(line.strip())
    return entries


def signature(message: str) -> str:
    sig = message
    for pattern, token in _MASKS:
        sig = pattern.sub(token, sig)
    return " ".join(sig.split())[:200]


def cluster_errors(entries: list[LogEntry], levels: frozenset[str] = frozenset({"ERROR", "FATAL", "WARN"})) -> list[ErrorCluster]:
    groups: dict[tuple, list[LogEntry]] = defaultdict(list)
    for entry in entries:
        if entry.level in levels:
            groups[(entry.level, entry.logger, signature(entry.message))].append(entry)

    clusters = []
    for (level, logger, sig), items in groups.items():
        stamps = [e.timestamp for e in items if e.timestamp]
        clusters.append(
            ErrorCluster(
                signature=sig,
                level=level,
                logger=logger,
                exception=next((e.exception for e in items if e.exception), None),
                count=len(items),
                first_seen=min(stamps).isoformat(sep=" ") if stamps else None,
                last_seen=max(stamps).isoformat(sep=" ") if stamps else None,
                sample=items[0].message,
            )
        )
    severity = {"FATAL": 0, "ERROR": 1, "WARN": 2}
    return sorted(clusters, key=lambda c: (severity.get(c.level, 3), -c.count))


def detect_anomalies(entries: list[LogEntry], z_threshold: float = 3.0, min_errors: int = 5) -> list[Anomaly]:
    """Flag minutes whose error count is far above the per-minute baseline (z-score)."""
    per_minute = Counter(e.timestamp.strftime("%Y-%m-%d %H:%M") for e in entries if e.is_error and e.timestamp)
    if not per_minute:
        return []
    all_minutes = sorted({e.timestamp.strftime("%Y-%m-%d %H:%M") for e in entries if e.timestamp})
    counts = [per_minute.get(m, 0) for m in all_minutes]
    anomalies = []
    for minute, count in zip(all_minutes, counts):
        others = [c for m, c in zip(all_minutes, counts) if m != minute]
        if count < min_errors:
            continue
        baseline = statistics.mean(others) if others else 0.0
        spread = statistics.pstdev(others) if len(others) > 1 else 0.0
        z = (count - baseline) / spread if spread else float("inf")
        if z >= z_threshold:
            anomalies.append(Anomaly(minute, count, round(baseline, 2), f"{count} errors vs baseline {baseline:.1f}/min"))
    return anomalies


def summarize(entries: list[LogEntry]) -> dict:
    levels = Counter(e.level for e in entries)
    stamps = [e.timestamp for e in entries if e.timestamp]
    return {
        "total_lines": len(entries),
        "levels": dict(levels),
        "time_range": [min(stamps).isoformat(sep=" "), max(stamps).isoformat(sep=" ")] if stamps else None,
    }
