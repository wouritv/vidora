import { describe, it, expect } from 'vitest';
import { normalizeFrontendStatus, statusLabel, statusClass, statusMeta } from '../status';

describe('normalizeFrontendStatus', () => {
    it('maps "completed" → "complete"', () => {
        expect(normalizeFrontendStatus('completed')).toBe('complete');
    });

    it('maps "failed" → "error"', () => {
        expect(normalizeFrontendStatus('failed')).toBe('error');
    });

    it('passes through unknown statuses unchanged', () => {
        expect(normalizeFrontendStatus('processing')).toBe('processing');
        expect(normalizeFrontendStatus('pending')).toBe('pending');
        expect(normalizeFrontendStatus('')).toBe('');
    });
});

describe('statusLabel', () => {
    it('returns "Terminé" for termine', () => {
        expect(statusLabel('termine')).toBe('Terminé');
    });

    it('returns "En cours" for en_cours', () => {
        expect(statusLabel('en_cours')).toBe('En cours');
    });

    it('returns "Échec" for echec', () => {
        expect(statusLabel('echec')).toBe('Échec');
    });

    it('returns "-" for undefined/empty', () => {
        expect(statusLabel(undefined)).toBe('-');
        expect(statusLabel('')).toBe('-');
    });

    it('passes through unrecognized statuses', () => {
        expect(statusLabel('custom')).toBe('custom');
    });
});

describe('statusClass', () => {
    it('returns green classes for termine', () => {
        expect(statusClass('termine')).toContain('green');
    });

    it('returns blue classes for en_cours', () => {
        expect(statusClass('en_cours')).toContain('blue');
    });

    it('returns red classes for echec', () => {
        expect(statusClass('echec')).toContain('red');
    });

    it('returns a neutral fallback class for unknown status', () => {
        const cls = statusClass('unknown');
        expect(cls).not.toContain('green');
        expect(cls).not.toContain('red');
        expect(cls).not.toContain('blue');
    });
});

describe('statusMeta', () => {
    it('returns correct label for processing', () => {
        expect(statusMeta('processing').label).toBe('En cours');
    });

    it('returns correct label for complete', () => {
        expect(statusMeta('complete').label).toBe('Terminé');
    });

    it('returns "Erreur" label for unknown status', () => {
        expect(statusMeta('anything-else').label).toBe('Erreur');
    });

    it('always includes a className string', () => {
        ['processing', 'complete', 'error', 'unknown'].forEach((s) => {
            expect(typeof statusMeta(s).className).toBe('string');
        });
    });

    it('always includes an icon reference', () => {
        ['processing', 'complete', 'error'].forEach((s) => {
            expect(statusMeta(s).icon).toBeDefined();
        });
    });
});

