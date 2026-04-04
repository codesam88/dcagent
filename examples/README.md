# examples/

Scripts and configuration for monitoring a Linux host and forwarding alerts
to dcagent. Scripts print to stdout — pipe them to the dcagent pipe:

```bash
disk-space-alert >> /run/dcagent.pipe
```

---

## Disk space

`disk-space-alert` checks partition usage and prints a line for each mount
point exceeding a threshold. Configure via environment variables or
`/etc/dcagent/disk-space.conf`:

| Variable          | Default | Description                          |
|-------------------|---------|--------------------------------------|
| `ALERT_THRESHOLD` | `90`    | Usage % that triggers an alert       |
| `MONITOR_MOUNTS`  | (all)   | Space-separated list of mount points |

## Temperature sensors

`temp-alert` reads `sensors -j` (lm-sensors) and prints a line for each
sensor reading that exceeds its threshold. Configure via environment variables
or `/etc/dcagent/temp.conf`:

| Variable            | Default          | Description                                     |
|---------------------|------------------|-------------------------------------------------|
| `ALERT_THRESHOLD_C` | sensor's own max | Fixed °C threshold overriding per-sensor values |
| `IGNORE_CHIPS`      | (none)           | Space-separated chip name prefixes to skip      |

## Failed systemd services

`systemd-failed-alert` reports any unit in the `failed` state via
`systemctl --failed`. Optionally restrict to a specific set of services.
Configure via environment variables or `/etc/dcagent/systemd-failed.conf`:

| Variable          | Default | Description                                             |
|-------------------|---------|---------------------------------------------------------|
| `WATCH_SERVICES`  | (all)   | Space-separated service names to watch (e.g. `nginx sshd`) |

## CPU load, memory, and more

Users can leverage [glances](https://nicolargo.github.io/glances/) in server
mode (`glances -s` or `glances -w`) to monitor various aspects of the host —
CPU load, memory pressure, swap, disk I/O, network, and more — with default
thresholds already configured out of the box.

`glances-alert-poller` polls the glances REST API and forwards any active
WARNING or CRITICAL events to stdout. Events are deduplicated so each alert
is only reported once. Pipe to dcagent alongside glances in server mode:

```bash
glances -w &
glances-alert-poller >> /run/dcagent.pipe
```

Note: `glances -s` runs the XML-RPC server (port 61209), which does **not**
expose the REST API. Use `glances -w` (web server, port 61208) instead.

Configure via environment variables or `/etc/dcagent/glances-poller.conf`:

| Variable         | Default                  | Description                      |
|------------------|--------------------------|----------------------------------|
| `GLANCES_URL`    | `http://localhost:61208` | Base URL of the glances REST API |
| `POLL_INTERVAL`  | `30`                     | Seconds between polls            |

`glances.conf` and `glances-dcagent-alert` are also provided if you need to
customise thresholds or trigger actions beyond what the poller covers.

---

## More ideas

Other conditions worth alerting on directly (not yet covered by examples):

- **Network connectivity** — host cannot reach a gateway, DNS resolver, or key remote host
- **SSL certificate expiry** — a cert is expiring within N days
- **Open port / service reachability** — a local or remote service stops accepting connections
- **UPS / power status** — mains power lost, battery low (e.g. via `upsc`)
- **RAID / mdadm degraded array** — a mirror is degraded or rebuilding
- **Docker / container health** — a container with a health-check is unhealthy
- **Pending security updates** — `apt` or `dnf` has unattended security updates queued
- **Login / auth anomalies** — repeated failed SSH logins, new root session (via PAM or auth log)
- **Swap pressure** — swap usage climbing (complements the glances memory check)
- **IPv6 / WireGuard tunnel down** — tunnel interface missing or no traffic

---

## What not to monitor here

The following are better covered by logging to syslog (picked up by logcheck),
or by reporting built into the respective tool:

- **Kernel / filesystem errors** — logcheck, systemd-journald
- **SMART disk health** — `smartd` via syslog or email
- **Btrfs scrub errors** — reported in syslog
- **Backup job failures** — borg, restic, rsync exit codes or their own logging
- **Cron / timer failures** — `MAILTO` in crontab, systemd `OnFailure=` units
