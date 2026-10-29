import { useEffect, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";

import { Button } from "./ui/button";

/**
 * The recorded product footage (hero-demo), shared by the landing hero and the
 * hypothetical preview. The file is large and autoplays, so mounting it with
 * sources inline puts megabytes of video in a footrace with the app JS on slow
 * networks — the footage always loses and the page stays blank longer.
 *
 * So the video mounts as a poster frame only (preload="none", no sources) and
 * the footage is attached when the frame nears the viewport (400px
 * rootMargin, so it is usually loaded before it is seen). The poster IS the
 * first frame, so on fast connections the swap is invisible: no flicker, no
 * layout shift, same UI and the same autoplay. Without IntersectionObserver
 * (old browsers, embedded webviews) it loads immediately — the same as before.
 * Under reduced motion it never loads on its own: the contract there is a
 * paused poster, and downloading footage that never plays wastes the bytes this
 * was saving.
 *
 * Playback is the visitor's to stop, so a caller can ask for the play/pause
 * control (`showPlayControl`). An autoplaying loop needs a way to pause it
 * (WCAG 2.2.2), and a refused autoplay — data saver, an embedded webview, a
 * strict default — leaves the same control saying Play, which is the only way
 * through rather than a Pause drawn over a frozen poster. It is also how
 * reduced motion opts in: the poster still downloads nothing until that
 * button is pressed, so the byte-saving contract holds while the footage
 * stays reachable. The control positions against the caller's frame, so it
 * must be rendered inside a `relative` box.
 */
export function LazyHeroVideo({ poster, sources, ariaLabel, className, showPlayControl = false }) {
  const videoRef = useRef(null);
  const reduceMotion =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true;
  const [shouldLoad, setShouldLoad] = useState(false);
  // Playback truth comes from the element's own events, never from a guess:
  // autoplay can be refused, and a control that assumed it was running would
  // draw Pause over a frozen poster with no way back to Play.
  const [isPlaying, setIsPlaying] = useState(false);
  // A recording the browser cannot decode leaves the poster and no way to
  // play it. The control is dropped then: a Play button over footage that
  // cannot start is a dead control, and the poster alone reads as what it is.
  const [failed, setFailed] = useState(false);
  // A tap that lands before the footage is attached has to survive the render
  // that mounts the <source> elements, so the intent waits in a ref and the
  // effect below starts playback once they are in the DOM.
  const playOnLoadRef = useRef(false);
  // Canplay fires again after a source change; it must not restart footage the
  // visitor paused on purpose.
  const userPausedRef = useRef(false);

  useEffect(() => {
    if (videoRef.current) videoRef.current.muted = true;
    if (reduceMotion) return undefined;
    if (typeof IntersectionObserver === "undefined") {
      setShouldLoad(true);
      return undefined;
    }
    const video = videoRef.current;
    if (!video) return undefined;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setShouldLoad(true);
          observer.disconnect();
        }
      },
      { rootMargin: "400px" }
    );
    observer.observe(video);
    return () => observer.disconnect();
  }, [reduceMotion]);

  useEffect(() => {
    if (!shouldLoad || !playOnLoadRef.current) return;
    playOnLoadRef.current = false;
    videoRef.current?.play?.()?.catch?.(() => setIsPlaying(false));
  }, [shouldLoad]);

  const togglePlayback = () => {
    const video = videoRef.current;
    if (!video) return;
    if (isPlaying) {
      userPausedRef.current = true;
      video.pause?.();
      return;
    }
    userPausedRef.current = false;
    if (!shouldLoad) {
      playOnLoadRef.current = true;
      setShouldLoad(true);
      return;
    }
    video.play?.()?.catch?.(() => setIsPlaying(false));
  };

  const label = isPlaying ? "Pause the recording" : "Play the recording";

  return (
    <>
      <video
        ref={videoRef}
        className={className}
        autoPlay={!reduceMotion}
        muted
        loop
        playsInline
        preload="none"
        poster={poster}
        aria-label={ariaLabel}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onError={() => {
          setIsPlaying(false);
          setFailed(true);
        }}
        onCanPlay={(event) => {
          if (reduceMotion || userPausedRef.current) return;
          event.currentTarget.play?.()?.catch?.(() => setIsPlaying(false));
        }}
      >
        {shouldLoad &&
          sources.map((source) => (
            <source key={source.type} src={source.src} type={source.type} />
          ))}
      </video>
      {/* The wrapper owns the position: `.btn-studio` sets `position:
          relative` after Tailwind's utilities, so `absolute` on the <Button>
          itself is dropped and the control would sit in the frame's flow. */}
      {showPlayControl && !failed && (
        <div className="absolute bottom-2 right-2 z-10">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="tap-chip focus-ring h-9 w-9 rounded-full border border-white/25 bg-black/65 p-0 text-white backdrop-blur-sm hover:bg-black/80 hover:text-white"
            onClick={togglePlayback}
            aria-label={label}
            title={label}
            data-testid="hero-play-toggle"
          >
            {isPlaying ? (
              <Pause className="h-4 w-4" aria-hidden="true" />
            ) : (
              <Play className="h-4 w-4" aria-hidden="true" />
            )}
          </Button>
        </div>
      )}
    </>
  );
}

export default LazyHeroVideo;

