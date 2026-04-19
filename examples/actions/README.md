# Example dcagent actions

This directory contains "action" scripts: self-contained programs that issue
alert or status messages. Actions are intended to be small, self-contained
checks that run periodically and write single-line commands to stdout. The
caller (scheduler) redirects these outputs to a unix pipe exposed by dcagent.

## Design and conventions

- Scheduling: Each action can output one or more alert messages (`alert
  <category> <message>`) and/or set a field in the bot's status line (`status
  <key> <value>`). An external scheduler such as Cron can be used to launch the
  scripts and forward the output to the dcagent exposed unix pipe. For detailed
  syntax see the bot's pipe command documentation.

- Configuration: scripts should use `DCAGENT_CONFIG_PATH` (default:
  `/etc/dcagent`) and source its dcagent.conf for global settings, then source an
  optional `$DCAGENT_CONFIG_PATH/conf.d/<script>.conf`
  for script-specific variables such as alert filters and thresholds.

- Placement: install action scripts into `$DCAGENT_CONFIG_PATH/actions` Enable
  a script for a given interval by creating a symlink from the action script
  into the desired cron interval directory under `$DCAGENT_CONFIG_PATH/cron` (e.g.
  `/etc/dcagent/cron/hourly.d/`).

- Dependencies: scripts should declare external dependencies at the top (e.g.
  `lm-sensors` for temperature checks or `distro-info` for release reporting)
  and print a helpful error to stderr if a dependency is missing.

- Safety and logging: Avoid long-running blocking operations in the run-parts
  context as they may block other actions. Setup a separate cron schedule or
  systemd.timer event instead. Make sure you receive errors from failed cron
  executions, e.g. using logcheck. In principle, I guess we should also be using
  a proper socket or a mutual file lock on the unix pipe to avoid cross-talk.

- Message Load: Every status update and every new alert message creates
  a broadcast message to all enabled chats and participants. Since actions are
  run in fixed intervals, the dcagent bot implements a simple de-duplication
  logic. However, it may be prudent to not report frequently changing data such as
  the CPU temperature as a `status` field. This may also be a good reason to
  separate less frequently status update actions from more frequently scheduled
  alert (threshold-checking) actions.



## Example Actions

---

### Disk space

`disk-space-alert` checks partition usage and prints a line for each mount
point exceeding a threshold. Configure via environment variables or
`$DCAGENT_CONFIG_PATH/conf.d/disk-space-alert.conf`:

| Variable          | Default | Description                          |
|-------------------|---------|--------------------------------------|
| `ALERT_THRESHOLD` | `90`    | Usage % that triggers an alert       |
| `MONITOR_MOUNTS`  | (all)   | Space-separated list of mount points |

`disk-status` reports the usage of the most-full partition as a bot
status update (`status 30_disk home:72%`). Configure via environment variables or
`$DCAGENT_CONFIG_PATH/conf.d/disk-status.conf`. Action scripts source
`$DCAGENT_CONFIG_PATH/dcagent.conf` and then the per-script config so they inherit the configured
`DCAGENT_PIPE_PATH` by default. Override the emitted status key with
`DISK_STATUS_KEY`:

| Variable         | Default | Description                          |
|------------------|---------|--------------------------------------|
| `MONITOR_MOUNTS` | (all)   | Space-separated list of mount points |

### Temperature sensors

`temp-alert` reads `sensors -j` (lm-sensors) and prints a line for each
sensor reading that exceeds its threshold. Configure via environment variables
or `$DCAGENT_CONFIG_PATH/conf.d/temp-alert.conf`:

| Variable            | Default          | Description                                     |
|---------------------|------------------|-------------------------------------------------|
| `ALERT_THRESHOLD_C` | sensor's own max | Fixed °C threshold overriding per-sensor values |
| `IGNORE_CHIPS`      | (none)           | Space-separated chip name prefixes to skip      |

`temp-status` reports the highest reading across all (or selected) sensors as a bot
status update (`status 20_temp 65°C`). Configure via environment variables or
`$DCAGENT_CONFIG_PATH/conf.d/temp-status.conf`. Override the emitted status key with
`TEMP_STATUS_KEY`:

| Variable        | Default | Description                                        |
|-----------------|---------|----------------------------------------------------|
| `REPORT_CHIPS`  | (all)   | Space-separated chip name prefixes to include      |
| `IGNORE_CHIPS`  | (none)  | Space-separated chip name prefixes to skip         |

### Failed systemd services

`systemd-failed-alert` reports any unit in the `failed` state via
`systemctl --failed`. Optionally restrict to a specific set of services.
Configure via environment variables or `$DCAGENT_CONFIG_PATH/conf.d/systemd-failed-alert.conf`:

| Variable         | Default | Description                                             |
|------------------|---------|---------------------------------------------------------|
| `WATCH_SERVICES` | (all)   | Space-separated service names to watch (e.g. `nginx sshd`) |

### Pending security updates (apt)

`security-updates-alert` checks for pending security updates using
`apt-get -s dist-upgrade` and reports them as a single alert plus a status
entry (`status 10_updates`). Configure via environment variables or
`$DCAGENT_CONFIG_PATH/conf.d/security-updates-alert.conf`. Uses the existing apt cache —
run `apt-get update` beforehand (e.g. in the same cron job) to keep results current.
Override the emitted status key with `SECURITY_UPDATES_ALERT_STATUS_KEY`.

### Distribution release info

`distro-info` reports the current release codename and its lifecycle status
as a bot status entry (`status 01_release Ubuntu noble [lts]`). Also sends an alert
if a newer stable or LTS release is available. Supports Debian and Ubuntu;
uses the `distro-info` package when installed and will surface a helpful
error status if the tool is missing. Configure via environment variables or
`$DCAGENT_CONFIG_PATH/conf.d/distro-info.conf`. Override the emitted status key with
`DISTRO_INFO_STATUS_KEY`.


## Other Ideas

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

The following are better covered by logging to syslog (picked up by logcheck),
or by reporting built into the respective tool:

- **Kernel / filesystem errors** — logcheck, systemd-journald
- **SMART disk health** — `smartd` via syslog or email
- **Btrfs scrub errors** — reported in syslog
- **Backup job failures** — borg, restic, rsync exit codes or their own logging
- **Cron / timer failures** — `MAILTO` in crontab, systemd `OnFailure=` units
