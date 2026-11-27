#!/usr/bin/env bash
# Install the already prepared upstream v1.3.1 build as described in its README.
# Run from a terminal: sudo bash scripts/install_spacemouse_system.sh
set -euo pipefail

TOOLKIT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SPACENAV_SOURCE="$TOOLKIT_ROOT/.runtime/spacenavd-src"
SPACENAV_COMMIT=22d9730719fe509780f19d25d40687adb16d0baf

if [[ "$EUID" -ne 0 ]]; then
    echo 'System installation requires sudo. Run this script in your terminal.' >&2
    exit 1
fi
if [[ ! -x "$SPACENAV_SOURCE/spacenavd" ]]; then
    echo 'Prepare the spacenavd v1.3.1 source build first; see docs/spacemouse-system-install.md.' >&2
    exit 1
fi
if [[ "$(git -c safe.directory="$SPACENAV_SOURCE" -C "$SPACENAV_SOURCE" rev-parse HEAD)" != "$SPACENAV_COMMIT" ]]; then
    echo 'Expected the verified upstream v1.3.1 commit.' >&2
    exit 1
fi
git -c safe.directory="$SPACENAV_SOURCE" -C "$SPACENAV_SOURCE" diff --exit-code HEAD --
"$SPACENAV_SOURCE/spacenavd" -V
if pgrep -x spacenavd >/dev/null && ! systemctl is-active --quiet spacenavd.service; then
    echo 'A foreground spacenavd is still running. Stop it before switching to systemd.' >&2
    exit 1
fi

# Already installed build-essential/git/libx11-dev/libxi-dev were used to build.
# Install the ROS driver's system library, replacing the temporary library path.
apt-get install -y libspnav-dev
if systemctl is-active --quiet spacenavd.service; then
    systemctl stop spacenavd.service
fi
make -C "$SPACENAV_SOURCE" install PREFIX=/usr/local
install -m 644 "$SPACENAV_SOURCE/contrib/systemd/spacenavd.service" /etc/systemd/system/spacenavd.service
systemctl daemon-reload
systemctl enable --now spacenavd.service

/usr/local/bin/spacenavd -V
systemctl is-enabled spacenavd.service
systemctl is-active spacenavd.service
systemctl --no-pager --full status spacenavd.service
