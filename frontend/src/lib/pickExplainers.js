/**
 * The pick explainers (Kasra's order, Nov 27 2026): every unified
 * slider carries one brief explanation of what its CURRENT stop
 * means — what having the toggle set there does to the result.
 * The slider shows the explainer for the stop the user just set,
 * after they change that slider this session; an untouched pick
 * shows none (the display rule of the same day's toggle round).
 *
 * Every explainer is written to one tight shared band — 55–65
 * characters for the fixed texts — so no slider's explanation
 * outweighs another's, and each is far shorter than the long
 * silent-voice note (~200 characters) this set replaces. The
 * render smoke suite measures every text this module carries and
 * pins the band, so a future long explainer fails the gate.
 *
 * Stops whose names are themselves content (a Location, a
 * Wardrobe, an environment, a backdrop, an animation) take their
 * explainer from the small functions at the bottom: one fixed
 * line per seat explaining what the seat controls, never naming
 * the stop — the pick's name already stands under the track.
 */

export const VOICE_EXPLAINERS = {
  talking: "The character speaks the line aloud, lips moving with the words.",
  silent: "No voice is recorded; TikTok text-to-speech can carry the line.",
};

export const CAMERA_EXPLAINERS = {
  handheld: "The character holds the phone, selfie style, free to move.",
  fixed: "The camera stays set down in one indoor spot for the take.",
};

export const TONE_EXPLAINERS = {
  "": "The app picks the hook's tone from the app and the angle.",
  plain: "The hook speaks plainly, with no extra color in the words.",
  warm: "The hook speaks warmly, like a friend sharing good news.",
  bold: "The hook speaks boldly, leading with a strong, sure claim.",
};

export const SHAPE_EXPLAINERS = {
  auto: "The app picks the hook's shape from the app and the angle.",
  question: "The hook asks a question and holds the answer for the demo.",
  statement: "The hook states the pain plainly and holds back the answer.",
};

export const OPENING_EXPLAINERS = {
  auto: "The app picks how the hook opens from the app and the angle.",
  action: "The hook opens mid-action, on the verb already in motion.",
  feeling: "The hook opens on the felt sensation before anything moves.",
};

// The Focus pick's stops are the app's choice plus the profile's
// own outcome lines: the app's choice has its own text, and a
// chosen line's explainer names the arrangement, not the line —
// the line itself already stands under the track as the value.
export const FOCUS_APP_EXPLAINER =
  "The app picks which outcome the hook leads with, by itself.";
export const FOCUS_LINE_EXPLAINER =
  "The hook leads with the outcome named under the knob here.";

export const STATUS_FILTER_EXPLAINERS = {
  completed: "Shows only renders that finished and stand ready to use.",
  failed: "Shows only renders that failed, so they can be retried.",
  generating: "Shows only renders being made right now, still in flight.",
  submitted: "Shows only renders sent off and still waiting to be made.",
  archived: "Shows only renders you archived and set aside earlier on.",
};

export const CLIP_STYLE_EXPLAINERS = {
  floating: "The phone floats over a backdrop, clear of any hand at all.",
  hand: "A hand holds the phone inside a real room scene on screen.",
  realistic: "The clip plays full-screen, as if filmed on the phone itself.",
};

export const TRANSITION_EXPLAINERS = {
  whip: "The join slings sideways with motion streaks at the cut.",
  zoom: "The join punches in and flashes through to the next clip.",
  spin: "The join twirls the picture into the next clip's start.",
  glitch: "The join slices and flickers as one clip becomes the next.",
};

// The resolution stops are the model's own list: its default
// (the first stop) is the standard render, and any other stop is
// a step down from it.
export function resolutionExplainer(value, isDefault) {
  return isDefault
    ? "The model's standard resolution, the usual render quality."
    : "A lower resolution: a smaller file with a softer picture.";
}

// The label-carrying seats (Kasra's order, later Nov 27 2026):
// the old templates merely restated the pick ("The hook is
// filmed in this place: Living room."), so each seat now carries
// ONE fixed line explaining what the seat controls — the same
// words for every stop, never naming the pick. The label
// argument callers pass is ignored. The gate pins the exact
// texts and the wider 45–70 sanity band — still far under the
// old note's ~200 characters.
export function locationExplainer(label) {
  return "The place the hook is filmed in — pick the room or spot.";
}

export function wardrobeExplainer(label) {
  return "What the presenter wears on camera for this hook.";
}

export function environmentExplainer(label) {
  return "The setting painted around the clip in the editor.";
}

export function backdropExplainer(label) {
  return "What stands behind the phone in the second clip.";
}

export function animationExplainer(label) {
  return "How a still image moves while it is on screen.";
}
