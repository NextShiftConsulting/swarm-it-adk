//! Swarm-It Rust Client
//!
//! Thin client for the Swarm-It sidecar.
//!
//! # Example
//!
//! ```no_run
//! use swarmit::{SwarmIt, ValidationType};
//!
//! #[tokio::main]
//! async fn main() -> Result<(), swarmit::Error> {
//!     let client = SwarmIt::new("http://localhost:8080");
//!     let cert = client.certify("What is 2+2?", None).await?;
//!
//!     if cert.allowed {
//!         // let response = my_llm(&prompt).await;
//!         client.validate(&cert.id, ValidationType::TypeI, 0.9, false).await?;
//!     }
//!
//!     Ok(())
//! }
//! ```

use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::time::Duration;

/// Error type for Swarm-It operations.
#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("HTTP error: {0}")]
    Http(#[from] reqwest::Error),

    #[error("API error: {0}")]
    Api(String),

    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),
}

/// Gate decision from certification.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "UPPERCASE")]
pub enum GateDecision {
    Execute,
    Repair,
    Delegate,
    Block,
    Reject,
}

/// Validation type (Type I-VI).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ValidationType {
    #[serde(rename = "TYPE_I")]
    TypeI,
    #[serde(rename = "TYPE_II")]
    TypeII,
    #[serde(rename = "TYPE_III")]
    TypeIII,
    #[serde(rename = "TYPE_IV")]
    TypeIV,
    #[serde(rename = "TYPE_V")]
    TypeV,
    #[serde(rename = "TYPE_VI")]
    TypeVI,
}

/// RSCT Certificate.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Certificate {
    pub id: String,
    pub timestamp: String,
    #[serde(rename = "R")]
    pub r: f64,
    #[serde(rename = "S")]
    pub s: f64,
    #[serde(rename = "N")]
    pub n: f64,
    pub kappa_gate: f64,
    pub sigma: f64,
    pub decision: GateDecision,
    pub gate_reached: i32,
    pub reason: String,
    pub allowed: bool,
    #[serde(rename = "kappa_H")]
    pub kappa_h: Option<f64>,
    #[serde(rename = "kappa_L")]
    pub kappa_l: Option<f64>,
    pub kappa_interface: Option<f64>,
    pub weak_modality: Option<String>,
    pub is_multimodal: bool,
}

/// Options for certification.
#[derive(Debug, Clone, Default, Serialize)]
pub struct CertifyOptions {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub context: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub swarm_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub policy: Option<String>,
}

/// Response from validation.
#[derive(Debug, Clone, Deserialize)]
pub struct ValidateResponse {
    pub recorded: bool,
    pub adjustment: Option<serde_json::Value>,
}

/// Options for audit export.
#[derive(Debug, Clone, Default, Serialize)]
pub struct AuditOptions {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub start_time: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub end_time: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub format: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub limit: Option<i32>,
}

/// Response from audit export.
#[derive(Debug, Clone, Deserialize)]
pub struct AuditResponse {
    pub certificate_count: i32,
    pub format: String,
    pub records: Vec<serde_json::Value>,
}

/// Swarm-It client.
pub struct SwarmIt {
    base_url: String,
    client: Client,
}

impl SwarmIt {
    /// Create a new Swarm-It client.
    pub fn new(base_url: &str) -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(30))
            .build()
            .expect("Failed to create HTTP client");

        Self {
            base_url: base_url.trim_end_matches('/').to_string(),
            client,
        }
    }

    /// Create a client with custom timeout.
    pub fn with_timeout(base_url: &str, timeout: Duration) -> Self {
        let client = Client::builder()
            .timeout(timeout)
            .build()
            .expect("Failed to create HTTP client");

        Self {
            base_url: base_url.trim_end_matches('/').to_string(),
            client,
        }
    }

    /// Certify a prompt for RSCT compliance.
    pub async fn certify(
        &self,
        prompt: &str,
        options: Option<CertifyOptions>,
    ) -> Result<Certificate, Error> {
        #[derive(Serialize)]
        struct Request {
            prompt: String,
            #[serde(flatten)]
            options: CertifyOptions,
        }

        let request = Request {
            prompt: prompt.to_string(),
            options: options.unwrap_or_default(),
        };

        let response = self
            .client
            .post(format!("{}/api/v1/certify", self.base_url))
            .json(&request)
            .send()
            .await?;

        if !response.status().is_success() {
            let text = response.text().await.unwrap_or_default();
            return Err(Error::Api(text));
        }

        Ok(response.json().await?)
    }

    /// Submit post-execution validation feedback.
    pub async fn validate(
        &self,
        certificate_id: &str,
        validation_type: ValidationType,
        score: f64,
        failed: bool,
    ) -> Result<ValidateResponse, Error> {
        #[derive(Serialize)]
        struct Request {
            certificate_id: String,
            validation_type: ValidationType,
            score: f64,
            failed: bool,
        }

        let request = Request {
            certificate_id: certificate_id.to_string(),
            validation_type,
            score,
            failed,
        };

        let response = self
            .client
            .post(format!("{}/api/v1/validate", self.base_url))
            .json(&request)
            .send()
            .await?;

        if !response.status().is_success() {
            let text = response.text().await.unwrap_or_default();
            return Err(Error::Api(text));
        }

        Ok(response.json().await?)
    }

    /// Export certificates for compliance audit.
    pub async fn audit(&self, options: Option<AuditOptions>) -> Result<AuditResponse, Error> {
        let request = options.unwrap_or_default();

        let response = self
            .client
            .post(format!("{}/api/v1/audit", self.base_url))
            .json(&request)
            .send()
            .await?;

        if !response.status().is_success() {
            let text = response.text().await.unwrap_or_default();
            return Err(Error::Api(text));
        }

        Ok(response.json().await?)
    }

    /// Get a certificate by ID.
    pub async fn get_certificate(&self, certificate_id: &str) -> Result<Certificate, Error> {
        let response = self
            .client
            .get(format!(
                "{}/api/v1/certificates/{}",
                self.base_url, certificate_id
            ))
            .send()
            .await?;

        if !response.status().is_success() {
            let text = response.text().await.unwrap_or_default();
            return Err(Error::Api(text));
        }

        Ok(response.json().await?)
    }

    /// Check if sidecar is healthy.
    pub async fn health(&self) -> bool {
        self.client
            .get(format!("{}/health", self.base_url))
            .send()
            .await
            .map(|r| r.status().is_success())
            .unwrap_or(false)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gate_decision_serialization() {
        let decision = GateDecision::Execute;
        let json = serde_json::to_string(&decision).unwrap();
        assert_eq!(json, "\"EXECUTE\"");
    }
}
