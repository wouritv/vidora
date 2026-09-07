import { beforeEach, describe, expect, it, vi } from 'vitest';

const createClientMock = vi.fn();

vi.mock('@supabase/supabase-js', () => ({
    createClient: createClientMock,
}));

describe('getSupabaseBrowserClient', () => {
    beforeEach(() => {
        vi.resetModules();
        vi.clearAllMocks();
        vi.unstubAllEnvs();
    });

    it('throws when required env vars are missing', async () => {
        vi.stubEnv('VITE_SUPABASE_URL', '');
        vi.stubEnv('VITE_SUPABASE_ANON_KEY', '');

        const { getSupabaseBrowserClient } = await import('../supabase-browser');

        expect(() => getSupabaseBrowserClient()).toThrow(
            'Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY',
        );
    });

    it('creates and memoizes supabase client with expected auth options', async () => {
        vi.stubEnv('VITE_SUPABASE_URL', 'https://supabase.example.co');
        vi.stubEnv('VITE_SUPABASE_ANON_KEY', 'anon-key');

        const fakeClient = { id: 'client-1' };
        createClientMock.mockReturnValue(fakeClient);

        const { getSupabaseBrowserClient } = await import('../supabase-browser');

        const first = getSupabaseBrowserClient();
        const second = getSupabaseBrowserClient();

        expect(first).toBe(fakeClient);
        expect(second).toBe(fakeClient);
        expect(createClientMock).toHaveBeenCalledTimes(1);
        expect(createClientMock).toHaveBeenCalledWith(
            'https://supabase.example.co',
            'anon-key',
            {
                auth: {
                    persistSession: true,
                    autoRefreshToken: true,
                    detectSessionInUrl: true,
                },
            },
        );
    });
});

