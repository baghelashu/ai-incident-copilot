# Runbook: Disk full on Linux host

## Symptoms
- `No space left on device` in application or syslog
- Log rotation failures, database or application unable to write files

## Root cause
A filesystem reached 100% usage, usually from unrotated application logs, large temp files,
core dumps, or deleted files still held open by a running process.

## Resolution
1. `df -h` to find the full filesystem and `du -xh --max-depth=1 / | sort -h` to find the largest directories.
2. `lsof +L1` to find deleted-but-open files; restart the holding process to free the space.
3. Compress or remove old logs and fix logrotate configuration.
4. Add disk usage alerting at 80% and 90%.
