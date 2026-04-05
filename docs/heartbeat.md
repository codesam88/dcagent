# Heartbeat Protocol

## Purpose

Multiple dcagent instances can monitor each other's liveness by joining a shared
heartbeat group chat. Each node periodically broadcasts a heartbeat message.
If a node goes silent, a surviving node sends an alert to the alert channel.

## Setup

Each participating node joins the same heartbeat group:

```bash
# On the first node — create the group and print the invite
dcagent heartbeat

# On every other node — join using the invite
dcagent heartbeat INVITE
```

## Message format

```
heartbeat <addr> <seq>
```

- `addr` — the node's email address (unique; authenticated and verified by Delta Chat)
- `seq` — monotonically increasing integer per node; allows detecting restarts

Example:

```
heartbeat bot@example.com 42
```

## Timing

| Parameter            | Default | Description                                        |
|----------------------|---------|----------------------------------------------------|
| `HEARTBEAT_INTERVAL` | 60 s    | How often each node broadcasts a heartbeat message |
| `HEARTBEAT_TIMEOUT`  | 180 s   | Silence threshold (3 × interval) before offline    |

Both are configurable via environment variable.

## Detection and alerting

Every node maintains a `last_seen` map of `addr → timestamp` updated on each
received heartbeat. A periodic check (once per interval) determines:

- **Offline**: `now − last_seen[addr] > TIMEOUT` and not already flagged offline
- **Recovered**: `now − last_seen[addr] ≤ TIMEOUT` and previously flagged offline

### Master election

To avoid duplicate alerts, only one node — the **master** — sends alerts.
The master is implicitly elected as the node with the **lexicographically smallest
`addr`** among nodes seen within the last `2 × INTERVAL`.

This requires no coordination: if the master goes offline, the next node in
sorted order promotes itself on its next check cycle. A brief overlap (~one
interval) may produce a duplicate alert during transition — this is acceptable.

## Alert messages

Alerts are forwarded to the alert channel via the standard `_pipe_do_alert` path:

| Event     | Message                                      |
|-----------|----------------------------------------------|
| Offline   | `⚠️ Node offline: <addr> (last seen Xm ago)` |
| Recovered | `✅ Node recovered: <addr>`                  |

## State machine per remote node

```
         heartbeat received
UNKNOWN ──────────────────► ONLINE
                               │  silence > TIMEOUT (master alerts)
                               ▼
                            OFFLINE
                               │  heartbeat received (master alerts recovery)
                               ▼
                            ONLINE
```
