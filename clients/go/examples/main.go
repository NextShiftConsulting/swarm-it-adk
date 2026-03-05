// Swarm-It Go Example
//
// Demonstrates RSCT certification flow with the Swarm-It sidecar.
//
// Run the sidecar first:
//   cd swarm-it/sidecar && USE_YRSN=1 uvicorn main:app --port 8080
//
// Then run this example:
//   cd swarm-it/clients/go/examples && go run main.go
package main

import (
	"context"
	"fmt"
	"log"
	"time"

	swarmit "github.com/NextShiftConsulting/swarm-it/clients/go"
)

func main() {
	// Initialize client
	client := swarmit.NewClient("http://localhost:8080")

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// Check health
	if !client.Health(ctx) {
		log.Fatal("Sidecar is not healthy - start it with: cd sidecar && uvicorn main:app --port 8080")
	}
	fmt.Println("✓ Sidecar is healthy")

	// Example 1: Simple certification
	fmt.Println("\n--- Example 1: Simple Certification ---")
	cert, err := client.Certify(ctx, "What is the capital of France?", nil)
	if err != nil {
		log.Fatalf("Certify failed: %v", err)
	}

	fmt.Printf("Certificate ID: %s\n", cert.ID)
	fmt.Printf("RSN Scores: R=%.3f, S=%.3f, N=%.3f\n", cert.R, cert.S, cert.N)
	fmt.Printf("Kappa Gate: %.3f\n", cert.KappaGate)
	fmt.Printf("Decision: %s (Allowed: %v)\n", cert.Decision, cert.Allowed)
	fmt.Printf("Reason: %s\n", cert.Reason)

	// Example 2: Certification with context
	fmt.Println("\n--- Example 2: Certification with Context ---")
	cert2, err := client.Certify(ctx, "Summarize the key findings", &swarmit.CertifyOptions{
		Context: "The study found that participants who exercised regularly showed 30% improvement in cognitive function.",
		ModelID: "gpt-4",
		Policy:  "strict",
	})
	if err != nil {
		log.Fatalf("Certify failed: %v", err)
	}

	fmt.Printf("Certificate ID: %s\n", cert2.ID)
	fmt.Printf("Decision: %s\n", cert2.Decision)
	fmt.Printf("Gate Reached: %d\n", cert2.GateReached)

	// Example 3: Full workflow with validation feedback
	fmt.Println("\n--- Example 3: Full Workflow ---")
	prompt := "Explain quantum entanglement in simple terms"

	// Pre-execution: Certify
	cert3, err := client.Certify(ctx, prompt, nil)
	if err != nil {
		log.Fatalf("Certify failed: %v", err)
	}
	fmt.Printf("Pre-execution gate: %s\n", cert3.Decision)

	if cert3.Allowed {
		// Execute LLM call (simulated)
		fmt.Println("Executing LLM call...")
		// response := myLLM(prompt)

		// Post-execution: Validate
		validateResp, err := client.Validate(ctx, cert3.ID, swarmit.TypeI, 0.92, false)
		if err != nil {
			log.Fatalf("Validate failed: %v", err)
		}
		fmt.Printf("Validation recorded: %v\n", validateResp.Recorded)

		if validateResp.Adjustment != nil {
			fmt.Printf("Threshold adjustment: %v\n", validateResp.Adjustment)
		}
	} else {
		fmt.Printf("Blocked: %s\n", cert3.Reason)
	}

	// Example 4: Audit export
	fmt.Println("\n--- Example 4: Audit Export ---")
	auditResp, err := client.Audit(ctx, &swarmit.AuditOptions{
		Format: "JSON",
		Limit:  5,
	})
	if err != nil {
		log.Fatalf("Audit failed: %v", err)
	}
	fmt.Printf("Exported %d certificates\n", auditResp.CertificateCount)

	// Example 5: Retrieve certificate by ID
	fmt.Println("\n--- Example 5: Get Certificate ---")
	retrieved, err := client.GetCertificate(ctx, cert.ID)
	if err != nil {
		log.Fatalf("GetCertificate failed: %v", err)
	}
	fmt.Printf("Retrieved: %s (R=%.3f)\n", retrieved.ID, retrieved.R)

	fmt.Println("\n✓ All examples completed successfully")
}
