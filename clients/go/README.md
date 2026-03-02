# Go Client

Go client for the Swarm‑It sidecar (transport only).

## Use

```go
package main

import (
  "context"
  "log"

  swarmit "github.com/NextShiftConsulting/swarm-it/clients/go"
)

func main() {
  ctx := context.Background()
  client := swarmit.NewClient("http://localhost:8080")

  cert, err := client.Certify(ctx, "What is 2+2?", nil)
  if err != nil {
    log.Fatal(err)
  }

  if cert.Allowed {
    // call your model
  }
}
```
