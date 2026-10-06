// What to tell the founder when a request failed.
//
// Extracted from api.js so the rule can be asserted as behaviour. The rule that
// matters is the one about a 502 with no body, which is the difference between
// "the thing you clicked is broken" and "the app was briefly unavailable" -- and
// getting that wrong sends people to retry work that never started.

/**
 * The message for a failed request.
 *
 * Our handlers always answer with a JSON `detail`, so it is preferred whenever
 * it exists and says something specific. The interesting case is when it does
 * NOT: a 502 with no JSON body came from the edge in front of the app, meaning
 * the container was restarting, asleep, or the connection dropped mid-request.
 * That is the app being briefly unavailable rather than the action being broken,
 * and "Request failed with status code 502" reads like the latter.
 *
 * A 502 that *does* carry a detail is our own handler reporting a failed
 * recovery, and that detail is the honest one, so it wins.
 */
export function errorMessageFor(err) {
  const detail = err?.response?.data?.detail;
  if (detail) return detail;
  if (err?.response?.status === 502) {
    return (
      "The server restarted while this was running, so nothing was saved. " +
      "Wait a moment and try again."
    );
  }
  return err?.message || "Something went wrong. Please try again.";
}
