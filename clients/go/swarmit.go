// Package swarmit provides a Go client for the Swarm-It sidecar.
//
// Example:
//
//	client := swarmit.NewClient("http://localhost:8080")
//	cert, err := client.Certify(ctx, "What is 2+2?", nil)
//	if err != nil {
//	    log.Fatal(err)
//	}
//
//	if cert.Allowed {
//	    response := myLLM(prompt)
//	    client.Validate(ctx, cert.ID, swarmit.TypeI, 0.9, false)
//	}
package swarmit

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// GateDecision represents the certification gate decision.
type GateDecision string

const (
	Execute  GateDecision = "EXECUTE"
	Repair   GateDecision = "REPAIR"
	Delegate GateDecision = "DELEGATE"
	Block    GateDecision = "BLOCK"
	Reject   GateDecision = "REJECT"
)

// ValidationType represents Type I-VI validation.
type ValidationType string

const (
	TypeI   ValidationType = "TYPE_I"
	TypeII  ValidationType = "TYPE_II"
	TypeIII ValidationType = "TYPE_III"
	TypeIV  ValidationType = "TYPE_IV"
	TypeV   ValidationType = "TYPE_V"
	TypeVI  ValidationType = "TYPE_VI"
)

// Certificate represents an RSCT certificate.
type Certificate struct {
	ID             string       `json:"id"`
	Timestamp      string       `json:"timestamp"`
	R              float64      `json:"R"`
	S              float64      `json:"S"`
	N              float64      `json:"N"`
	KappaGate      float64      `json:"kappa_gate"`
	Sigma          float64      `json:"sigma"`
	Decision       GateDecision `json:"decision"`
	GateReached    int          `json:"gate_reached"`
	Reason         string       `json:"reason"`
	Allowed        bool         `json:"allowed"`
	KappaH         *float64     `json:"kappa_H,omitempty"`
	KappaL         *float64     `json:"kappa_L,omitempty"`
	KappaInterface *float64     `json:"kappa_interface,omitempty"`
	WeakModality   *string      `json:"weak_modality,omitempty"`
	IsMultimodal   bool         `json:"is_multimodal"`
}

// CertifyOptions contains optional parameters for certification.
type CertifyOptions struct {
	ModelID  string `json:"model_id,omitempty"`
	Context  string `json:"context,omitempty"`
	SwarmID  string `json:"swarm_id,omitempty"`
	Policy   string `json:"policy,omitempty"`
}

// ValidateResponse is the response from validation.
type ValidateResponse struct {
	Recorded   bool                   `json:"recorded"`
	Adjustment map[string]interface{} `json:"adjustment,omitempty"`
}

// AuditOptions contains options for audit export.
type AuditOptions struct {
	StartTime string `json:"start_time,omitempty"`
	EndTime   string `json:"end_time,omitempty"`
	Format    string `json:"format,omitempty"`
	Limit     int    `json:"limit,omitempty"`
}

// AuditResponse is the response from audit export.
type AuditResponse struct {
	CertificateCount int                      `json:"certificate_count"`
	Format           string                   `json:"format"`
	Records          []map[string]interface{} `json:"records"`
}

// Client is the Swarm-It sidecar client.
type Client struct {
	baseURL    string
	httpClient *http.Client
}

// NewClient creates a new Swarm-It client.
func NewClient(baseURL string) *Client {
	return &Client{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// WithTimeout sets a custom timeout.
func (c *Client) WithTimeout(timeout time.Duration) *Client {
	c.httpClient.Timeout = timeout
	return c
}

// Certify requests RSCT certification for a prompt.
func (c *Client) Certify(ctx context.Context, prompt string, opts *CertifyOptions) (*Certificate, error) {
	body := map[string]interface{}{
		"prompt": prompt,
		"policy": "default",
	}

	if opts != nil {
		if opts.ModelID != "" {
			body["model_id"] = opts.ModelID
		}
		if opts.Context != "" {
			body["context"] = opts.Context
		}
		if opts.SwarmID != "" {
			body["swarm_id"] = opts.SwarmID
		}
		if opts.Policy != "" {
			body["policy"] = opts.Policy
		}
	}

	var cert Certificate
	if err := c.post(ctx, "/api/v1/certify", body, &cert); err != nil {
		return nil, err
	}

	return &cert, nil
}

// Validate submits post-execution validation feedback.
func (c *Client) Validate(ctx context.Context, certificateID string, validationType ValidationType, score float64, failed bool) (*ValidateResponse, error) {
	body := map[string]interface{}{
		"certificate_id":  certificateID,
		"validation_type": validationType,
		"score":           score,
		"failed":          failed,
	}

	var resp ValidateResponse
	if err := c.post(ctx, "/api/v1/validate", body, &resp); err != nil {
		return nil, err
	}

	return &resp, nil
}

// Audit exports certificates for compliance.
func (c *Client) Audit(ctx context.Context, opts *AuditOptions) (*AuditResponse, error) {
	body := map[string]interface{}{
		"format": "JSON",
		"limit":  100,
	}

	if opts != nil {
		if opts.Format != "" {
			body["format"] = opts.Format
		}
		if opts.Limit > 0 {
			body["limit"] = opts.Limit
		}
		if opts.StartTime != "" {
			body["start_time"] = opts.StartTime
		}
		if opts.EndTime != "" {
			body["end_time"] = opts.EndTime
		}
	}

	var resp AuditResponse
	if err := c.post(ctx, "/api/v1/audit", body, &resp); err != nil {
		return nil, err
	}

	return &resp, nil
}

// GetCertificate retrieves a certificate by ID.
func (c *Client) GetCertificate(ctx context.Context, certificateID string) (*Certificate, error) {
	var cert Certificate
	if err := c.get(ctx, "/api/v1/certificates/"+certificateID, &cert); err != nil {
		return nil, err
	}

	return &cert, nil
}

// Health checks if the sidecar is healthy.
func (c *Client) Health(ctx context.Context) bool {
	var resp map[string]interface{}
	if err := c.get(ctx, "/health", &resp); err != nil {
		return false
	}
	return true
}

func (c *Client) post(ctx context.Context, path string, body interface{}, result interface{}) error {
	jsonBody, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("marshal body: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+path, bytes.NewReader(jsonBody))
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
	}

	if err := json.NewDecoder(resp.Body).Decode(result); err != nil {
		return fmt.Errorf("decode response: %w", err)
	}

	return nil
}

func (c *Client) get(ctx context.Context, path string, result interface{}) error {
	req, err := http.NewRequestWithContext(ctx, "GET", c.baseURL+path, nil)
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
	}

	if err := json.NewDecoder(resp.Body).Decode(result); err != nil {
		return fmt.Errorf("decode response: %w", err)
	}

	return nil
}
