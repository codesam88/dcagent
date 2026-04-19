# actions/

This directory contains "action" scripts: executables that either emit alerts
(`alert <message>`) or update bot status (`status <key> <value>`). Actions are
intended to be small, self-contained checks that run periodically and write
single-line commands to stdout which dcagent consumes.

Design and conventions

- Single category: actions combine the former "alerts" and "status" examples.
- Placement: install action scripts into `$DCAGENT_CONFIG_PATH/actions` (defaults to `/etc/dcagent/actions`).
  Enable a script for a given interval by creating a symlink from the action
  script into the desired cron interval directory under `$DCAGENT_CONFIG_PATH/cron` (e.g.
  `/etc/dcagent/cron/hourly.d/`). Action scripts are executed by cron or systemd
  timers — the agent no longer invokes run-parts itself.

- Configuration: scripts should start by setting `DCAGENT_CONFIG_PATH` to
  `/etc/dcagent` by default, then source `$DCAGENT_CONFIG_PATH/dcagent.conf`
  and the optional `$DCAGENT_CONFIG_PATH/conf.d/<script>.conf` for common
  variables such as `DCAGENT_PIPE_PATH`.

  Example (shell):

    DCAGENT_CONFIG_PATH="${DCAGENT_CONFIG_PATH:-/etc/dcagent}"
    DCAGENT_CONFIG_FILE="$DCAGENT_CONFIG_PATH/dcagent.conf"
    ACTION_CONFIG_FILE="$DCAGENT_CONFIG_PATH/conf.d/${0##*/}.conf"
    # shellcheck source=/dev/null
    [[ -f "$DCAGENT_CONFIG_FILE" ]] && source "$DCAGENT_CONFIG_FILE"
    # shellcheck source=/dev/null
    [[ -f "$ACTION_CONFIG_FILE" ]] && source "$ACTION_CONFIG_FILE"

  Example (python): the script may parse key=value lines from the file and set
  the variables into `os.environ` so code can read `os.environ['DCAGENT_PIPE_PATH']`.

- Output format:
  - Alerts: `alert <category> [message]` (dcagent tracks state per category and forwards to alert chats)
    - Category should use dashes as word separators (e.g., `disk-usage`, `security-updates`, `temperature-<chip>-<label>`)
    - If `<message>` is empty or omitted, dcagent marks the category as "recovered" (normal state)
    - If `<message>` changes, dcagent forwards the new message as `<category>: <message>`
    - If category is "" (empty string), the message is always sent without a prefix and bypasses deduplication
    - On first transition from error to recovery, dcagent sends: `<category>: recovered (was: <previous message>)`
  - Status: `status <key> <value>` (dcagent updates the in-chat status map)
    - Status keys are configurable via a script-specific `*_STATUS_KEY` env var.

- Scheduling:
  - All scheduling is managed externally (cron or systemd timers). The project
    provides a dcagent user crontab example (examples/systemd/dcagent.crontab) that
    runs run-parts on cron interval directories under "$DCAGENT_CONFIG_PATH/cron". To add
    custom execution times, edit the dcagent user's crontab with
    `crontab -e -u dcagent`.

- Installation and layout (setup.sh):
  - `DCAGENT_CONFIG_PATH` (default `/etc/dcagent`) is the root for configuration
    and action scripts. `dcagent.conf` lives at `$DCAGENT_CONFIG_PATH/dcagent.conf`,
    per-script configs live in `$DCAGENT_CONFIG_PATH/conf.d/`, action scripts live
    in `$DCAGENT_CONFIG_PATH/actions`, and the cron interval directories live in
    `$DCAGENT_CONFIG_PATH/cron`.
  - Cron-managed interval directories under `$DCAGENT_CONFIG_PATH/cron` include:
      - `hourly.d/`, `daily.d/`, `weekly.d/`, `monthly.d/`, `yearly.d/`
    The example crontab runs run-parts on these directories and redirects output
    to the dcagent pipe.
  - The setup script copies the example action scripts into
    `$DCAGENT_CONFIG_PATH/actions/` and creates the cron interval dirs. Enabling a
    script for an interval is done by creating a symlink from
    `$DCAGENT_CONFIG_PATH/actions/<script>` into the desired cron directory (`$DCAGENT_CONFIG_PATH/cron/hourly.d/`).

  Example (enable security updates hourly):

    ln -s "$DCAGENT_CONFIG_PATH/actions/security-updates-alert" "$DCAGENT_CONFIG_PATH/cron/hourly.d/"

  - setup.sh will also install the provided crontab into the `dcagent` user's
    crontab so the hourly/daily/... jobs run automatically.
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
  intended to be installed to `$DCAGENT_CONFIG_PATH/dcagent.conf` by the setup script.
- To enable action scripts for scheduled execution, create symlinks from the
  action script into the desired interval directory (e.g. `$DCAGENT_CONFIG_PATH/cron/hourly.d/`).
  The setup script already creates these interval directories and installs a
  default per-user crontab for the `dcagent` user.
- For cron/systemd timer scheduling, ensure scripts are executable and either
  source the action config or set `DCAGENT_PIPE_PATH` explicitly in the timer
  unit or crontab.
