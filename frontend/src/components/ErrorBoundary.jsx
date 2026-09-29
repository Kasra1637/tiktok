import React from "react";

/**
 * Top-level error boundary.
 *
 * Without this, any throw during render (a bad Clerk key, a malformed API
 * response, a missing icon export) unmounts the entire tree and the user is
 * left staring at a blank dark page with no clue what happened. This turns
 * that failure mode into a readable screen with the actual error text and a
 * reload button.
 *
 * Deliberately dependency-free and inline-styled so it still renders even if
 * Tailwind/CSS or a UI component is the thing that broke.
 */
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null, componentStack: null };
  }

  static getDerivedStateFromError(error) {
    // Reset the stack too: getDerivedStateFromError replaces state wholesale,
    // so a previous error's stack must not leak into a new one.
    return { error, componentStack: null };
  }

  componentDidCatch(error, info) {
    console.error("[HookForge] Unhandled render error:", error, info);
    // info.componentStack is the only place the real component names survive a
    // production build, so it is kept for the fallback screen. This runs after
    // the first fallback render, which then re-renders with the stack.
    if (info?.componentStack) {
      this.setState({ componentStack: String(info.componentStack) });
    }
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    // A minified build strips the identifier out of a
    // "Cannot access 'x' before initialization", so the message alone is a
    // dead end - it names a one-letter variable that exists nowhere in the
    // source. The component stack is what actually points at the culprit, so
    // it is shown here rather than only going to the console.
    const message = String(error?.message || error);
    const isOpaqueIdentifier = /^Cannot access '[^']+' before initialization$/.test(message);
    const componentStack = String(this.state.componentStack || "").trim();

    return (
      <div
        role="alert"
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "24px",
          background: "hsl(228, 14%, 7%)",
          color: "hsl(220, 20%, 93%)",
          fontFamily: '"Figtree", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        }}
      >
        <div style={{ maxWidth: 560, width: "100%" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              marginBottom: 18,
            }}
          >
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 36,
                height: 36,
                borderRadius: 10,
                background: "rgba(254, 44, 85, 0.12)",
                border: "1px solid rgba(254, 44, 85, 0.25)",
                color: "#FE2C55",
                fontSize: 18,
                fontWeight: 700,
              }}
            >
              !
            </span>
            <span style={{ fontSize: 17, fontWeight: 700, letterSpacing: "-0.02em" }}>
              Something went wrong
            </span>
          </div>

          <p style={{ fontSize: 14, lineHeight: 1.6, color: "hsl(220, 10%, 62%)", margin: "0 0 16px" }}>
            The app hit an unexpected error while rendering. The details below usually say why.
          </p>

          <pre
            style={{
              margin: "0 0 20px",
              padding: 14,
              borderRadius: 12,
              background: "hsl(228, 14%, 10%)",
              border: "1px solid rgba(255,255,255,0.08)",
              color: "hsl(220, 10%, 70%)",
              fontFamily: '"IBM Plex Mono", Menlo, Consolas, monospace',
              fontSize: 12,
              lineHeight: 1.6,
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              maxHeight: 220,
              overflow: "auto",
            }}
          >
            {message}
          </pre>

          {isOpaqueIdentifier && (
            <p style={{ margin: "-8px 0 16px", fontSize: 13, lineHeight: 1.6, color: "hsl(220, 10%, 62%)" }}>
              The identifier above is minified. The component stack below is what
              identifies the real source file — please include it when reporting
              this.
            </p>
          )}

          {componentStack && (
            <pre
              style={{
                margin: "0 0 20px",
                padding: 14,
                borderRadius: 12,
                background: "hsl(228, 14%, 10%)",
                border: "1px solid rgba(255,255,255,0.08)",
                color: "hsl(220, 10%, 70%)",
                fontFamily: '"IBM Plex Mono", Menlo, Consolas, monospace',
                fontSize: 11,
                lineHeight: 1.5,
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                maxHeight: 260,
                overflow: "auto",
              }}
            >
              {componentStack}
            </pre>
          )}

          <button
            onClick={() => window.location.reload()}
            style={{
              appearance: "none",
              border: "none",
              cursor: "pointer",
              padding: "10px 18px",
              borderRadius: 12,
              background: "#818CF8",
              color: "#fff",
              fontSize: 14,
              fontWeight: 600,
              fontFamily: "inherit",
            }}
          >
            Reload page
          </button>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
