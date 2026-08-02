import { describe, it, expect, beforeEach } from 'vitest';
import { encrypt, decrypt } from '../encryption';

describe('encryption', () => {
    describe('encrypt', () => {
        it('returns empty string for falsy input', () => {
            expect(encrypt('')).toBe('');
            expect(encrypt(null)).toBe('');
            expect(encrypt(undefined)).toBe('');
        });

        it('returns a string prefixed with ENC:', () => {
            expect(encrypt('my-api-key')).toMatch(/^ENC:/);
        });

        it('produces different ciphertext for different inputs', () => {
            expect(encrypt('key-a')).not.toBe(encrypt('key-b'));
        });

        it('is deterministic (same input → same output)', () => {
            expect(encrypt('stable')).toBe(encrypt('stable'));
        });
    });

    describe('decrypt', () => {
        it('returns empty string for falsy input', () => {
            expect(decrypt('')).toBe('');
            expect(decrypt(null)).toBe('');
            expect(decrypt(undefined)).toBe('');
        });

        it('returns the original value when not prefixed with ENC:', () => {
            expect(decrypt('plain-text')).toBe('plain-text');
            expect(decrypt('another-value')).toBe('another-value');
        });

        it('returns empty string for a malformed ENC: payload', () => {
            expect(decrypt('ENC:!!!not-base64!!!')).toBe('');
        });

        it('round-trips correctly (decrypt(encrypt(x)) === x)', () => {
            const samples = ['hello', 'my-secret-key-123', 'ユニコード', '!@#$%^&*()'];
            for (const sample of samples) {
                expect(decrypt(encrypt(sample))).toBe(sample);
            }
        });
    });
});

