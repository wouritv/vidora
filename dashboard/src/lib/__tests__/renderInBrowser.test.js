import { beforeEach, describe, expect, it, vi } from 'vitest';

const renderMediaOnWebMock = vi.fn();
const toBrowserSafeMediaUrlMock = vi.fn();

vi.mock('@remotion/web-renderer', () => ({
    renderMediaOnWeb: renderMediaOnWebMock,
}));

vi.mock('../../remotion/compositions/ShortVideo', () => ({
    ShortVideo: function ShortVideo() {
        return null;
    },
}));

vi.mock('../clips', () => ({
    toBrowserSafeMediaUrl: toBrowserSafeMediaUrlMock,
}));

describe('renderInBrowser', () => {
    let originalCreateObjectUrl;

    beforeEach(() => {
        vi.clearAllMocks();
        originalCreateObjectUrl = URL.createObjectURL;
    });

    it('builds remotion render params and returns object URL', async () => {
        const blob = new Blob(['x'], { type: 'video/mp4' });
        const getBlob = vi.fn().mockResolvedValue(blob);

        toBrowserSafeMediaUrlMock.mockReturnValue('https://safe.example/video.mp4');
        renderMediaOnWebMock.mockResolvedValue({ getBlob });

        URL.createObjectURL = vi.fn().mockReturnValue('blob:rendered-video');

        const { renderInBrowser } = await import('../renderInBrowser');

        const onProgress = vi.fn();
        const controller = new AbortController();
        const output = await renderInBrowser({
            videoUrl: 'https://raw.example/video.mp4',
            durationInSeconds: 12.2,
            subtitles: { enabled: true },
            hook: { text: 'Hook' },
            effects: { contrast: 1.1 },
            onProgress,
            signal: controller.signal,
        });

        expect(output).toBe('blob:rendered-video');
        expect(toBrowserSafeMediaUrlMock).toHaveBeenCalledWith('https://raw.example/video.mp4');
        expect(renderMediaOnWebMock).toHaveBeenCalledTimes(1);

        const params = renderMediaOnWebMock.mock.calls[0][0];
        expect(params.composition.durationInFrames).toBe(366);
        expect(params.composition.fps).toBe(30);
        expect(params.inputProps.videoUrl).toBe('https://safe.example/video.mp4');
        expect(params.inputProps.subtitles).toEqual({ enabled: true });
        expect(params.signal).toBe(controller.signal);

        params.onProgress({ progress: 0.42 });
        expect(onProgress).toHaveBeenCalledWith(0.42);
        expect(getBlob).toHaveBeenCalledTimes(1);

        URL.createObjectURL = originalCreateObjectUrl;
    });

    it('omits progress callback when onProgress is not provided', async () => {
        const blob = new Blob(['x'], { type: 'video/mp4' });
        renderMediaOnWebMock.mockResolvedValue({ getBlob: vi.fn().mockResolvedValue(blob) });
        toBrowserSafeMediaUrlMock.mockReturnValue('https://safe.example/video.mp4');
        URL.createObjectURL = vi.fn().mockReturnValue('blob:video-no-progress');

        const { renderInBrowser } = await import('../renderInBrowser');
        await renderInBrowser({ videoUrl: 'https://raw.example/video.mp4' });

        const params = renderMediaOnWebMock.mock.calls[0][0];
        expect(params.onProgress).toBeUndefined();
        URL.createObjectURL = originalCreateObjectUrl;
    });
});


