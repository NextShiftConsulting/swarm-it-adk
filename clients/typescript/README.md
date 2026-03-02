# TypeScript Client

TypeScript client for the Swarm‑It sidecar (transport only).

## Build

```bash
npm install
npm run build
```

## Use

```ts
import { SwarmIt } from "@swarmit/client";

const swarm = new SwarmIt({ url: "http://localhost:8080" });
const cert = await swarm.certify("What is 2+2?");

if (cert.allowed) {
  // call your model
}
```
