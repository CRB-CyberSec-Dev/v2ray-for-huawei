# AGENTS.md: porting V2Ray for Huawei to another router

This file is the operating manual for anyone (human or AI coding agent) bringing this project to a
router other than the Huawei B310s-925 it was built on. Read all of it before touching a device.
The [README](README.md) explains what the project does; this file explains how it is wired, what a
target router must provide, and every trap found while building it.

## 1. Rules (read first)

1. **Ask the owner before anything irreversible or disruptive**: flashing firmware, writing to raw
   flash (`/dev/mtd*`), changing NV items, rebooting, changing the router's admin settings, or
   pushing anything to a remote repository. Show what you will run.
2. **Back up before the first write.** Dump every flash partition and verify the checksum on both
   sides (section 4.2). Keep the dumps off GitHub: they contain IMEI, keys and calibration data.
3. **Never touch** bootloader, NV, `oeminfo`, IMEI or calibration partitions. This project only
   needs files on mounted filesystems.
4. **Never commit secrets**: `xray.conf`, `config.json`, partition dumps, firmware images.
5. **`/system` stays read-only at runtime.** Everything the running system writes goes to the
   persistent read-write directory (`/data/xray` here). Only the installer remounts `/system`.
6. **Prove it on the device.** Run the verification list in section 6, including the reboot path,
   and report exactly what you verified and what you could not.

## 2. Architecture

```
LAN ─► br0 ─► iptables nat PREROUTING
               ├─ XRAY_REDIRECT  (TCP) ─► REDIRECT :12345 ─► xray dokodemo-door (followRedirect)
               └─ XRAY_UDPREDIR  (UDP) ─► REDIRECT :12346 ─► udprelay ─► xray SOCKS5 :1080 UDP ASSOCIATE
xray outbound: trojan | vless | shadowsocks, TLS 1.3 (uTLS fingerprint, or chrome-chacha) ─► WAN
XRAY_UDPBLOCK (filter FORWARD): drops LAN UDP except DNS and private ranges (leak protection mode)

panel: busybox httpd :8081 -h /system/xray/www
  /                    ─► cgi-bin/index.cgi ─► login.html or panel.html (by session cookie)
  cgi-bin/login.cgi    ─► router web UI /api/user/login (the router checks the password)
  cgi-bin/*.cgi        ─► . auth.sh; require_auth ─► scripts in /system/xray
boot:  /system/etc/autorun.sh ─► boot.sh ─► httpd, start.sh, UDP mode, redirect, watchdog.sh
```

### Files

| File (repo `router/system/xray/`) | Role |
|---|---|
| `boot.sh` | boot entry: creates `/data/xray`, starts panel, restores tunnel/UDP/redirect state, starts watchdog |
| `start.sh` / `stop.sh` / `restart.sh` | xray process control (`restart` regenerates config) |
| `gen_config.sh` | `/data/xray/xray.conf` (shell vars) ─► `/data/xray/config.json` (xray JSON) |
| `redirect_on.sh` / `redirect_off.sh` | whole-LAN TCP redirect chain |
| `udp_tunnel.sh` / `udp_untunnel.sh` | UDP redirect chain + udprelay process |
| `udp_block.sh` / `udp_unblock.sh` | UDP leak-block chain |
| `watchdog.sh` | every 15 s: re-applies whatever state files say should be running |
| `status.sh` | CLI status for a shell session |
| `auth.sh` | session check sourced by every CGI except login |
| `panel.html`, `login.html`, `www/theme.css` | UI (self-contained: no CDN, must work with the tunnel down) |
| `www/cgi-bin/index.cgi` | serves `/` (login page or panel) |
| `www/cgi-bin/login.cgi` | challenge + hashed login against the router's own account |
| `www/cgi-bin/logout.cgi` | ends the session |
| `www/cgi-bin/status.cgi`, `metrics.cgi`, `log.cgi` | JSON/text for the panel |
| `www/cgi-bin/control.cgi`, `save.cgi` | actions and server settings |

State files in `/data/xray`: `tunnel_state` (1/0), `redirect_state` (1/0), `udp_mode`
(`direct`/`tunnel`/`block`), `cipher_mode` (`fast`/`compat`), `xray.conf`, `config.json`, logs.

`src/udprelay` is a tiny Go program: it reads each LAN UDP flow's original destination from
`/proc/net/nf_conntrack` and forwards it through xray's SOCKS5 UDP ASSOCIATE.
`src/xray-patch` adds the `chrome-chacha` fingerprint to Xray-core.

## 3. What a target router must provide

| Need | How to check | B310s-925 value |
|---|---|---|
| Root shell | `adb connect IP:5555` or telnet | adbd + telnetd started by `autorun.sh` |
| Root boot hook | find what init runs: `/system/etc/autorun.sh`, `/etc/init.d/*`, `rc.local`, `/etc/rc.d` | `/system/etc/autorun.sh` |
| CPU arch | `cat /proc/cpuinfo` (`uname` may be missing) | ARMv7 Cortex-A9 (`CPU part 0xc09`), no AES, no NEON |
| RAM | `grep MemTotal /proc/meminfo` | 134 MB; xray uses ~25-30 MB |
| Space for binaries (~40 MB) | `busybox df -k` | `/system` 100 MB yaffs2 (ro after boot) |
| Persistent rw dir (~1 MB) | `mount`, then write+reboot test | `/data` 10 MB yaffs2 |
| Staging space for install | a writable mount with ~40 MB | `/online` (Huawei update partition) |
| BusyBox applets | `busybox --list` | v1.21.1: ash awk sed grep ps kill setsid httpd nc sha256sum base64 md5sum dd od tr stat date ifconfig df find head tail wc sleep touch cut |
| httpd with CGI | `busybox httpd --help` | yes |
| iptables nat REDIRECT | `iptables -t nat -L` | iptables 1.4.11.1 |
| conntrack table | `ls /proc/net/nf_conntrack` | present |
| LAN bridge / WAN iface | `busybox ifconfig` | `br0` / `wan0` |
| Web UI login API | see 5.4 | Huawei `/api/user/login`, `password_type` 4 |

Below about 64 MB RAM, xray is marginal: lower `GOMEMLIMIT` and expect slowdowns.

## 4. Porting procedure

### 4.1 Recon (read-only)

```sh
cat /proc/cpuinfo; grep MemTotal /proc/meminfo; cat /proc/mtd; mount; busybox df -k
busybox --list; busybox httpd --help; iptables --version; iptables -t nat -L -n
busybox ifconfig; ls /proc/net/nf_conntrack; ls /system/etc /etc/init.d 2>/dev/null
```

Write the results into a table like section 3 before changing anything.

### 4.2 Back up flash

`dd` fails on some NAND regions; `nanddump` from busybox works. Per partition (read-only device):

```sh
busybox nanddump -s 0 -l <SIZE> -f - /dev/mtd/mtd<N>ro | busybox md5sum        # on the router
adb shell "busybox nanddump -s 0 -l <SIZE> -f - /dev/mtd/mtd<N>ro | busybox base64" > mtdN.b64  # PC
```

Decode on the PC, compare the md5 with the router's, and retry on mismatch. Sizes come from `/proc/mtd`.

### 4.3 Adapt the parameters

Every device-specific value in the repo:

| Value | Where | Notes |
|---|---|---|
| `/system/xray` (program dir) | all scripts, CGIs, process-match patterns like `'/system/xray/xray run'` | `grep -rn /system/xray router/ install/` |
| `/data/xray` (state dir) | `boot.sh start.sh gen_config.sh watchdog.sh udp_tunnel.sh status.sh install.sh`, CGIs | must survive reboot and be writable at boot |
| `/tmp/xraypanel` (sessions) | `auth.sh`, `login.cgi` | any RAM dir |
| shebang `/system/bin/busybox ash` | every script | point at the target's busybox |
| `br0` | `redirect_*.sh`, `udp_*.sh`, `login.cgi` (router LAN IP) | LAN bridge |
| `wan0` | `metrics.cgi` | WAN interface for the throughput tiles |
| `8081` | `boot.sh`, `watchdog.sh`, `status.sh`, `install.sh` | panel port |
| `1080 1081 12345` | `gen_config.sh` | SOCKS, HTTP, redirect inbound |
| `12346`, `127.0.0.1:1080` | `src/udprelay/main.go`, `udp_tunnel.sh` | UDP relay |
| `GOMEMLIMIT` 40MiB / 16MiB | `start.sh`, `udp_tunnel.sh` | scale to RAM |
| private ranges | `redirect_on.sh`, `udp_*.sh`, `gen_config.sh` | add the LAN subnet if it is not RFC1918 |
| boot hook line | `install.sh` (`HOOK`, autorun path) | target's root boot script |
| login backend | `login.cgi` | section 5.4 |

### 4.4 Build for the target CPU

| CPU | Go env |
|---|---|
| ARMv7 (Cortex-A7/A9/A53 in 32-bit) | `GOARCH=arm GOARM=7` |
| ARMv5/v6 | `GOARCH=arm GOARM=5` or `6` |
| ARM64 | `GOARCH=arm64` |
| MIPS big-endian (many Qualcomm/Atheros, older Broadcom) | `GOARCH=mips GOMIPS=softfloat` |
| MIPS little-endian (MediaTek MT7621/MT76x8) | `GOARCH=mipsle GOMIPS=softfloat` |

Always `CGO_ENABLED=0` (static). Build commands are in the README. Pick the cipher by measuring:
`tools/cipherbench` prints AES-GCM vs ChaCha20 throughput on the device. Without AES
instructions, `fast` (chrome-chacha) wins.

### 4.5 Install

`install/deploy.sh ROUTER_IP` (PC side, adb) stages files and runs `install/install.sh` on the
router. Without adb, copy the same tree (`system/`, `data/xray/xray.conf.example`, `bin/xray`,
`bin/udprelay`, `install.sh`) by any means and run `busybox sh install.sh STAGING_DIR` as root.

## 5. Pitfalls found on the B310s (and their fixes)

1. **`/system` is read-only after boot.** A shell redirect into a read-only path makes the shell
   skip the whole command, so `boot.sh > /system/xray/boot.log` meant nothing started after a
   reboot. All runtime writes go to `/data/xray`; the boot hook redirects to `/dev/null`.
2. **Replacing files on `/system`.** Overwriting a running binary fails with *Text file busy*.
   Replacing a running script by rename leaves the old inode open, and then
   `mount -o remount,ro /system` fails with *Device or resource busy*. `install.sh` writes changed
   files in place, stops a binary before replacing it, and restarts the watchdog before the remount.
3. **`adb shell` never returns after starting daemons.** The router's adbd shell leaves the
   terminal on fd 10, and busybox ash parks copies of stdout in high fds. Daemons inherit them and
   keep the session open. Fix: `exec 10>&-`, and run the installer with
   `< /dev/null > log 2>&1`. A real boot has no terminal, so this only affects installs over adb.
4. **`/data` is only 10 MB.** Stage the 34 MB binary elsewhere (`deploy.sh` picks the first
   writable mount with room; on the B310s that is `/online`) and clean it up afterwards.
5. **busybox httpd 1.21:**
   - ignores CGI `Status:` headers; to send 401, print the full status line `HTTP/1.0 401 Unauthorized` first;
   - passes `HTTP_COOKIE`, `REQUEST_METHOD`, `QUERY_STRING`, `CONTENT_LENGTH` (POST body on stdin);
   - serves `/` through `cgi-bin/index.cgi` when `www/` has no `index.html` (this is the login gate);
   - CGI headers end in LF only: browsers are fine, PowerShell `Invoke-WebRequest` rejects them (use curl).
6. **Huawei web API on `127.0.0.1` answers 307 redirect.** Call it on the LAN IP (`ifconfig br0`).
7. **Huawei's busybox `wget` is a custom upload/download tool**, not GNU-style wget. Use `nc` for HTTP.
8. **busybox `base64` wraps at 76 columns.** Pipe through `tr -d '\n'` before using it in a hash.
9. **Word-splitting user input globs.** `login.cgi` splits the POST body on `&`; a `*` in a password
   would expand to file names. `set -f` before splitting.
10. **No `crypto.subtle` on plain-HTTP pages**, except on localhost. The login page carries its own
    SHA-256, verified against Python's `hashlib` on 211 inputs including non-ASCII.
11. **Go on a small router**: `GOMEMLIMIT`, `GOGC=40` and `GOMAXPROCS=1` keep xray around 25-30 MB RSS.
12. **CRLF breaks busybox scripts.** `.gitattributes` forces LF; check with `grep -rlI $'\r' router install`.
13. **Git Bash on Windows**: set `MSYS_NO_PATHCONV=1` so remote paths like `/data/...` are not
    rewritten, and pass local paths to `adb.exe` as `C:/...` (`pwd -W`).
14. **`uname` may be missing**: use `/proc/cpuinfo`.

### 5.4 Login backend

Huawei HiLink routers (B310 here; other Huawei LTE routers likely, verify):

1. `GET /api/webserver/SesTokInfo` gives `<SesInfo>` (cookie) and `<TokInfo>` (one-time token).
2. `GET /api/user/state-login` with that cookie gives `<password_type>`. `4` means
   `base64(sha256hex(user + base64(sha256hex(password)) + token))`.
3. `POST /api/user/login` with headers `Cookie: <SesInfo>` and `__RequestVerificationToken: <token>`, body
   `<?xml version="1.0" encoding="UTF-8"?><request><Username>..</Username><Password>HASH</Password><password_type>4</password_type></request>`.
   `<response>OK</response>` means success.
4. Log that session out (`POST /api/user/logout` with the new `SessionID` cookie and the
   `__RequestVerificationTokenone` response header) so the panel never holds a router login.

Error codes seen: `108001`/`108002`/`108006` wrong username or password, `108007` too many attempts (locked),
`108003` already logged in, `125002`/`125003` session or token invalid.

If `password_type` is not 4, or the router is not Huawei, replace only the verification step in
`login.cgi`. Keep the challenge flow so the password never travels in clear. One option is a salted
hash stored in the persistent dir with the same challenge construction.

### 5.5 Other platforms (unverified hints)

- **OpenWrt**: much simpler. Use a procd init script instead of `autorun.sh`, `/etc` is writable,
  fw4/nftables replaces iptables (rewrite the four chain scripts), and `uhttpd` can serve the CGIs.
  The login backend could use rpcd/ubus sessions.
- **Other Android-based LTE routers** (HiSilicon/Balong): expect the same read-only `/system` +
  small `/data` split as the B310s.

## 6. Verification checklist

Run all of these on the device and report the results:

```sh
# processes: httpd :8081, xray run -c /data/xray/config.json, udprelay (if UDP tunnel), watchdog.sh
busybox ps | busybox grep -E '[x]ray run|[h]ttpd -f|[w]atchdog|[u]dprelay'
mount | busybox grep ' /system '          # must say ro
```

From a LAN PC:

```sh
curl -s http://ROUTER:8081/ | grep -o '<title>[^<]*'               # login page
curl -s -o /dev/null -w '%{http_code}\n' http://ROUTER:8081/cgi-bin/status.cgi   # 401
curl -s -x http://ROUTER:1081 https://www.cloudflare.com/cdn-cgi/trace           # ip= is the server's
curl -s https://www.cloudflare.com/cdn-cgi/trace                                  # same ip when LAN redirect is on
```

- Sign in with a wrong password (expect "Wrong username or password"), then the right one.
- **Reboot path**: power-cycle, or simulate one: with `/system` read-only, run the exact boot-hook
  line, then repeat the checks above.

## 7. Conventions

- Shell: busybox ash, `$B`/`busybox` prefix for applets, LF line endings, small focused scripts.
- Runtime writes only under the state dir; scripts are idempotent (delete-then-create chains).
- UI: no external resources; dark glass theme in `www/theme.css`; keep element IDs the panel JS uses.
- Never commit `xray.conf`, `config.json`, dumps or firmware (`.gitignore` covers the usual names).
