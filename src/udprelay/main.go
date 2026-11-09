package main

import (
	"bufio"
	"encoding/binary"
	"fmt"
	"io"
	"net"
	"os"
	"strings"
	"sync"
	"time"
)

const (
	listenPort = 12346
	socksAddr  = "127.0.0.1:1080"
	idleLimit  = 45 * time.Second
)

type flow struct {
	up     *net.UDPConn
	ctl    net.Conn
	hdr    []byte
	client *net.UDPAddr
	last   time.Time
}

var (
	mu    sync.Mutex
	flows = map[string]*flow{}
	srv   *net.UDPConn
)

func origDst(c *net.UDPAddr) (net.IP, uint16, bool) {
	f, err := os.Open("/proc/net/nf_conntrack")
	if err != nil {
		return nil, 0, false
	}
	defer f.Close()
	cip, cport, rport := c.IP.String(), fmt.Sprint(c.Port), fmt.Sprint(listenPort)
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 64*1024), 64*1024)
	for sc.Scan() {
		l := sc.Text()
		if !strings.Contains(l, " udp ") {
			continue
		}
		var src, dst, sp, dp []string
		for _, t := range strings.Fields(l) {
			switch {
			case strings.HasPrefix(t, "src="):
				src = append(src, t[4:])
			case strings.HasPrefix(t, "dst="):
				dst = append(dst, t[4:])
			case strings.HasPrefix(t, "sport="):
				sp = append(sp, t[6:])
			case strings.HasPrefix(t, "dport="):
				dp = append(dp, t[6:])
			}
		}
		if len(src) < 2 || len(sp) < 2 || len(dst) < 1 || len(dp) < 1 {
			continue
		}
		if src[0] == cip && sp[0] == cport && sp[1] == rport {
			var p int
			fmt.Sscan(dp[0], &p)
			ip := net.ParseIP(dst[0]).To4()
			if ip != nil && p > 0 {
				return ip, uint16(p), true
			}
		}
	}
	return nil, 0, false
}

func newFlow(client *net.UDPAddr, ip net.IP, port uint16) (*flow, error) {
	ctl, err := net.DialTimeout("tcp", socksAddr, 5*time.Second)
	if err != nil {
		return nil, err
	}
	ctl.SetDeadline(time.Now().Add(5 * time.Second))
	ctl.Write([]byte{5, 1, 0})
	b := make([]byte, 2)
	if _, err = io.ReadFull(ctl, b); err != nil || b[1] != 0 {
		ctl.Close()
		return nil, fmt.Errorf("socks auth")
	}
	ctl.Write([]byte{5, 3, 0, 1, 0, 0, 0, 0, 0, 0})
	r := make([]byte, 10)
	if _, err = io.ReadFull(ctl, r); err != nil || r[1] != 0 {
		ctl.Close()
		return nil, fmt.Errorf("socks assoc")
	}
	ctl.SetDeadline(time.Time{})
	relay := &net.UDPAddr{IP: net.ParseIP("127.0.0.1"), Port: int(binary.BigEndian.Uint16(r[8:10]))}
	up, err := net.DialUDP("udp", nil, relay)
	if err != nil {
		ctl.Close()
		return nil, err
	}
	hdr := []byte{0, 0, 0, 1, ip[0], ip[1], ip[2], ip[3], 0, 0}
	binary.BigEndian.PutUint16(hdr[8:], port)
	fl := &flow{up: up, ctl: ctl, hdr: hdr, client: client, last: time.Now()}
	go fl.readUp(client.String())
	go func() {
		io.Copy(io.Discard, ctl)
		closeFlow(client.String())
	}()
	return fl, nil
}

func (fl *flow) readUp(key string) {
	buf := make([]byte, 65536)
	for {
		n, err := fl.up.Read(buf)
		if err != nil {
			closeFlow(key)
			return
		}
		off := 10
		if n > 4 {
			switch buf[3] {
			case 3:
				off = 7 + int(buf[4])
			case 4:
				off = 22
			}
		}
		if n <= off {
			continue
		}
		srv.WriteToUDP(buf[off:n], fl.client)
		mu.Lock()
		fl.last = time.Now()
		mu.Unlock()
	}
}

func closeFlow(key string) {
	mu.Lock()
	fl := flows[key]
	delete(flows, key)
	mu.Unlock()
	if fl != nil {
		fl.up.Close()
		fl.ctl.Close()
	}
}

func main() {
	var err error
	srv, err = net.ListenUDP("udp", &net.UDPAddr{Port: listenPort})
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	go func() {
		for range time.Tick(10 * time.Second) {
			var dead []string
			mu.Lock()
			for k, f := range flows {
				if time.Since(f.last) > idleLimit {
					dead = append(dead, k)
				}
			}
			mu.Unlock()
			for _, k := range dead {
				closeFlow(k)
			}
		}
	}()
	buf := make([]byte, 65536)
	for {
		n, client, err := srv.ReadFromUDP(buf)
		if err != nil {
			continue
		}
		key := client.String()
		mu.Lock()
		fl := flows[key]
		mu.Unlock()
		if fl == nil {
			var ip net.IP
			var port uint16
			ok := false
			for i := 0; i < 3 && !ok; i++ {
				ip, port, ok = origDst(client)
				if !ok {
					time.Sleep(5 * time.Millisecond)
				}
			}
			if !ok {
				continue
			}
			fl, err = newFlow(client, ip, port)
			if err != nil {
				continue
			}
			mu.Lock()
			flows[key] = fl
			mu.Unlock()
		}
		fl.up.Write(append(append([]byte{}, fl.hdr...), buf[:n]...))
		mu.Lock()
		fl.last = time.Now()
		mu.Unlock()
	}
}
