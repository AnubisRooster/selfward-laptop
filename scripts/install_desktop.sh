#!/bin/bash
# Installs Selfward's launcher entry and icons for the current user (no sudo):
#   scripts/install_desktop.sh            use the native window  (resources/selfward-ui-bin/selfward)
#   scripts/install_desktop.sh --browser  use the browser launcher (bin/start_selfward.sh)
set -e
APP="$(cd "$(dirname "$0")/.." && pwd)"
ID="com.mikefink.selfward"
ICONS="$HOME/.local/share/icons/hicolor"
APPS="$HOME/.local/share/applications"

if [ "$1" = "--browser" ]; then EXEC="$APP/bin/start_selfward.sh"; else EXEC="$APP/resources/selfward-ui-bin/selfward"; fi
[ -x "$EXEC" ] || { echo "Missing $EXEC (build it with scripts/build_native.sh)" >&2; exit 1; }

mkdir -p "$APPS"
for pair in "32:32x32.png" "64:64x64.png" "128:128x128.png" "256:128x128@2x.png" "512:icon.png"; do
  size="${pair%%:*}"; file="${pair#*:}"
  mkdir -p "$ICONS/${size}x${size}/apps"
  cp "$APP/frontend/src-tauri/icons/$file" "$ICONS/${size}x${size}/apps/$ID.png"
done

cat > "$APPS/$ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Selfward
GenericName=Private reflection companion
Comment=A private, on-device space for reflection with a guide you choose
Exec=$EXEC
Icon=$ID
Terminal=false
Categories=Utility;
Keywords=AI;Journal;Reflection;Wellbeing;Therapy;
StartupNotify=true
# The window announces the app id "selfward", not the bundle identifier; GNOME matches the dock icon on it.
StartupWMClass=selfward
EOF
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -f -t "$ICONS" 2>/dev/null || true
echo "Installed $APPS/$ID.desktop (launches $EXEC)"
