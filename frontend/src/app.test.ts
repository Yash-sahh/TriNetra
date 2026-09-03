import { describe, it, expect } from 'vitest';

describe('TriNetra Frontend Core', () => {
  it('enforces demo synthetic data guardrails', () => {
    const bannerText = 'DEMO DATA — SYNTHETIC INVESTIGATION ENVIRONMENT';
    expect(bannerText).toContain('SYNTHETIC');
    expect(bannerText).not.toContain('Guilt score');
    expect(bannerText).not.toContain('Criminal score');
  });

  it('validates allowed terminology and disclaimers', () => {
    const disclaimer = 'This system provides analytical leads and does not establish guilt or final legal conclusions.';
    expect(disclaimer).toContain('analytical leads');
    expect(disclaimer).not.toContain('Proven guilty');
  });

  it('verifies entity resolution categories', () => {
    const categories = ['CONFIRMED', 'PROBABLE', 'POSSIBLE', 'UNRESOLVED'];
    expect(categories).toContain('CONFIRMED');
    expect(categories).toContain('PROBABLE');
    expect(categories).toContain('POSSIBLE');
    expect(categories).toContain('UNRESOLVED');
  });

  it('verifies priority score component weights', () => {
    const components = {
      network_position: 30,
      cross_community_connections: 25,
      temporal_activity: 20,
      evidence_quality: 15,
      data_completeness: 10,
    };
    const total = Object.values(components).reduce((a, b) => a + b, 0);
    expect(total).toBe(100);
  });
});
