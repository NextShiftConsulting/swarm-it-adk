//! Swarm-It Rust Example
//!
//! Demonstrates RSCT certification flow with the Swarm-It sidecar.
//!
//! Run the sidecar first:
//!   cd swarm-it/sidecar && USE_YRSN=1 uvicorn main:app --port 8080
//!
//! Then run this example:
//!   cd swarm-it/clients/rust && cargo run --example main

use swarmit::{AuditOptions, CertifyOptions, SwarmIt, ValidationType};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize client
    let client = SwarmIt::new("http://localhost:8080");

    // Check health
    if !client.health().await {
        eprintln!("Sidecar is not healthy - start it with: cd sidecar && uvicorn main:app --port 8080");
        std::process::exit(1);
    }
    println!("✓ Sidecar is healthy\n");

    // Example 1: Simple certification
    println!("--- Example 1: Simple Certification ---");
    let cert1 = client.certify("What is the capital of France?", None).await?;

    println!("Certificate ID: {}", cert1.id);
    println!("RSN Scores: R={:.3}, S={:.3}, N={:.3}", cert1.r, cert1.s, cert1.n);
    println!("Kappa Gate: {:.3}", cert1.kappa_gate);
    println!("Decision: {:?} (Allowed: {})", cert1.decision, cert1.allowed);
    println!("Reason: {}\n", cert1.reason);

    // Example 2: Certification with context
    println!("--- Example 2: Certification with Context ---");
    let cert2 = client
        .certify(
            "Summarize the key findings",
            Some(CertifyOptions {
                context: Some("The study found that participants who exercised regularly showed 30% improvement in cognitive function.".to_string()),
                model_id: Some("gpt-4".to_string()),
                policy: Some("strict".to_string()),
                ..Default::default()
            }),
        )
        .await?;

    println!("Certificate ID: {}", cert2.id);
    println!("Decision: {:?}", cert2.decision);
    println!("Gate Reached: {}\n", cert2.gate_reached);

    // Example 3: Full workflow with validation feedback
    println!("--- Example 3: Full Workflow ---");
    let prompt = "Explain quantum entanglement in simple terms";

    // Pre-execution: Certify
    let cert3 = client.certify(prompt, None).await?;
    println!("Pre-execution gate: {:?}", cert3.decision);

    if cert3.allowed {
        // Execute LLM call (simulated)
        println!("Executing LLM call...");
        // let response = my_llm(prompt).await;

        // Post-execution: Validate (Type I = Groundedness)
        let validate_resp = client
            .validate(&cert3.id, ValidationType::TypeI, 0.92, false)
            .await?;
        println!("Validation recorded: {}", validate_resp.recorded);

        if let Some(adjustment) = validate_resp.adjustment {
            println!("Threshold adjustment: {}", adjustment);
        }
    } else {
        println!("Blocked: {}", cert3.reason);
    }
    println!();

    // Example 4: Audit export
    println!("--- Example 4: Audit Export ---");
    let audit_resp = client
        .audit(Some(AuditOptions {
            format: Some("JSON".to_string()),
            limit: Some(5),
            ..Default::default()
        }))
        .await?;
    println!("Exported {} certificates\n", audit_resp.certificate_count);

    // Example 5: Retrieve certificate by ID
    println!("--- Example 5: Get Certificate ---");
    let retrieved = client.get_certificate(&cert1.id).await?;
    println!("Retrieved: {} (R={:.3})\n", retrieved.id, retrieved.r);

    println!("✓ All examples completed successfully");

    Ok(())
}
