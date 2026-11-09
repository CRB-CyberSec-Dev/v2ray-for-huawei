import os, socket, ssl, struct, sys, time
# speed.cloudflare.com 403s large/repeated downloads, so use OVH with a Range request
def get(n, socks=None, host="proof.ovh.net"):
    if socks:
        s = socket.create_connection(socks, timeout=15)
        s.sendall(b"\x05\x01\x00"); s.recv(2)
        hb = host.encode()
        s.sendall(b"\x05\x01\x00\x03" + bytes([len(hb)]) + hb + struct.pack(">H", 443))
        r = s.recv(10)
        if r[1] != 0: raise Exception("socks fail %d" % r[1])
    else:
        s = socket.create_connection((host, 443), timeout=15)
    t0 = time.time()
    s = ssl.create_default_context().wrap_socket(s, server_hostname=host)
    s.sendall(("GET /files/100Mb.dat HTTP/1.1\r\nHost: %s\r\nRange: bytes=0-%d\r\nConnection: close\r\n\r\n" % (host, n - 1)).encode())
    got = 0; first = None
    while True:
        d = s.recv(65536)
        if not d: break
        if first is None: first = time.time()
        got += len(d)
    t = time.time() - t0
    return got, t, first - t0
mode = sys.argv[1]; n = int(sys.argv[2])
socks = (os.environ.get("ROUTER", "192.168.8.1"), 1080) if mode == "tunnel" else None
got, t, ttfb = get(n, socks)
print("%s: %.1f MB in %.1fs = %.2f Mbit/s (first byte %.2fs)" % (mode, got/1e6, t, got*8/t/1e6, ttfb))
