#!/usr/bin/env bash
set -euo pipefail

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

usage() {
    printf 'Usage: %s {install|uninstall}\n' "$0" >&2
    exit 2
}

[[ $# -eq 1 ]] || usage
[[ "$1" == "install" || "$1" == "uninstall" ]] || usage

command -v uv >/dev/null 2>&1 || die "uv is required. Install it from https://docs.astral.sh/uv/."

readonly APP_ID="apkit4d"
readonly PROJECT_DIR="$(pwd -P)"
readonly ICON_SOURCE="${PROJECT_DIR}/images/ApKit4D.png"

data_home=${XDG_DATA_HOME:-$HOME/.local/share}
applications_dir="${data_home}/applications"
icon_dir="${data_home}/icons/hicolor/512x512/apps"
desktop_file="${applications_dir}/${APP_ID}.desktop"
icon_file="${icon_dir}/${APP_ID}.png"

update_desktop() {
    update-desktop-database "$applications_dir" || true # look only in the destination of $desktop_file
    xdg-icon-resource forceupdate || true
}

if [[ "$1" == "uninstall" ]]; then
    uv tool uninstall "$APP_ID"
    rm -f "$desktop_file" "$icon_file"
    update_desktop
    echo "Uninstalled ApKit4D for $USER"
    exit 0
fi

[[ -f "$ICON_SOURCE" ]] || die "Application icon not found: ${ICON_SOURCE}"

# equivalent to running `uv tool install .` in the repo
uv tool install --force "$PROJECT_DIR"
launcher="$(uv tool dir --bin)/${APP_ID}"
[[ -x "$launcher" ]] || die "Installed ApKit4D launcher is not executable: ${launcher}"

mkdir -p "$applications_dir" "$icon_dir"
install -m 0644 "$ICON_SOURCE" "$icon_file"

cat >"$desktop_file" <<EOF
[Desktop Entry]
Type=Application
Name=ApKit4D
Comment=Visualize and analyze 4D microscopy recordings
Exec="${launcher}" gui
Icon=${APP_ID}
Terminal=false
Categories=Science;Education;
EOF
chmod 0644 "$desktop_file"
update_desktop

echo "Installed ApKit4D for $USER"
