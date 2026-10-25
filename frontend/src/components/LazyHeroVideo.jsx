import { useEffect, useRef, useState } from "react";

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
 * Under reduced motion it never loads at all: the contract there is a paused
 * poster, and downloading footage that never plays wastes the bytes this was
 * saving.
 */
export function LazyHeroVideo({ poster, sources, ariaLabel, className }) {
  const videoRef = useRef(null);
  const [reduceMotion] = useState(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true
  );
  const [shouldLoad, setShouldLoad] = useState(false);

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

  return (
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
      onCanPlay={(event) => {
        if (!reduceMotion) event.currentTarget.play()?.catch?.(() => {});
      }}
    >
      {shouldLoad &&
        sources.map((source) => (
          <source key={source.type} src={source.src} type={source.type} />
        ))}
    </video>
  );
}

export default LazyHeroVideo;
