# Rust Client

Rust client for the Swarm‑It sidecar (transport only).

## Use

```rust
use swarmit::{SwarmIt, ValidationType};

#[tokio::main]
async fn main() -> Result<(), swarmit::Error> {
    let client = SwarmIt::new("http://localhost:8080");
    let cert = client.certify("What is 2+2?", None).await?;

    if cert.allowed {
        client.validate(&cert.id, ValidationType::TypeI, 0.9, false).await?;
    }

    Ok(())
}
```
