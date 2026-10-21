#!/usr/bin/env bash
# Install or update the Tervory workers service on a host (Boston first). Idempotent. Run as root.
#
#   sudo workers/host/install.sh [--subid-start N] [--no-start]
#
# What it does, in order:
#   1. apt: podman, uidmap, slirp4netns, passt, python3-venv from the distro's own repos, after a dry
#      run that aborts if anything Docker/containerd/runc would be installed, removed or upgraded.
#      needrestart is told not to restart services.
#   2. User tervory-workers: no sudo, no docker group, no extra groups, nologin shell, home 0700.
#   3. subuid/subgid: the next free 65536 range (or --subid-start N), same start in both files.
#   4. Lingering (loginctl enable-linger) so the user's systemd manager runs without a login.
#   5. /etc/tervory-workers: dir root:tervory-workers 0750, worker.env and the App key 0640.
#      A missing worker.env is created from worker.env.example with EMPTY secret values.
#   6. Code to /srv/tervory-workers/app (root-owned, read-only to the user), venv in
#      /srv/tervory-workers/venv.
#   7. The systemd user unit, then checks podman as the user and fails loudly if rootless podman,
#      cgroups v2 delegation, the OCI runtime or slirp4netns are not usable.
#   8. Enables and (re)starts the unit unless --no-start.
#
# This file holds no secret. Values live only in /etc/tervory-workers on the server.
set -euo pipefail

WORKER_USER="tervory-workers"
ETC_DIR="/etc/tervory-workers"
ENV_FILE="$ETC_DIR/worker.env"
KEY_FILE="$ETC_DIR/github-app.pem"
SRV_DIR="/srv/tervory-workers"
APP_DIR="$SRV_DIR/app"
VENV_DIR="$SRV_DIR/venv"
UNIT_NAME="tervory-workers.service"
SUBID_COUNT=65536
SUBID_FLOOR=100000
APT_PACKAGES=(podman uidmap slirp4netns passt python3 python3-venv)
# Never let apt touch these. podman-docker replaces the docker CLI.
APT_FORBIDDEN_RE='^(Inst|Remv|Purg|Conf) (docker[^ ]*|containerd[^ ]*|runc|moby[^ ]*|podman-docker)( |$)'
SECRET_NAMES=(GITHUB_APP_ID GITHUB_APP_INSTALLATION_ID TANK_KEY_WORKERS)

die() { echo "install.sh: ERROR: $*" >&2; exit 1; }
say() { echo "install.sh: $*"; }

script_dir() { cd "$(dirname "${BASH_SOURCE[0]}")" && pwd; }

# Highest end of any range in the given subid files, rounded up to SUBID_FLOOR at least.
next_free_subid() {
  local files=("$@")
  awk -F: -v floor="$SUBID_FLOOR" '
    NF >= 3 && $2 ~ /^[0-9]+$/ && $3 ~ /^[0-9]+$/ { end = $2 + $3; if (end > max) max = end }
    END { if (max < floor) max = floor; print max }
  ' "${files[@]}" 2>/dev/null || echo "$SUBID_FLOOR"
}

# 0 when [start, start+count) overlaps any range owned by someone other than $user.
subid_overlaps() {
  local start=$1 count=$2 user=$3; shift 3
  awk -F: -v s="$start" -v c="$count" -v u="$user" '
    NF >= 3 && $1 != u { if (s < $2 + $3 && $2 < s + c) found = 1 }
    END { exit found ? 0 : 1 }
  ' "$@" 2>/dev/null
}

apt_install() {
  local missing=()
  for pkg in "${APT_PACKAGES[@]}"; do
    dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed" || missing+=("$pkg")
  done
  if [ "${#missing[@]}" -eq 0 ]; then
    say "packages already installed: ${APT_PACKAGES[*]}"
    return
  fi
  say "installing from the distro repos: ${missing[*]}"
  export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l NEEDRESTART_SUSPEND=1
  apt-get update -qq
  local plan
  plan=$(apt-get install -s --no-install-recommends "${missing[@]}")
  if grep -Eq "$APT_FORBIDDEN_RE" <<<"$plan"; then
    grep -E "$APT_FORBIDDEN_RE" <<<"$plan" >&2
    die "apt would touch Docker/containerd/runc. Aborting before any change."
  fi
  if grep -Eq '^Remv ' <<<"$plan"; then
    grep -E '^Remv ' <<<"$plan" >&2
    die "apt would remove packages. Aborting before any change."
  fi
  apt-get install -y -q --no-install-recommends "${missing[@]}"
}

ensure_user() {
  if ! id "$WORKER_USER" >/dev/null 2>&1; then
    say "creating user $WORKER_USER"
    useradd --create-home --shell /usr/sbin/nologin --user-group "$WORKER_USER"
  fi
  local groups
  groups=$(id -nG "$WORKER_USER")
  [ "$groups" = "$WORKER_USER" ] || die "$WORKER_USER must have no extra groups (has: $groups). Remove them by hand."
  if [ -r /etc/sudoers ] && grep -Rqs "^[^#]*\b$WORKER_USER\b" /etc/sudoers /etc/sudoers.d; then
    die "$WORKER_USER appears in sudoers. Remove it by hand."
  fi
  local members
  members=$(getent group "$WORKER_USER" | cut -d: -f4)
  [ -z "$members" ] || die "group $WORKER_USER must have no other members (has: $members)"
  chmod 0700 "$(getent passwd "$WORKER_USER" | cut -d: -f6)"
}

ensure_subids() {
  local requested=${1:-}
  local have_uid have_gid
  have_uid=$(awk -F: -v u="$WORKER_USER" '$1 == u { print $2 ":" $3 }' /etc/subuid 2>/dev/null || true)
  have_gid=$(awk -F: -v u="$WORKER_USER" '$1 == u { print $2 ":" $3 }' /etc/subgid 2>/dev/null || true)
  if [ -n "$have_uid" ] || [ -n "$have_gid" ]; then
    [ "$have_uid" = "$have_gid" ] || die "subuid ($have_uid) and subgid ($have_gid) differ for $WORKER_USER"
    if [ -n "$requested" ] && [ "$have_uid" != "$requested:$SUBID_COUNT" ]; then
      die "$WORKER_USER already has $have_uid, not $requested:$SUBID_COUNT"
    fi
    say "subuid/subgid already set: $have_uid"
    return
  fi
  local start=${requested:-$(next_free_subid /etc/subuid /etc/subgid)}
  [[ "$start" =~ ^[0-9]+$ ]] || die "bad subid start"
  if subid_overlaps "$start" "$SUBID_COUNT" "$WORKER_USER" /etc/subuid /etc/subgid; then
    die "subid range $start:$SUBID_COUNT overlaps another user"
  fi
  usermod --add-subuids "$start-$((start + SUBID_COUNT - 1))" --add-subgids "$start-$((start + SUBID_COUNT - 1))" "$WORKER_USER"
  say "subuid/subgid set: $start:$SUBID_COUNT"
}

ensure_linger() {
  loginctl enable-linger "$WORKER_USER"
  local uid
  uid=$(id -u "$WORKER_USER")
  for _ in $(seq 1 30); do
    [ -S "/run/user/$uid/bus" ] && return
    sleep 1
  done
  die "the user manager for $WORKER_USER did not start (no /run/user/$uid/bus)"
}

check_apparmor() {
  local restrict
  restrict=$(sysctl -n kernel.apparmor_restrict_unprivileged_userns 2>/dev/null || echo 0)
  if [ "$restrict" = "1" ]; then
    [ -f /etc/apparmor.d/podman ] || die "kernel.apparmor_restrict_unprivileged_userns=1 but /etc/apparmor.d/podman is missing"
    if [ -r /sys/kernel/security/apparmor/profiles ] && ! grep -q '^podman ' /sys/kernel/security/apparmor/profiles; then
      apparmor_parser -r /etc/apparmor.d/podman || die "could not load the podman AppArmor profile"
    fi
    say "AppArmor restricts unprivileged user namespaces; podman profile is loaded"
  fi
}

ensure_secrets_dir() {
  install -d -o root -g "$WORKER_USER" -m 0750 "$ETC_DIR"
  if [ ! -e "$ENV_FILE" ]; then
    install -o root -g "$WORKER_USER" -m 0640 "$(script_dir)/worker.env.example" "$ENV_FILE"
    say "created $ENV_FILE from the template. Fill the secret values on the server."
  fi
  for file in "$ENV_FILE" "$KEY_FILE"; do
    [ -e "$file" ] || continue
    [ ! -L "$file" ] || die "$file must not be a symlink"
    chown root:"$WORKER_USER" "$file"
    chmod 0640 "$file"
  done
  local name empty=()
  for name in "${SECRET_NAMES[@]}"; do
    grep -Eq "^${name}=.+" "$ENV_FILE" || empty+=("$name")
  done
  [ -s "$KEY_FILE" ] || empty+=("$(basename "$KEY_FILE")")
  if [ "${#empty[@]}" -gt 0 ]; then
    say "not set yet (names only): ${empty[*]}. The service starts but takes no task until they are."
  fi
}

deploy_code() {
  local src
  src=$(cd "$(script_dir)/../.." && pwd)
  [ -f "$src/workers/service.py" ] || die "run this from a checkout of tervory-tank"
  install -d -o root -g root -m 0755 "$SRV_DIR"
  local stage="$SRV_DIR/app.new"
  rm -rf "$stage"
  install -d -o root -g root -m 0755 "$stage"
  (cd "$src" && tar --exclude='__pycache__' --exclude='*.pyc' -cf - workers) | tar -C "$stage" --no-same-owner -xf -
  chown -R root:root "$stage"
  find "$stage" -type d -exec chmod 0755 {} +
  find "$stage" -type f -exec chmod 0644 {} +
  find "$stage" -type f -name '*.sh' -exec chmod 0755 {} +
  rm -rf "$SRV_DIR/app.old"
  [ ! -d "$APP_DIR" ] || mv "$APP_DIR" "$SRV_DIR/app.old"
  mv "$stage" "$APP_DIR"
  rm -rf "$SRV_DIR/app.old"
  if [ ! -x "$VENV_DIR/bin/python" ]; then
    python3 -m venv "$VENV_DIR"
  fi
  local want have
  want=$(sha256sum "$APP_DIR/workers/requirements.txt" | cut -d' ' -f1)
  have=$(cat "$VENV_DIR/.requirements.sha256" 2>/dev/null || true)
  if [ "$want" != "$have" ]; then
    "$VENV_DIR/bin/pip" install -q --disable-pip-version-check -r "$APP_DIR/workers/requirements.txt"
    echo "$want" > "$VENV_DIR/.requirements.sha256"
  fi
  chown -R root:root "$VENV_DIR"
  chmod -R go-w "$VENV_DIR"
  say "code in $APP_DIR, venv in $VENV_DIR"
}

as_user() {
  local uid
  uid=$(id -u "$WORKER_USER")
  (cd / && runuser -u "$WORKER_USER" -- env -i \
    HOME="$(getent passwd "$WORKER_USER" | cut -d: -f6)" USER="$WORKER_USER" LOGNAME="$WORKER_USER" \
    PATH=/usr/local/bin:/usr/bin:/bin XDG_RUNTIME_DIR="/run/user/$uid" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" "$@")
}

install_unit() {
  local home unit_dir
  home=$(getent passwd "$WORKER_USER" | cut -d: -f6)
  unit_dir="$home/.config/systemd/user"
  as_user mkdir -p "$unit_dir"
  install -o "$WORKER_USER" -g "$WORKER_USER" -m 0644 "$(script_dir)/$UNIT_NAME" "$unit_dir/$UNIT_NAME"
  as_user systemctl --user daemon-reload
}

check_podman() {
  local info
  info=$(as_user podman info --format json) || die "podman info failed as $WORKER_USER"
  python3 - "$info" <<'PY' || die "rootless podman is not usable as the worker user (see above)"
import json, sys
info = json.loads(sys.argv[1])
host = info.get("host", {})
errors = []
if not host.get("security", {}).get("rootless"):
    errors.append("podman is not rootless")
if host.get("cgroupVersion") != "v2":
    errors.append("cgroups v2 is required")
missing = {"cpu", "memory", "pids"} - set(host.get("cgroupControllers") or [])
if missing:
    errors.append("cgroup controllers not delegated: " + ",".join(sorted(missing)))
runtime = (host.get("ociRuntime") or {}).get("name")
if not runtime:
    errors.append("no OCI runtime")
slirp = (host.get("slirp4netns") or {}).get("executable")
if not slirp:
    errors.append("slirp4netns is missing")
version = str(info.get("version", {}).get("Version", ""))
if not version.startswith("5."):
    errors.append(f"podman {version}: slirp4netns needs podman 5 (podman 6 removed it)")
for line in errors:
    print("install.sh: ERROR:", line, file=sys.stderr)
print(f"install.sh: podman {version}, runtime {runtime}, cgroups v2 controllers {sorted(host.get('cgroupControllers') or [])}")
sys.exit(1 if errors else 0)
PY
}

start_unit() {
  as_user systemctl --user enable "$UNIT_NAME" >/dev/null
  as_user systemctl --user restart "$UNIT_NAME"
  sleep 3
  as_user systemctl --user is-active --quiet "$UNIT_NAME" || die "$UNIT_NAME did not stay active"
  say "$UNIT_NAME is active"
}

main() {
  local subid_start="" start=1
  while [ $# -gt 0 ]; do
    case "$1" in
      --subid-start) subid_start=${2:?}; shift 2 ;;
      --no-start) start=0; shift ;;
      *) die "unknown option $1" ;;
    esac
  done
  [ "$(id -u)" -eq 0 ] || die "run as root"
  apt_install
  ensure_user
  ensure_subids "$subid_start"
  ensure_linger
  check_apparmor
  ensure_secrets_dir
  deploy_code
  install_unit
  check_podman
  if [ "$start" -eq 1 ]; then
    start_unit
  fi
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main "$@"
fi
