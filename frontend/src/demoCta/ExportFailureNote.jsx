/**
 * Which export stage a bannered failure came from, and when. The banner
 * carries the message; this names the stage so a founder (or a bug report)
 * can tell a failed encode from a failed save without opening the console.
 */
export function ExportFailureNote({ entry }) {
  if (!entry) return null;
  let when = "";
  try {
    when = new Date(entry.at).toLocaleTimeString();
  } catch {
    when = "";
  }
  const next =
    entry.stage === "save"
      ? "Your video is still above — Download it, then try Save again or a shorter clip."
      : "Try the export again in Chrome or Edge.";
  return (
    <span className="mt-1 block text-xs opacity-80">
      Failed during {entry.stage}{when ? ` · ${when}` : ""}. {next}
    </span>
  );
}
