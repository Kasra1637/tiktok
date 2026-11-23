/**
 * The empty states' mini-illustrations (ADR 0284): one line family with
 * the landing How it works strip's STEP_ART — the app's indigo tokens,
 * layered cards at stepped opacities, one solid glyph per scene. Each
 * scene shows what its page will hold once it has something: a clip
 * frame for History, a rising line for Analytics, an app tile waiting
 * for its first profile. Decorative throughout — the words beside
 * them carry the meaning.
 */
export function HistoryEmptyArt() {
  return (
    <svg data-testid="empty-art-history" viewBox="0 0 200 150" fill="none" stroke="var(--brand-indigo)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="34" y="28" width="112" height="76" rx="10" opacity="0.35" />
      <rect x="54" y="44" width="112" height="76" rx="10" fill="var(--indigo-10)" />
      <circle cx="68" cy="58" r="3" fill="var(--brand-indigo)" stroke="none" opacity="0.5" />
      <circle cx="68" cy="82" r="3" fill="var(--brand-indigo)" stroke="none" opacity="0.5" />
      <circle cx="68" cy="106" r="3" fill="var(--brand-indigo)" stroke="none" opacity="0.5" />
      <circle cx="152" cy="58" r="3" fill="var(--brand-indigo)" stroke="none" opacity="0.5" />
      <circle cx="152" cy="82" r="3" fill="var(--brand-indigo)" stroke="none" opacity="0.5" />
      <circle cx="152" cy="106" r="3" fill="var(--brand-indigo)" stroke="none" opacity="0.5" />
      <path d="M100 66 l24 16 l-24 16 Z" fill="var(--brand-indigo)" stroke="none" />
    </svg>
  );
}

export function AnalyticsEmptyArt() {
  return (
    <svg data-testid="empty-art-analytics" viewBox="0 0 200 150" fill="none" stroke="var(--brand-indigo)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="34" y="28" width="112" height="76" rx="10" opacity="0.35" />
      <rect x="54" y="44" width="112" height="76" rx="10" fill="var(--indigo-10)" />
      <line x1="74" y1="104" x2="148" y2="104" opacity="0.55" />
      <path d="M76 94 L100 76 L116 84 L146 58" />
      <circle cx="100" cy="76" r="3.5" fill="var(--brand-indigo)" stroke="none" />
      <circle cx="116" cy="84" r="3.5" fill="var(--brand-indigo)" stroke="none" />
      <circle cx="146" cy="58" r="5" fill="var(--brand-indigo)" stroke="none" />
    </svg>
  );
}

export function AppProfileEmptyArt() {
  return (
    <svg data-testid="empty-art-profile" viewBox="0 0 200 150" fill="none" stroke="var(--brand-indigo)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="34" y="28" width="112" height="76" rx="10" opacity="0.35" />
      <rect x="54" y="44" width="112" height="76" rx="10" fill="var(--indigo-10)" />
      <rect x="72" y="62" width="30" height="30" rx="8" fill="var(--indigo-25)" fillOpacity="0.35" />
      <line x1="112" y1="70" x2="148" y2="70" opacity="0.55" />
      <line x1="112" y1="86" x2="134" y2="86" opacity="0.55" />
      <circle cx="146" cy="104" r="12" fill="var(--brand-indigo)" stroke="none" />
      <path d="M146 98 v12 M140 104 h12" stroke="#fff" strokeWidth="4" />
    </svg>
  );
}
