// Standalone Swarm-It Go Example (no module dependencies)
//
// Run with: go run standalone.go
//
// Requires sidecar running:
//   cd swarm-it/sidecar && USE_YRSN=1 uvicorn main:app --port 8080

//go:build ignore

package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

const baseURL = "http://localhost:8080"

type Certificate struct {
	ID        string  `json:"id"`
	R         float64 `json:"R"`
	S         float64 `json:"S"`
	N         float64 `json:"N"`
	KappaGate float64 `json:"kappa_gate"`
	Decision  string  `json:"decision"`
	Allowed   bool    `json:"allowed"`
	Reason    string  `json:"reason"`
}

func certify(prompt string) (*Certificate, error) {
	body, _ := json.Marshal(map[string]interface{}{
		"prompt": prompt,
		"policy": "default",
	})

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	req, _ := http.NewRequestWithContext(ctx, "POST", baseURL+"/api/v1/certify", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
	}

	var cert Certificate
	json.NewDecoder(resp.Body).Decode(&cert)
	return &cert, nil
}

func main() {
	fmt.Println("Swarm-It Go Standalone Example")
	fmt.Println("================================\n")

	// Test 1: Simple query
	cert, err := certify("What is 2 + 2?")
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		fmt.Println("\nMake sure sidecar is running:")
		fmt.Println("  cd swarm-it/sidecar && uvicorn main:app --port 8080")
		return
	}

	fmt.Printf("Certificate: %s\n", cert.ID)
	fmt.Printf("RSN: R=%.3f, S=%.3f, N=%.3f\n", cert.R, cert.S, cert.N)
	fmt.Printf("Kappa: %.3f\n", cert.KappaGate)
	fmt.Printf("Decision: %s (Allowed: %v)\n", cert.Decision, cert.Allowed)
	fmt.Printf("Reason: %s\n", cert.Reason)

	// Test 2: Complex query
	fmt.Println("\n--- Test 2: Complex Query ---")
	cert2, err := certify("Explain the implications of quantum entanglement for cryptographic key distribution")
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		return
	}

	fmt.Printf("Certificate: %s\n", cert2.ID)
	fmt.Printf("RSN: R=%.3f, S=%.3f, N=%.3f\n", cert2.R, cert2.S, cert2.N)
	fmt.Printf("Decision: %s\n", cert2.Decision)

	fmt.Println("\n✓ Done")
}
