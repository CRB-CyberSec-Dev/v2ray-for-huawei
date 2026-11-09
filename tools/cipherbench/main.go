// Measures AEAD decrypt throughput on the router to pick the TLS cipher.
package main

import (
	"crypto/aes"
	"crypto/cipher"
	"fmt"
	"time"

	"golang.org/x/crypto/chacha20poly1305"
)

func bench(name string, a cipher.AEAD) {
	buf := make([]byte, 16384)
	nonce := make([]byte, a.NonceSize())
	sealed := a.Seal(nil, nonce, buf, nil)
	out := make([]byte, 0, len(buf))
	n, t0 := 0, time.Now()
	for time.Since(t0) < 3*time.Second {
		if _, err := a.Open(out[:0], nonce, sealed, nil); err != nil {
			panic(err)
		}
		n += len(buf)
	}
	fmt.Printf("%-20s %6.1f MB/s = %6.1f Mbit/s\n", name, float64(n)/time.Since(t0).Seconds()/1e6, float64(n)*8/time.Since(t0).Seconds()/1e6)
}

func main() {
	k := make([]byte, 32)
	b, _ := aes.NewCipher(k[:16])
	g, _ := cipher.NewGCM(b)
	bench("AES-128-GCM", g)
	b2, _ := aes.NewCipher(k)
	g2, _ := cipher.NewGCM(b2)
	bench("AES-256-GCM", g2)
	c, _ := chacha20poly1305.New(k)
	bench("ChaCha20-Poly1305", c)
}
