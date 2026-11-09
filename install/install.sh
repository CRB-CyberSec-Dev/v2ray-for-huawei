#!/system/bin/busybox ash
# Device-side installer, run as root on the router. Idempotent: safe to re-run for updates.
#   busybox sh install.sh [STAGING_DIR]
# STAGING_DIR (default: the directory of this script) must contain:
#   system/xray/...   (router/system/xray from the repo)
#   data/xray/xray.conf.example
#   bin/xray bin/udprelay   (ARM binaries from the GitHub release, or built yourself)
# Layout it creates:
#   /system/xray  programs, scripts, web panel   (read-only after boot, remounted rw only here)
#   /data/xray    config, state, logs            (rw + persistent)
B=busybox
# The router's adbd shell leaves its terminal open on fd 10; daemons started from here would
# inherit it and `adb shell` would never return.
exec 10>&-
SRC=${1:-$($B dirname "$0")}
DIR=/system/xray
ST=/data/xray
HOOK='/system/xray/boot.sh > /dev/null 2>&1 &'

die() { echo "ERROR: $*" >&2; mount -o remount,ro /system 2>/dev/null; exit 1; }

[ "$($B id -u)" = 0 ] || die "run as root"
for f in system/xray/boot.sh system/xray/www/cgi-bin/index.cgi data/xray/xray.conf.example bin/xray bin/udprelay; do
  [ -f "$SRC/$f" ] || die "missing $SRC/$f"
done

# space check: binaries + scripts need roughly their own size on /system
NEED=$(( ($($B wc -c < "$SRC/bin/xray") + $($B wc -c < "$SRC/bin/udprelay")) / 1024 + 512 ))
# (busybox df wraps long device names onto their own line, so read the last line only)
HAVE=$($B df -k /system | $B tail -1 | $B awk '{print $(NF-2)}')
[ -f "$DIR/xray" ] && HAVE=$((HAVE + $($B wc -c < "$DIR/xray") / 1024))
[ -f "$DIR/udprelay" ] && HAVE=$((HAVE + $($B wc -c < "$DIR/udprelay") / 1024))
[ "$HAVE" -ge "$NEED" ] || die "/system needs ${NEED} KB, has ${HAVE} KB free"

# 1) writable side
$B mkdir -p "$ST"
$B chmod 700 "$ST"
# migrate from older layouts that kept config/state in /system/xray (never overwrites /data)
for f in xray.conf config.json tunnel_state redirect_state udp_mode cipher_mode; do
  [ -f "$DIR/$f" ] && [ ! -f "$ST/$f" ] && $B cp -p "$DIR/$f" "$ST/$f" && echo "migrated $f to $ST"
done
if [ ! -f "$ST/xray.conf" ]; then
  $B cp "$SRC/data/xray/xray.conf.example" "$ST/xray.conf"
  echo "created $ST/xray.conf from the example (set your server in the panel)"
fi

# 2) program side
mount -o remount,rw /system || die "cannot remount /system rw"
$B mkdir -p "$DIR/www/cgi-bin"
changed() { [ "$($B md5sum < "$1")" != "$($B md5sum < "$2" 2>/dev/null)" ]; }
# Write changed files in place (same inode). Replacing by rename would leave running scripts
# (watchdog.sh) holding the deleted old file, and then /system refuses to go back to read-only.
for f in $(cd "$SRC/system/xray" && $B find . -type f); do
  f=${f#./}
  changed "$SRC/system/xray/$f" "$DIR/$f" || continue
  $B mkdir -p "$($B dirname "$DIR/$f")"
  $B cat "$SRC/system/xray/$f" > "$DIR/$f" || die "writing $DIR/$f"
  case "$f" in
    *.sh|*.cgi) $B chmod 755 "$DIR/$f" ;;
    *) $B chmod 644 "$DIR/$f" ;;
  esac
  echo "updated $f"
done
# A running executable can't be overwritten ("Text file busy"), so stop it first;
# the watchdog (or step 4 on a fresh install) starts the new one.
for b in xray udprelay; do
  changed "$SRC/bin/$b" "$DIR/$b" || continue
  for sig in TERM KILL; do
    for p in $($B ps | $B grep "/system/xray/$b" | $B grep -v grep | $B awk '{print $1}'); do $B kill -$sig "$p" 2>/dev/null; done
    $B sleep 1
  done
  $B cat "$SRC/bin/$b" > "$DIR/$b" || die "writing $DIR/$b"
  $B chmod 755 "$DIR/$b"
  echo "installed $b"
done
# "/" must be served by cgi-bin/index.cgi (login gate), so no static index.html
$B rm -f "$DIR/www/index.html"
# stale writable files from old layouts
for f in xray.conf config.json tunnel_state redirect_state udp_mode cipher_mode boot.log boot_start.log httpd.log xray.log watchdog.log watchdog_stdout.log last_restart.log udprelay.log; do
  $B rm -f "$DIR/$f"
done

# 3) boot hook (needs a firmware whose init runs /system/etc/autorun.sh as root)
if [ -f /system/etc/autorun.sh ]; then
  if ! $B grep -q '/system/xray/boot.sh' /system/etc/autorun.sh; then
    $B cp -p /system/etc/autorun.sh "$ST/autorun.sh.orig"
    printf '\n# V2Ray for Huawei: tunnel + web panel autostart\n%s\n' "$HOOK" >> /system/etc/autorun.sh
    echo "added boot hook to /system/etc/autorun.sh (original saved to $ST/autorun.sh.orig)"
  else
    # older installs redirected output into /system, which fails once /system is read-only
    $B sed -i 's#^/system/xray/boot.sh > /system/xray/boot.log 2>&1 &$#/system/xray/boot.sh > /dev/null 2>\&1 \&#' /system/etc/autorun.sh
  fi
else
  echo "WARNING: /system/etc/autorun.sh not found - no boot hook installed."
  echo "         Add this line to whatever your firmware runs as root at boot:"
  echo "         $HOOK"
fi

$B sync
# a running watchdog keeps its script open: restart it (it kills older copies itself) so it runs
# the current file and nothing pins a stale inode on /system
if $B ps | $B grep -q '[w]atchdog.sh'; then
  $B setsid "$DIR/watchdog.sh" > "$ST/watchdog_stdout.log" 2>&1 < /dev/null &
  $B sleep 2
fi
if mount -o remount,ro /system; then
  echo "/system is back to read-only"
else
  echo "WARNING: /system is still read-write (a process holds a replaced file); a reboot makes it read-only again"
fi

# 4) start now if nothing is running yet (updates of a running install: restart from the panel or reboot)
if $B ps | $B grep -q '/system/xray/xray run'; then
  echo "xray already running - restart it from the panel (or reboot) to load updated files"
else
  "$DIR/boot.sh" < /dev/null > /dev/null 2>&1 &
  echo "started"
fi
LAN=$($B ifconfig br0 2>/dev/null | $B sed -n 's/.*inet addr:\([0-9.]*\).*/\1/p')
echo "panel: http://${LAN:-<router-ip>}:8081  (sign in with the router admin account)"
