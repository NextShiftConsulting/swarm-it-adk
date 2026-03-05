/**
 * Swarm-It TypeScript Example
 *
 * Demonstrates RSCT certification flow with the Swarm-It sidecar.
 *
 * Run the sidecar first:
 *   cd swarm-it/sidecar && USE_YRSN=1 uvicorn main:app --port 8080
 *
 * Then run this example:
 *   cd swarm-it/clients/typescript
 *   npx ts-node examples/example.ts
 */

import { SwarmIt, ValidationType, GateDecision } from '../src/index';

async function main() {
  // Initialize client
  const swarm = new SwarmIt({ url: 'http://localhost:8080' });

  // Check health
  const healthy = await swarm.health();
  if (!healthy) {
    console.error('Sidecar is not healthy - start it with: cd sidecar && uvicorn main:app --port 8080');
    process.exit(1);
  }
  console.log('✓ Sidecar is healthy\n');

  // Example 1: Simple certification
  console.log('--- Example 1: Simple Certification ---');
  const cert1 = await swarm.certify('What is the capital of France?');

  console.log(`Certificate ID: ${cert1.id}`);
  console.log(`RSN Scores: R=${cert1.R.toFixed(3)}, S=${cert1.S.toFixed(3)}, N=${cert1.N.toFixed(3)}`);
  console.log(`Kappa Gate: ${cert1.kappa_gate.toFixed(3)}`);
  console.log(`Decision: ${cert1.decision} (Allowed: ${cert1.allowed})`);
  console.log(`Reason: ${cert1.reason}\n`);

  // Example 2: Certification with context
  console.log('--- Example 2: Certification with Context ---');
  const cert2 = await swarm.certify('Summarize the key findings', {
    context: 'The study found that participants who exercised regularly showed 30% improvement in cognitive function.',
    model_id: 'gpt-4',
    policy: 'strict',
  });

  console.log(`Certificate ID: ${cert2.id}`);
  console.log(`Decision: ${cert2.decision}`);
  console.log(`Gate Reached: ${cert2.gate_reached}\n`);

  // Example 3: Full workflow with validation feedback
  console.log('--- Example 3: Full Workflow ---');
  const prompt = 'Explain quantum entanglement in simple terms';

  // Pre-execution: Certify
  const cert3 = await swarm.certify(prompt);
  console.log(`Pre-execution gate: ${cert3.decision}`);

  if (cert3.allowed) {
    // Execute LLM call (simulated)
    console.log('Executing LLM call...');
    // const response = await myLLM(prompt);

    // Post-execution: Validate (Type I = Groundedness)
    const validateResp = await swarm.validate(cert3.id, ValidationType.TYPE_I, 0.92, false);
    console.log(`Validation recorded: ${validateResp.recorded}`);

    if (validateResp.adjustment) {
      console.log(`Threshold adjustment: ${JSON.stringify(validateResp.adjustment)}`);
    }
  } else {
    console.log(`Blocked: ${cert3.reason}`);
  }
  console.log('');

  // Example 4: Audit export
  console.log('--- Example 4: Audit Export ---');
  const auditResp = await swarm.audit({ format: 'JSON', limit: 5 });
  console.log(`Exported ${auditResp.certificate_count} certificates\n`);

  // Example 5: Retrieve certificate by ID
  console.log('--- Example 5: Get Certificate ---');
  const retrieved = await swarm.getCertificate(cert1.id);
  console.log(`Retrieved: ${retrieved.id} (R=${retrieved.R.toFixed(3)})\n`);

  // Example 6: Get statistics
  console.log('--- Example 6: Statistics ---');
  const stats = await swarm.statistics();
  console.log(`Total certificates: ${stats.total_certificates}`);
  console.log(`Thresholds: ${JSON.stringify(stats.thresholds)}\n`);

  console.log('✓ All examples completed successfully');
}

// Run
main().catch((err) => {
  console.error('Error:', err);
  process.exit(1);
});
