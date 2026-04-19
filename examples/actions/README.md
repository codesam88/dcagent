# actions/

This directory contains "action" scripts: executables that either emit alerts
(`alert <message>`) or update bot status (`status <key> <value>`). Actions are
intended to be small, self-contained checks that run periodically and write
single-line commands to stdout which dcagent consumes.

Design and conventions

- Single category: actions combine the former "alerts" and "status" examples.
- Placement: package-provided scripts can live in an AVAILABLE directory
  (e.g. `/etc/dcagent/action-available/`). Enable a script by symlinking it into
  the ENABLED directory (`/etc/dcagent/action-enabled/`). Enabled scripts may be
  invoked by dcagent (run-parts) or executed via cron/systemd timers.

- Configuration: scripts should source their action config before doing work.
  By default they read `/etc/dcagent/dcagent.conf` for common variables such as
  `DCAGENT_PIPE_PATH`. A script can override which file to source using the
  `DCAGENT_ACTION_CONF` environment variable.

  Example (shell):

    ACTION_CONF="${DCAGENT_ACTION_CONF:-/etc/dcagent/dcagent.conf}"
    # shellcheck source=/dev/null
    [[ -f "$ACTION_CONF" ]] && source "$ACTION_CONF"

  Example (python): the script may parse key=value lines from the file and set
  the variables into `os.environ` so code can read `os.environ['DCAGENT_PIPE_PATH']`.

- Output format:
  - Alerts: `alert <message>` (dcagent forwards to alert chats)
  - Status: `status <key> <value>` (dcagent updates the in-chat status map)

- Scheduling:
  - Short-interval checks (e.g. every 30s-5min) can continue to be run by
    dcagent using run-parts and the configured `DCAGENT_ACTION_DIR`/interval.
  - Infrequent checks (hourly/daily/weekly/monthly) should be scheduled using
    systemd timers or cron under a dedicated user (e.g. `dcagent`) to avoid
    keeping them in the fast polling loop.

- Dependencies: scripts should declare external dependencies at the top (e.g.
  `lm-sensors` for temperature checks or `distro-info` for release reporting)
  and print a helpful error to stderr if a dependency is missing.

- Safety and logging: actions should avoid long-running blocking operations in
  the run-parts context; prefer short-lived tasks. For heavier jobs, use a
  systemd timer and let the script run independently, emitting its output to
  the dcagent pipe.

Examples in this directory:
- `disk-space-alert` — alert when partitions exceed threshold
- `disk-status` — report the worst partition usage as status
- `temp-alert` / `temp-status` — temperature-based alert and status
- `security-updates-alert` — checks apt for pending security updates
- `distro-info` — reports current distro codename and lifecycle status

Installation notes

- The system-wide config template is `examples/systemd/dcagent.conf` and is
  intended to be installed to `/etc/dcagent/dcagent.conf` by the setup script.
- To enable action scripts for dcagent-run scheduling, create `/etc/dcagent/`
  subdirectories and symlink scripts into `/etc/dcagent/action-enabled/`.
- For cron/systemd timer scheduling, ensure scripts are executable and either
  source the action config or set `DCAGENT_PIPE_PATH` explicitly in the timer
  unit or crontab.
