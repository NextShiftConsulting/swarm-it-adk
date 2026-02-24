/**
 * Swarm-It TypeScript Client
 *
 * Thin client for the Swarm-It sidecar.
 *
 * @example
 * ```typescript
 * import { SwarmIt } from '@swarmit/client';
 *
 * const swarm = new SwarmIt({ url: 'http://localhost:8080' });
 * const cert = await swarm.certify('What is 2+2?');
 *
 * if (cert.allowed) {
 *   const response = await myLLM(prompt);
 *   await swarm.validate(cert.id, 'TYPE_I', 0.9);
 * }
 * ```
 */

export enum GateDecision {
  EXECUTE = 'EXECUTE',
  REPAIR = 'REPAIR',
  DELEGATE = 'DELEGATE',
  BLOCK = 'BLOCK',
  REJECT = 'REJECT',
}

export enum ValidationType {
  TYPE_I = 'TYPE_I',
  TYPE_II = 'TYPE_II',
  TYPE_III = 'TYPE_III',
  TYPE_IV = 'TYPE_IV',
  TYPE_V = 'TYPE_V',
  TYPE_VI = 'TYPE_VI',
}

export interface Certificate {
  id: string;
  timestamp: string;
  R: number;
  S: number;
  N: number;
  kappa_gate: number;
  sigma: number;
  decision: GateDecision;
  gate_reached: number;
  reason: string;
  allowed: boolean;
  kappa_H?: number;
  kappa_L?: number;
  kappa_interface?: number;
  weak_modality?: string;
  is_multimodal: boolean;
}

export interface CertifyOptions {
  model_id?: string;
  context?: string;
  swarm_id?: string;
  policy?: string;
}

export interface ValidateResponse {
  recorded: boolean;
  adjustment?: {
    type: string;
    failure_rate: number;
    threshold: number;
    recommendation: string;
  };
}

export interface AuditOptions {
  start_time?: string;
  end_time?: string;
  format?: 'JSON' | 'SR11-7' | 'CSV';
  limit?: number;
}

export interface AuditResponse {
  certificate_count: number;
  format: string;
  records: Record<string, unknown>[];
}

export interface SwarmItConfig {
  url?: string;
  timeout?: number;
}

export class SwarmIt {
  private baseUrl: string;
  private timeout: number;

  constructor(config: SwarmItConfig = {}) {
    this.baseUrl = (config.url || 'http://localhost:8080').replace(/\/$/, '');
    this.timeout = config.timeout || 30000;
  }

  /**
   * Certify a prompt for RSCT compliance.
   */
  async certify(prompt: string, options: CertifyOptions = {}): Promise<Certificate> {
    const response = await this.fetch('/api/v1/certify', {
      method: 'POST',
      body: JSON.stringify({
        prompt,
        model_id: options.model_id,
        context: options.context,
        swarm_id: options.swarm_id,
        policy: options.policy || 'default',
      }),
    });

    return response as Certificate;
  }

  /**
   * Submit post-execution validation feedback.
   */
  async validate(
    certificateId: string,
    validationType: ValidationType | string,
    score: number,
    failed: boolean = false
  ): Promise<ValidateResponse> {
    const response = await this.fetch('/api/v1/validate', {
      method: 'POST',
      body: JSON.stringify({
        certificate_id: certificateId,
        validation_type: validationType,
        score,
        failed,
      }),
    });

    return response as ValidateResponse;
  }

  /**
   * Export certificates for compliance audit.
   */
  async audit(options: AuditOptions = {}): Promise<AuditResponse> {
    const response = await this.fetch('/api/v1/audit', {
      method: 'POST',
      body: JSON.stringify({
        format: options.format || 'JSON',
        limit: options.limit || 100,
        start_time: options.start_time,
        end_time: options.end_time,
      }),
    });

    return response as AuditResponse;
  }

  /**
   * Get a certificate by ID.
   */
  async getCertificate(certificateId: string): Promise<Certificate> {
    const response = await this.fetch(`/api/v1/certificates/${certificateId}`, {
      method: 'GET',
    });

    return response as Certificate;
  }

  /**
   * Get sidecar statistics.
   */
  async statistics(): Promise<Record<string, unknown>> {
    return this.fetch('/api/v1/statistics', { method: 'GET' });
  }

  /**
   * Check if sidecar is healthy.
   */
  async health(): Promise<boolean> {
    try {
      await this.fetch('/health', { method: 'GET' });
      return true;
    } catch {
      return false;
    }
  }

  private async fetch(path: string, options: RequestInit): Promise<Record<string, unknown>> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await globalThis.fetch(`${this.baseUrl}${path}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        signal: controller.signal,
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `HTTP ${response.status}`);
      }

      return response.json();
    } finally {
      clearTimeout(timeoutId);
    }
  }
}

export default SwarmIt;
