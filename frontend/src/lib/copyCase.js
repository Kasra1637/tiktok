/**
 * Sentence capitalization for copy this app does not author by hand.
 *
 * The hand-written copy in this app is capitalized, and the two prior
 * capitalization passes (0e40336, 91e5931) swept the source for it. What those
 * passes could not reach is the text a MODEL wrote: content angles, tailored
 * template outcomes, and strategy fields are all generated from JSON schema
 * examples that read like "the concrete problem this angle speaks to", so the
 * model returns "sporadic journaling that fails to reveal patterns" and the
 * card renders it verbatim. Every generated angle therefore starts lowercase,
 * which reads as a typo next to the hand-written lines above it.
 *
 * So the last mile is fixed here rather than in the data. Two reasons:
 *
 *   1. It is immediate. Every angle, template and strategy already in the
 *      database is fixed the moment this ships, with no migration and no
 *      rewrite of rows a founder may have edited by hand.
 *   2. The generation prompt is the actual source, and it is fixed separately
 *      (ai_service.py). This is the safety net for text written before that
 *      rule existed, and for anything a model still gets wrong.
 *
 * WHAT THIS MUST NOT DO
 * ---------------------
 * It capitalizes the first letter of each SENTENCE and nothing else. That
 * distinction is load-bearing, and the three things below are the cases a
 * regex or a blanket `replace(/^./)` would get wrong:
 *
 *   - Mid-sentence fragments stay untouched. Six string literals in
 *     CreateVideo.jsx are continuation halves of a concatenated sentence
 *     ("...rebuild it on Hook + Story " + "before rendering if you edited
 *     since it was built."). Capitalizing the tail would render "Hook +
 *     Story Before rendering". Those are never passed through here.
 *   - Tokens that are not prose are left alone: emails, URLs, and anything
 *     that does not start with a letter. "privacy@hookforge.app" must not
 *     become "Privacy@hookforge.app", which would break the mailto.
 *   - Text that is already correct is a no-op, so this is safe to apply
 *     unconditionally at render time and safe to re-run.
 */

// Punctuation that ends a sentence, plus the whitespace that follows it.
// Splitting on this is what makes "nothing gets finished. it stays with them"
// become "Nothing gets finished. It stays with them".
const SENTENCE_BOUNDARY = /([.!?]\s+)/;

// A leading token that is an address or a bare domain, never prose.
// "privacy@hookforge.app" must not become "Privacy@hookforge.app" (a broken
// mailto), and "taskly.com/sync" must not become "Taskly.com/sync" (a wrong
// link). Both appear inside stored free-text fields, so they are checked
// rather than assumed away.
const ADDRESS_LIKE = /^[^@\s]+@[^\s]+$/;
const DOMAIN_LIKE = /^[a-z0-9-]+(\.[a-z0-9-]+)+(\/|$)/i;

// A leading token that carries an internal capital is a brand name, not a
// sentence opener. "iOS", "iPhone" and "eBay" are spelled that way, and the
// Platforms field is a list of exactly these (the profile schema's own example
// is ["iOS", "Android"]), so capitalizing the first letter would render "IOS"
// — a different product's name. Prose never has this shape.
const MIXED_CASE_TOKEN = /^[a-z]+[A-Z]/;

/**
 * Uppercase the first letter of every sentence in a string.
 *
 * Returns the input unchanged (as a string) when there is nothing to do, so
 * this is cheap to call on every render of stored text.
 */
export function sentenceCase(value) {
  if (value === null || value === undefined) return "";
  const text = String(value);
  if (!text.trim()) return text;

  const trimmed = text.trimStart();
  const first = trimmed[0];
  // Not prose at all: a digit, a symbol, or nothing.
  if (!first || !/[a-z]/i.test(first)) return text;

  // Prose that OPENS with an address or a domain is not a sentence opener we
  // should touch.
  const firstToken = trimmed.split(/\s/)[0];
  if (
    ADDRESS_LIKE.test(firstToken) ||
    DOMAIN_LIKE.test(firstToken) ||
    MIXED_CASE_TOKEN.test(firstToken)
  ) {
    return text;
  }

  return text
    // Leading whitespace must not stop the match: without the \s*, a value
    // stored with an indenting space would come back untouched, and the fix
    // would look like it worked only for values that happened to be flush.
    .replace(/^\s*([a-z])/, (_match, letter) => letter.toUpperCase())
    .replace(
      new RegExp(`${SENTENCE_BOUNDARY.source}([a-z])`, "g"),
      (_match, lead, letter) => lead + letter.toUpperCase()
    );
}

/**
 * sentenceCase, but always returning a trimmed string.
 *
 * For values rendered as a standalone line rather than inside a sentence,
 * where leading whitespace is never wanted.
 */
export function sentenceCaseTrimmed(value) {
  return sentenceCase(value).trim();
}