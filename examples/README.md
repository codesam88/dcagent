# examples/

Scripts and configuration for monitoring a Linux host and forwarding alerts
to dcagent. Three main areas are covered:

- **alerts/** — scripts that detect and report problem conditions
- **status/** — scripts that report current system state to the bot status message
- **systemd/** — service unit, config template, and install/uninstall helper for running dcagent as a systemd service

Alert scripts print `alert <message>` lines to stdout. When running as a
systemd service, dcagent invokes them automatically via `run-parts` from
`/etc/dcagent/alert-enabled/`. They can also be run standalone with redirection:

```bash
examples/alerts/disk-space-alert >> /run/dcagent/dcagent.pipe
```

Status scripts print a single `status <key> <value>` line that updates the bot's
status message. Run automatically from `/etc/dcagent/status-enabled/`, or
standalone:

```bash
examples/status/disk-status >> /run/dcagent/dcagent.pipe
examples/status/temp-status >> /run/dcagent/dcagent.pipe
```

To enable a script, symlink it into the appropriate `-enabled/` directory:

```bash
ln -s /etc/dcagent/alert-available/disk-space-alert /etc/dcagent/alert-enabled/
ln -s /etc/dcagent/status-available/disk-status      /etc/dcagent/status-enabled/
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

`disk-status` reports the usage of the most-full partition as a bot
status update (`status 30_disk home:72%`). Configure via environment variables or
`/etc/dcagent/disk-status.conf`:

| Variable         | Default | Description                          |
|------------------|---------|--------------------------------------|
| `MONITOR_MOUNTS` | (all)   | Space-separated list of mount points |

## Temperature sensors

`temp-alert` reads `sensors -j` (lm-sensors) and prints a line for each
sensor reading that exceeds its threshold. Configure via environment variables
or `/etc/dcagent/temp.conf`:

| Variable            | Default          | Description                                     |
|---------------------|------------------|-------------------------------------------------|
| `ALERT_THRESHOLD_C` | sensor's own max | Fixed °C threshold overriding per-sensor values |
| `IGNORE_CHIPS`      | (none)           | Space-separated chip name prefixes to skip      |

`temp-status` reports the highest reading across all (or selected) sensors as a bot
status update (`status 20_temp 65°C`). Configure via environment variables or
`/etc/dcagent/temp-status.conf`:

| Variable        | Default | Description                                        |
|-----------------|---------|----------------------------------------------------|
| `REPORT_CHIPS`  | (all)   | Space-separated chip name prefixes to include      |
| `IGNORE_CHIPS`  | (none)  | Space-separated chip name prefixes to skip         |

## Failed systemd services

`systemd-failed-alert` reports any unit in the `failed` state via
`systemctl --failed`. Optionally restrict to a specific set of services.
Configure via environment variables or `/etc/dcagent/systemd-failed.conf`:

| Variable         | Default | Description                                             |
|------------------|---------|---------------------------------------------------------|
| `WATCH_SERVICES` | (all)   | Space-separated service names to watch (e.g. `nginx sshd`) |

## Pending security updates (apt)

`security-updates-alert` checks for pending security updates using
`apt-get -s dist-upgrade` and reports them as a single alert plus a status
entry (`status 10_updates`). Uses the existing apt cache — run `apt-get update`
beforehand (e.g. in the same cron job) to keep results current.

## Distribution release status

`distro-info` reports the current release codename and its lifecycle status
as a bot status entry (`status 40_release noble [lts]`). Also sends an alert
if a newer stable or LTS release is available. Supports Debian and Ubuntu;
uses the `distro-info` package when installed, otherwise falls back to a
built-in release table.

---

## More ideas

Other conditions worth alerting on directly (not yet covered by examples):

- **Network connectivity** — host cannot reach a gateway, DNS resolver, or key remote host
- **SSL certificate expiry** — a cert is expiring within N days
- **Open port / service reachability** — a local or remote service stops accepting connections
- **UPS / power status** — mains power lost, battery low (e.g. via `upsc`)
- **RAID / mdadm degraded array** — a mirror is degraded or rebuilding
- **Docker / container health** — a container with a health-check is unhealthy
- **Login / auth anomalies** — repeated failed SSH logins, new root session (via PAM or auth log)
- **Swap pressure** — swap usage climbing
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
