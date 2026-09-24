#!/bin/sh
# Keep the Brain Vault helper running in the background: starts it now and at every login.
#
#   bridge/install-service.sh            install (or reinstall) and start
#   bridge/install-service.sh status     is it running?
#   bridge/install-service.sh uninstall  stop it and remove it
#
# macOS uses a LaunchAgent, Linux a systemd user service. Logs go to bridge/server.log.
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
LABEL="${BRAIN_VAULT_SERVICE_LABEL:-com.brainvault.bridge}"
LOG="$HERE/server.log"
CMD="${1:-install}"

port() {
  p=$(sed -n 's/^[[:space:]]*BRAIN_VAULT_PORT[[:space:]]*=[[:space:]]*//p' "$HERE/.env" 2>/dev/null | tail -1)
  echo "${p:-${BRAIN_VAULT_PORT:-5128}}"
}

wait_healthy() {
  i=0
  while [ $i -lt 20 ]; do
    if curl -fs "http://localhost:$(port)/health" >/dev/null 2>&1; then
      echo "Helper is running on http://localhost:$(port)"
      return 0
    fi
    i=$((i + 1)); sleep 0.5
  done
  echo "The helper didn't answer on port $(port). Last lines of $LOG:" >&2
  tail -n 20 "$LOG" >&2 2>/dev/null || true
  return 1
}

python_bin() {
  py="${PYTHON:-$(command -v python3 || true)}"
  if [ -z "$py" ]; then echo "python3 not found. Install Python 3.9 or newer." >&2; exit 1; fi
  # Resolve shims (pyenv, asdf) to the real interpreter so the service doesn't depend on shell setup.
  "$py" -c 'import sys; assert sys.version_info >= (3, 9), "Python 3.9 or newer is needed"; print(sys.executable)'
}

case "$(uname -s)" in
Darwin)
  PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
  DOMAIN="gui/$(id -u)"
  case "$CMD" in
  install)
    PY=$(python_bin)
    mkdir -p "$HOME/Library/LaunchAgents"
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>$PY</string><string>$HERE/server.py</string></array>
  <key>WorkingDirectory</key><string>$HERE</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>$PATH</string>
    <key>PYTHONUNBUFFERED</key><string>1</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
EOF
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    launchctl bootstrap "$DOMAIN" "$PLIST"
    wait_healthy
    ;;
  status)
    if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then wait_healthy; else echo "Not installed."; exit 1; fi
    ;;
  uninstall)
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "Removed. The helper won't start at login any more."
    ;;
  *) echo "Usage: $0 [install|status|uninstall]" >&2; exit 2 ;;
  esac
  ;;
Linux)
  if ! command -v systemctl >/dev/null 2>&1; then
    echo "No systemd here. Start the helper yourself: nohup python3 $HERE/server.py >> $LOG 2>&1 &" >&2
    exit 1
  fi
  UNIT="$HOME/.config/systemd/user/$LABEL.service"
  case "$CMD" in
  install)
    PY=$(python_bin)
    mkdir -p "$(dirname "$UNIT")"
    cat > "$UNIT" <<EOF
[Unit]
Description=Brain Vault helper

[Service]
ExecStart=$PY $HERE/server.py
WorkingDirectory=$HERE
Environment=PATH=$PATH
Environment=PYTHONUNBUFFERED=1
Restart=always
StandardOutput=append:$LOG
StandardError=append:$LOG

[Install]
WantedBy=default.target
EOF
    systemctl --user daemon-reload
    systemctl --user enable "$LABEL.service" >/dev/null
    systemctl --user restart "$LABEL.service"
    wait_healthy
    ;;
  status)
    if systemctl --user is-active --quiet "$LABEL.service"; then wait_healthy; else echo "Not running."; exit 1; fi
    ;;
  uninstall)
    systemctl --user disable --now "$LABEL.service" 2>/dev/null || true
    rm -f "$UNIT"; systemctl --user daemon-reload
    echo "Removed. The helper won't start at login any more."
    ;;
  *) echo "Usage: $0 [install|status|uninstall]" >&2; exit 2 ;;
  esac
  ;;
*)
  echo "Not supported on this system. Start the helper yourself: python3 $HERE/server.py" >&2
  exit 1
  ;;
esac
