import struct, sys, os

src, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)
d = open(src, 'rb').read()
MAGIC = bytes.fromhex('55aa5aa5')
pos = d.find(MAGIC)
print('first magic at', hex(pos), 'file size', len(d))
n = 0
while pos != -1 and pos + 98 <= len(d):
    hl, unk = struct.unpack_from('<II', d, pos + 4)
    hw = d[pos + 12:pos + 20].rstrip(b'\0').decode('latin1')
    seq, size = struct.unpack_from('<II', d, pos + 20)
    date = d[pos + 28:pos + 44].rstrip(b'\0').decode('latin1')
    tm = d[pos + 44:pos + 60].rstrip(b'\0').decode('latin1')
    ftype = d[pos + 60:pos + 76].rstrip(b'\0').decode('latin1')
    # fixed layout varies: take a printable tail of the header as the name hint
    hdr = d[pos:pos + hl]
    start = pos + hl
    end = start + size
    print(f'#{n} @0x{pos:x} hl={hl} hw={hw!r} seq=0x{seq:x} size={size} date={date} {tm} raw={hdr[60:100]!r}')
    if end > len(d):
        print('  entry runs past EOF, stopping'); break
    open(os.path.join(outdir, f'{n:02d}_seq{seq:08x}.bin'), 'wb').write(d[start:end])
    n += 1
    nxt = (end + 3) & ~3
    pos = d.find(MAGIC, end)
    if pos != nxt:
        print(f'  next magic at {hex(pos) if pos!=-1 else None} (expected 0x{nxt:x})')
print('entries:', n)
