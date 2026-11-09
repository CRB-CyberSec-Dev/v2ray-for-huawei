# Trojan download benchmark run from the PC, bypassing the router's xray.
# Tells whether the ~6 Mbit/s ceiling is the router CPU or the server/ISP path.
# usage: python tools/trojan_bench.py BYTES [SNI]   (reads router/data/xray/xray.conf next to the repo root, or $XRAY_CONF)
import hashlib, os, socket, ssl, struct, sys, time

conf = {}
for line in open(os.environ.get("XRAY_CONF", os.path.join(os.path.dirname(__file__), "..", "router", "data", "xray", "xray.conf"))):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1)
        conf[k] = v.strip('"')
n = int(sys.argv[1])
sni = sys.argv[2] if len(sys.argv) > 2 else conf["SNI"]
host, path = "proof.ovh.net", "/files/100Mb.dat"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE  # server uses a pinned cert that doesn't match the spoofed SNI
s = ctx.wrap_socket(socket.create_connection((conf["ADDR"], int(conf["PORT"])), timeout=15), server_hostname=sni)
print("tls:", s.version(), s.cipher()[0])
hb = host.encode()
s.sendall(hashlib.sha224(conf["SECRET"].encode()).hexdigest().encode() + b"\r\n"
          + b"\x01\x03" + bytes([len(hb)]) + hb + struct.pack(">H", 443) + b"\r\n")
t0 = time.time()
# TLS-in-TLS: python can't wrap an SSLSocket again, so drive the inner TLS through memory BIOs
inc, out = ssl.MemoryBIO(), ssl.MemoryBIO()
inner = ssl.create_default_context().wrap_bio(inc, out, server_hostname=host)

def pump(op, *a):
    while True:
        try:
            r = op(*a)
            if out.pending:
                s.sendall(out.read())
            return r
        except ssl.SSLWantReadError:
            if out.pending:
                s.sendall(out.read())
            d = s.recv(65536)
            if not d:
                raise EOFError
            inc.write(d)

pump(inner.do_handshake)
pump(inner.write, ("GET %s HTTP/1.1\r\nHost: %s\r\nRange: bytes=0-%d\r\nConnection: close\r\n\r\n" % (path, host, n - 1)).encode())
got = 0
while got < n:
    try:
        d = pump(inner.read, 65536)
    except (EOFError, ssl.SSLZeroReturnError):
        break
    if not d:
        break
    got += len(d)
t = time.time() - t0
print("pc-trojan: %.1f MB in %.1fs = %.2f Mbit/s" % (got / 1e6, t, got * 8 / t / 1e6))
