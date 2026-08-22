import React, { forwardRef, useImperativeHandle, useMemo, useRef } from 'react';
import { Player } from '@remotion/player';
import { ShortVideo } from '../remotion/compositions/ShortVideo';
import { toBrowserSafeMediaUrl } from '../lib/clips';

/**
 * Wraps Remotion's Player component for real-time preview in modals.
 * Accepts the same ShortVideoProps interface as the Remotion composition.
 *
 * @param {object} props
 * @param {string} props.videoUrl - URL to the base clip video
 * @param {number} props.durationInSeconds - Video duration in seconds
 * @param {object|null} props.subtitles - SubtitleConfig or null
 * @param {object|null} props.hook - HookConfig or null
 * @param {object|null} props.effects - EffectsConfig or null
 * @param {string} [props.className] - Additional CSS classes
 */
const RemotionPreview = forwardRef(function RemotionPreview({
    videoUrl,
    durationInSeconds = 30,
    subtitles = null,
    hook = null,
    effects = null,
    className = '',
}, ref) {
    const fps = 30;
    const playerRef = useRef(null);
    const durationInFrames = Math.max(1, Math.round(durationInSeconds * fps));
    const browserSafeVideoUrl = toBrowserSafeMediaUrl(videoUrl);

    const inputProps = useMemo(
        () => ({
            videoUrl: browserSafeVideoUrl,
            durationInFrames,
            fps,
            width: 1080,
            height: 1920,
            subtitles,
            hook,
            effects,
        }),
        [browserSafeVideoUrl, durationInFrames, subtitles, hook, effects]
    );

    useImperativeHandle(ref, () => ({
        seekToMs(ms) {
            const frame = Math.max(0, Math.floor((Number(ms) || 0) * fps / 1000));
            playerRef.current?.seekTo?.(frame);
        },
    }), [fps]);

    const playerKey = useMemo(() => JSON.stringify({
        durationInFrames,
        style: subtitles?.style || null,
        words: Array.isArray(subtitles?.captions) ? subtitles.captions.length : 0,
    }), [durationInFrames, subtitles]);

    return (
        <div className={`w-full h-full ${className}`}>
            <Player
                key={playerKey}
                ref={playerRef}
                component={ShortVideo}
                inputProps={inputProps}
                durationInFrames={durationInFrames}
                fps={fps}
                compositionWidth={1080}
                compositionHeight={1920}
                style={{
                    width: '100%',
                    height: '100%',
                }}
                controls
                autoPlay
                loop
            />
        </div>
    );
});

export default RemotionPreview;
