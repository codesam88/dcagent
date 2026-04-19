#!/usr/bin/env bash
# setup.sh — install or uninstall dcagent as a systemd service
#
# Usage: sudo ./setup.sh [--pyz PATH] [--launch] [--uninstall]
#
#   --pyz PATH   use a local .pyz binary instead of downloading from Codeberg
#   --launch     enable and start dcagent.service after installation
#   --uninstall  stop and remove a previously installed dcagent

set -euo pipefail

CODEBERG_API="https://codeberg.org/api/v1/repos/codesam/dcagent/releases?limit=1"
SCRIPTDIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_BIN=/usr/local/bin/dcagent
RUN_ACTIONS_BIN=/usr/local/bin/dcagent-run-actions
SERVICE_DEST=/etc/systemd/system/dcagent.service
CONF_DEST=/etc/dcagent/dcagent.conf
DCAGENT_USER=dcagent
DCAGENT_HOME=/var/lib/dcagent
DCAGENT_CONF_DIR=/etc/dcagent
ARCH=$(uname -m)
DEFAULT_NAME="$(hostname -s) bot"
LAUNCH=false
UNINSTALL=false
PYZ=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --launch)    LAUNCH=true ;;
        --uninstall) UNINSTALL=true ;;
        --pyz)       shift; PYZ="${1:-}"; [[ -n "$PYZ" ]] || { echo "error: --pyz requires a path" >&2; exit 1; } ;;
        *)           echo "error: unknown argument: $1" >&2; exit 1 ;;
    esac
    shift
done

[[ $EUID -eq 0 ]] || { echo "error: run as root (sudo $0)" >&2; exit 1; }

# Print and execute a command
run() {
    printf '%q ' "$@"; echo
    "$@"
    echo
}

# Uninstall
if $UNINSTALL; then
    echo "dcagent uninstall"
    echo
    echo "Installed files and accounts:"
    [[ -f "$INSTALL_BIN" ]]  && echo "  $INSTALL_BIN"
    [[ -f "$RUN_ACTIONS_BIN" ]]   && echo "  $RUN_ACTIONS_BIN"
    [[ -f "$SERVICE_DEST" ]] && echo "  $SERVICE_DEST"
    [[ -d "$DCAGENT_CONF_DIR" ]] && echo "  $DCAGENT_CONF_DIR  (not removed — may contain your scripts)"
    echo
    id "$DCAGENT_USER" &>/dev/null && echo "Will also remove user '$DCAGENT_USER' and home $DCAGENT_HOME"
    echo

    read -r -p "Continue? [y/N] " answer
    [[ "$answer" =~ ^[yY]$ ]] || { echo "Aborted."; exit 0; }
    echo

    if systemctl is-active dcagent &>/dev/null 2>&1 || systemctl is-enabled dcagent &>/dev/null 2>&1; then
        run systemctl disable --now dcagent
    fi
    [[ -f "$SERVICE_DEST" ]] && run rm "$SERVICE_DEST"
    run systemctl daemon-reload
    [[ -f "$INSTALL_BIN" ]]  && run rm "$INSTALL_BIN"
    [[ -f "$RUN_ACTIONS_BIN" ]]   && run rm "$RUN_ACTIONS_BIN"
    id "$DCAGENT_USER" &>/dev/null && run userdel -r "$DCAGENT_USER"
    exit 0
fi

# Install
command -v python3 &>/dev/null || { echo "error: python3 is required" >&2; exit 1; }
[[ -n "$PYZ" ]] || command -v curl &>/dev/null || { echo "error: curl is required" >&2; exit 1; }

echo "dcagent install"
echo
echo "Files that will be created or modified:"
echo "  $INSTALL_BIN"
echo "  $RUN_ACTIONS_BIN"
echo "  $SERVICE_DEST"
if [[ -f "$CONF_DEST" ]]; then
    echo "  $CONF_DEST  (exists, will not be overwritten)"
else
    echo "  $CONF_DEST"
fi
echo
echo "Actions:"
N=1
if [[ -n "$PYZ" ]]; then
    echo "  $N. install $PYZ to $INSTALL_BIN"; (( N++ ))
else
    echo "  $N. download and install latest dcagent-${ARCH}.pyz to $INSTALL_BIN"; (( N++ ))
fi
echo "  $N. install systemd unit to $SERVICE_DEST"; (( N++ ))
echo "  $N. install helper to run all actions to $RUN_ACTIONS_BIN"; (( N++ ))
echo "  $N. install config file to $CONF_DEST (unless exists)"; (( N++ ))
echo "  $N. create per-script config dir $DCAGENT_CONF_DIR/conf.d"; (( N++ ))
echo "  $N. create system user '$DCAGENT_USER' (unless exists)"; (( N++ ))
echo "  $N. create chatmail account on nine.testrun.org as '$DEFAULT_NAME' (unless already configured)"; (( N++ ))
echo "  $N. print alert, heartbeat, and admin invite links"; (( N++ ))
$LAUNCH && { echo "  $N. enable and start dcagent.service"; (( N++ )); } || true
echo

read -r -p "Continue? [y/N] " answer
[[ "$answer" =~ ^[yY]$ ]] || { echo "Aborted."; exit 0; }
echo

# Download binary if not supplied
if [[ -z "$PYZ" ]]; then
    RELEASE_JSON=$(curl -fsSL "$CODEBERG_API")
    TAG=$(echo "$RELEASE_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['tag_name'])")
    TMPFILE=$(mktemp /tmp/dcagent-XXXXXX.pyz)
    trap "rm -f '$TMPFILE'" EXIT
    run curl -fSL --progress-bar -o "$TMPFILE" \
        "https://codeberg.org/codesam/dcagent/releases/download/$TAG/dcagent-${ARCH}.pyz"
    PYZ="$TMPFILE"
fi

run install -m 755 "$PYZ" "$INSTALL_BIN"
run install -m 755 "$SCRIPTDIR/../../scripts/dcagent-run-actions" "$RUN_ACTIONS_BIN"

if ! id "$DCAGENT_USER" &>/dev/null; then
    run useradd --system --user-group --home-dir "$DCAGENT_HOME" --create-home \
        --shell /usr/sbin/nologin "$DCAGENT_USER"
fi

run install -m 644 "$SCRIPTDIR/dcagent.service" "$SERVICE_DEST"
if [[ ! -f "$CONF_DEST" ]]; then
    run install -m 755 -d "$DCAGENT_CONF_DIR"
    run install -m 644 "$SCRIPTDIR/dcagent.conf" "$CONF_DEST"
fi
# Create config/action directories
run install -m 755 -d "$DCAGENT_CONF_DIR"
# Actions layout: scripts and cron interval dirs
run install -m 755 -d \
    "$DCAGENT_CONF_DIR/conf.d" \
    "$DCAGENT_CONF_DIR/actions" \
    "$DCAGENT_CONF_DIR/cron/hourly.d" \
    "$DCAGENT_CONF_DIR/cron/daily.d" \
    "$DCAGENT_CONF_DIR/cron/weekly.d" \
    "$DCAGENT_CONF_DIR/cron/monthly.d" \
    "$DCAGENT_CONF_DIR/cron/yearly.d"

# Copy example action scripts into actions/ (do not overwrite existing files)
if [[ -d "$SCRIPTDIR/../examples/actions" ]]; then
    for f in "$SCRIPTDIR/../examples/actions"/*; do
        fname=$(basename "$f")
        dest="$DCAGENT_CONF_DIR/actions/$fname"
        if [[ ! -e "$dest" ]]; then
            run install -m 755 "$f" "$dest"
        fi
    done
fi



# Install example crontab into dcagent user's crontab (unless one already exists)
if [[ -f "$SCRIPTDIR/dcagent.crontab" ]]; then
    if ! crontab -u "$DCAGENT_USER" -l &>/dev/null; then
        run crontab -u "$DCAGENT_USER" "$SCRIPTDIR/dcagent.crontab"
    else
        echo "Skipping crontab installation for $DCAGENT_USER — crontab already exists"
    fi
fi

# If /etc/cron.allow exists, ensure the dcagent user is permitted to run per-user cron jobs.
# Some systems restrict which users can run crontab -u via /etc/cron.allow; warn the
# administrator if the file exists and does not include the dcagent user.
if [[ -f /etc/cron.allow ]]; then
    if ! grep -qxF "$DCAGENT_USER" /etc/cron.allow; then
        echo "WARNING: /etc/cron.allow exists. Add '$DCAGENT_USER' to /etc/cron.allow to allow per-user cron jobs."
        echo "You can run:  echo '$DCAGENT_USER' >> /etc/cron.allow"
        echo
    fi
fi

run systemctl daemon-reload

# Skip init if an account is already configured (e.g. re-install over existing setup)
DCAGENT_ACCOUNTS="$DCAGENT_HOME/.config/dcagent/accounts"
if sudo -u "$DCAGENT_USER" test -d "$DCAGENT_ACCOUNTS" && \
   [ -n "$(sudo -u "$DCAGENT_USER" ls "$DCAGENT_ACCOUNTS" 2>/dev/null)" ]; then
    echo "Existing account found in $DCAGENT_ACCOUNTS, skipping init."
    echo
else
    run sudo -u "$DCAGENT_USER" "$INSTALL_BIN" init DCACCOUNT:https://nine.testrun.org/new
    run sudo -u "$DCAGENT_USER" "$INSTALL_BIN" config displayname "$DEFAULT_NAME"
fi
run sudo -u "$DCAGENT_USER" "$INSTALL_BIN" alert
run sudo -u "$DCAGENT_USER" "$INSTALL_BIN" heartbeat
run sudo -u "$DCAGENT_USER" "$INSTALL_BIN" admin

if $LAUNCH; then
    run systemctl enable --now dcagent
else
    echo "To start the service:"
    echo "  systemctl enable --now dcagent"
fi
