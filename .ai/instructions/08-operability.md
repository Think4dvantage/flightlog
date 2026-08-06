# Operability Conventions

Operability is goal #1. Every service must be fully diagnosable from its logs alone — no source-diving, no attaching debuggers. An operator who has never read the code should be able to understand exactly what the service is doing, why, and whether it is healthy.

---

## The Rule

**Log everything that matters. When in doubt, log it.**

Logging is never scope creep. Any time you add or modify a function — even for an unrelated fix — check whether it has logging. If it does not, add it before moving on.

---

## Backend / Service Logging

Use Python's standard `logging` module throughout. Never use `print()` in production code.

### Logger Setup

Each module gets its own named logger:

```python
import logging
logger = logging.getLogger(__name__)
```

Configure the root logger at startup in `main.py` lifespan with level, format, and handler. Log format must include timestamp, level, logger name, and message:

```
2025-01-15 14:32:01,234 INFO     [package.api.main] Service starting — version 1.2.0
2025-01-15 14:32:01,891 INFO     [package.database.db] Migrations applied: 3 (skipped: 1)
```

### Startup Sequence

Log every step of the startup sequence at `INFO`. An operator reading cold logs must be able to reconstruct exactly what the service did during boot:

| Event | What to log |
|---|---|
| Service start | Name, version, environment (dev/prod) |
| Config loaded | Source file path, key values (never secrets) — log level, DB path, IGC dir, `allow_self_registration`, every `igc.parsing:` tuning value |
| JWT secret validated | Pass/fail only — **never the value**. Fail closed: refuse to start if empty, <32 chars, or a known placeholder |
| DB initialised | WAL mode status, column migrations applied vs skipped, seeders run vs skipped |
| IGC storage ready | Resolved `igc_dir` path, writable yes/no |
| HTTP server ready | Bind address and port |

The `igc.parsing:` values are worth logging individually: they are the knobs that will actually be
tuned against real tracks, and a support question about a wrong thermal count is answered by reading
them out of a boot log.

### Request Lifecycle

Every API request must produce at least one log line. Use FastAPI middleware or a dependency to log at `INFO`:

```
INFO  [package.api.middleware] POST /api/widgets → 201 (34ms) user=alice
INFO  [package.api.middleware] GET  /api/widgets → 200 (12ms) user=bob  count=42
```

Log at `WARNING` for 4xx, `ERROR` for 5xx. Include request ID if available.

### Long-running operations

IGC analysis, the Excel importer and any re-analysis sweep must be bracketed with start and end lines:

```python
logger.info("IGC analysis starting — flight=%s sha256=%s", flight_id, sha[:12])
# ... do work ...
logger.info(
    "IGC analysis done — flight=%s thermals=%d climb=%dm glides=%d in %.1fs",
    flight_id, thermal_count, total_climb_m, glide_count, elapsed,
)
```

Log at `WARNING` when a track parses but yields nothing usable (zero thermals, zero fixes, duration
under a minute) — that is almost always a truncated or corrupt file, and it is worth seeing before the
user reports it.

Log at `ERROR` with the full exception when parsing fails, and **re-raise**. Never swallow it: a bare
`except: pass` around IGC parsing turns a corrupt upload into a flight that silently has no track, which
is far harder to diagnose than a 422.

The importer logs a summary line per gate — rows read vs written, alias hits, values that bypassed the
master lists, the region-count reconciliation, formula cross-check mismatches. Those lines *are* the
dry-run report.

### Database Operations

Log at `DEBUG` for individual queries in hot paths (use `DEBUG` so they can be silenced in prod). Log at `INFO` for migrations, bulk writes, schema changes. Log at `ERROR` for constraint violations or connection failures with full context.

### Log Levels — When to Use Each

| Level | When |
|---|---|
| `DEBUG` | Per-row/per-iteration detail, query parameters, cache internals |
| `INFO` | All significant state changes: startup steps, job runs, API requests, config values |
| `WARNING` | Recoverable anomalies: empty results, retries, degraded mode, deprecated usage |
| `ERROR` | Failures that affect correctness: exceptions, failed writes, auth errors |
| `CRITICAL` | Service cannot continue: DB unreachable at startup, config missing required field |

---

## Health Endpoint

Every service must expose a `GET /health` endpoint. It must:

- Return `200 OK` with a JSON body when all critical subsystems are up
- Return `503 Service Unavailable` with a descriptive JSON body when any critical subsystem is down
- Be callable without authentication
- Include at minimum: service name, version, uptime, DB status, IGC storage status

```json
{
  "status": "ok",
  "service": "flightlog",
  "version": "0.1.0",
  "uptime_seconds": 3621,
  "checks": {
    "sqlite": "ok",
    "igc_storage": "ok"
  }
}
```

**Liveness vs readiness.** A missing *non-critical* dependency reports `"status": "degraded"` at HTTP
**200**, not 503 — so the UI stays reachable and can show the operator what is wrong. Reserve 503 for
the cases where the service genuinely cannot serve: the database is unreachable, or the schema is not
initialised. Unwritable IGC storage is degraded, not dead: the flight log still works, only uploads fail.

Log every health check that returns non-ok at `WARNING`.

---

## Config Transparency

Config must be explicit and auditable:

- All tunable behaviour (intervals, timeouts, thresholds, feature flags) must be in `config.yml`, not hardcoded.
- On startup, log the resolved value of every non-secret config key at `INFO`.
- Provide a `config.yml.example` with every key documented and a sensible default.
- If a required key is missing, log at `CRITICAL` with the key name and fail fast — never silently fall back to a magic default.

---

## Structured Error Context

When logging an exception, always include context that tells the operator what the service was trying to do:

```python
# Good
logger.error("Collector [weather] failed to parse response — url=%s status=%d body=%.200s",
             url, status, body, exc_info=True)

# Bad
logger.error("Parse error", exc_info=True)
```

Never catch-and-ignore exceptions. If an exception cannot be re-raised, log it at `ERROR` with full context.

---

## Frontend

See `03-frontend-conventions.md` — Browser Console Logging Policy. The same philosophy applies: log everything at the browser console so any engineer can diagnose frontend behaviour without source-diving. Use the bracketed prefix convention (`[App:<page>]`) on every `console.*` call.
