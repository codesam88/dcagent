# Example cron.d-style entries for dcagent-managed action execution.
# This file is intended as an example of how to run the action interval
# directories from the system cron.d facility. The format requires a user
# field; these examples run as the "dcagent" system user.
#
# Install into /etc/dcagent/cron/cron.d/ or copy lines into /etc/cron.d/dcagent
# as appropriate for your system.

# Ensure action config is exported for the scripts
ACTION_CONF=/etc/dcagent/dcagent.conf

# Hourly: run all scripts in hourly.d
0 * * * * dcagent ACTION_CONF=/etc/dcagent/dcagent.conf /usr/bin/run-parts /etc/dcagent/cron/hourly.d >> /run/dcagent/dcagent.pipe 2>/dev/null

# Daily: run all scripts in daily.d at 06:00
0 6 * * * dcagent ACTION_CONF=/etc/dcagent/dcagent.conf /usr/bin/run-parts /etc/dcagent/cron/daily.d >> /run/dcagent/dcagent.pipe 2>/dev/null

# Weekly: Sundays at 06:00
0 6 * * 0 dcagent ACTION_CONF=/etc/dcagent/dcagent.conf /usr/bin/run-parts /etc/dcagent/cron/weekly.d >> /run/dcagent/dcagent.pipe 2>/dev/null

# Monthly: 1st day of month at 06:00
0 6 1 * * dcagent ACTION_CONF=/etc/dcagent/dcagent.conf /usr/bin/run-parts /etc/dcagent/cron/monthly.d >> /run/dcagent/dcagent.pipe 2>/dev/null

# Yearly: Jan 1st at 06:00
0 6 1 1 * dcagent ACTION_CONF=/etc/dcagent/dcagent.conf /usr/bin/run-parts /etc/dcagent/cron/yearly.d >> /run/dcagent/dcagent.pipe 2>/dev/null
