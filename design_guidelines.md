{
  "app_name": "HookForge",
  "design_personality": {
    "brand_attributes": [
      "energetic-but-serious (creator-culture + analytics)",
      "high-clarity (data-first)",
      "tactile (filmstrip + studio feel)",
      "optimistic (mint/teal calm + coral action)"
    ],
    "visual_style_fusion": {
      "layout_principle": "Bento grid + editorial side panels (analysis) + filmstrip scroller",
      "surface_style": "soft-warm neutral base with crisp borders + subtle grain overlay",
      "accent_language": "teal for navigation/selection, coral for primary CTAs, mint for success/progress",
      "avoid": [
        "purple-heavy AI aesthetics",
        "neon gradients",
        "centered single-column marketing layouts"
      ]
    }
  },
  "typography": {
    "font_pairing": {
      "display": {
        "name": "Space Grotesk",
        "weights": [500, 600, 700],
        "usage": ["H1/H2", "navigation", "score badges", "chip labels"]
      },
      "body": {
        "name": "Figtree",
        "weights": [400, 500, 600],
        "usage": ["body", "tables", "form labels", "helper text"]
      },
      "mono_optional": {
        "name": "IBM Plex Mono",
        "weights": [400, 500],
        "usage": ["Generation Spec JSON", "URLs", "IDs"]
      }
    },
    "implementation_notes": {
      "google_fonts": [
        "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Figtree:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap"
      ],
      "tailwind_usage": {
        "h1": "text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight",
        "h2": "text-base md:text-lg text-muted-foreground",
        "section_title": "text-lg font-semibold tracking-tight",
        "body": "text-sm md:text-base leading-relaxed",
        "small": "text-xs text-muted-foreground"
      }
    }
  },
  "color_system": {
    "palette": {
      "bg_lavender_white": "#F8F7FF",
      "surface_white": "#FDFBFF",
      "ink_charcoal": "#26243D",
      "muted_gray": "#6B7280",
      "border_lavender": "#DDD9F5",
      "brand_indigo": "#6366F1",
      "brand_indigo_dark": "#4F46E5",
      "accent_rose": "#F43F5E",
      "mint": "#E0E7FF",
      "danger": "#DC2626",
      "warning": "#D97706",
      "info": "#0284C7"
    },
    "semantic_tokens_hsl_for_shadcn": {
      "notes": "Update /app/frontend/src/index.css :root tokens to match these HSL values. Keep cards light for readability; use indigo/rose as accents only.",
      "root": {
        "--background": "245 50% 98%",
        "--foreground": "240 10% 15%",
        "--card": "240 40% 99%",
        "--card-foreground": "240 10% 15%",
        "--popover": "240 40% 99%",
        "--popover-foreground": "240 10% 15%",
        "--primary": "244 75% 59%",
        "--primary-foreground": "0 0% 100%",
        "--secondary": "240 20% 94%",
        "--secondary-foreground": "240 10% 15%",
        "--muted": "240 20% 94%",
        "--muted-foreground": "240 8% 46%",
        "--accent": "240 20% 94%",
        "--accent-foreground": "240 10% 15%",
        "--destructive": "0 72% 51%",
        "--destructive-foreground": "0 0% 100%",
        "--border": "240 25% 89%",
        "--input": "240 25% 89%",
        "--ring": "244 75% 59%",
        "--radius": "0.75rem"
      },
      "extra_css_custom_properties": {
        "--brand-teal": "#6366F1",
        "--brand-coral": "#F43F5E",
        "--brand-mint": "#E0E7FF",
        "--shadow-soft": "0 10px 30px rgba(30, 27, 75, 0.08)",
        "--shadow-tight": "0 6px 16px rgba(30, 27, 75, 0.10)",
        "--noise-opacity": "0.06"
      }
    },
    "gradients_and_texture": {
      "rule": "Gradients only as section backgrounds / decorative overlays; never on small UI elements; never exceed 20% viewport.",
      "allowed_gradients": [
        {
          "name": "Indigo → Rose (hero wash)",
          "css": "radial-gradient(1200px circle at 20% 10%, rgba(99,102,241,0.12), transparent 55%), radial-gradient(900px circle at 80% 0%, rgba(244,63,94,0.10), transparent 50%), linear-gradient(180deg, #F8F7FF 0%, #FDFBFF 60%, #F8F7FF 100%)"
        }
      ],
      "noise_overlay_css": "background-image: url('data:image/svg+xml,%3Csvg xmlns=\"http://www.w3.org/2000/svg\" width=\"160\" height=\"160\"%3E%3Cfilter id=\"n\"%3E%3CfeTurbulence type=\"fractalNoise\" baseFrequency=\"0.9\" numOctaves=\"3\" stitchTiles=\"stitch\"/%3E%3C/filter%3E%3Crect width=\"160\" height=\"160\" filter=\"url(%23n)\" opacity=\"0.35\"/%3E%3C/svg%3E'); mix-blend-mode: multiply; opacity: var(--noise-opacity); pointer-events:none;"
    }
  },
  "layout_and_grid": {
    "app_shell": {
      "pattern": "Left sidebar (collapsible) + top utility bar + main content",
      "desktop_grid": "max-w-[1400px] mx-auto px-4 md:px-6 lg:px-8",
      "content_grid": "grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-6",
      "bento_grid": "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"
    },
    "responsive_rules": [
      "Mobile: sidebar becomes Sheet (hamburger).",
      "Filmstrip becomes horizontal ScrollArea with snap.",
      "Side-by-side comparison stacks vertically on <md."
    ]
  },
  "core_pages_and_skeleton": {
    "home_niche_feed": {
      "top_bar": [
        "Niche selector (Tabs or Select)",
        "Paste TikTok URL input (Input + Button)",
        "History link"
      ],
      "main": [
        "Trending feed as card grid (thumbnail, title, creator, stats, Analyze Hook CTA)",
        "Right rail (desktop): 'Queue' + 'Recent analyses' mini list"
      ],
      "micro_interactions": [
        "Card hover: lift + border highlight (no transition:all)",
        "Analyze CTA: loading spinner + staged progress toast"
      ]
    },
    "analysis_detail": {
      "hero_row": [
        "Video preview (AspectRatio) + metadata",
        "Effectiveness score card (1-10) with meter + explanation"
      ],
      "filmstrip": [
        "Extracted frames (first 2-3s) in ScrollArea with snap-x",
        "Key hook frame highlighted with teal ring + 'Use as reference' button"
      ],
      "breakdown_sections": [
        "Facial expressions",
        "Body language/gestures",
        "Pacing & cuts",
        "Text overlay timing",
        "Audio cues",
        "Hook summary",
        "Replicable mechanics checklist"
      ]
    },
    "customization_workflow": {
      "left": [
        "Upload photo (dropzone)",
        "Preset chips: environment/background/clothing",
        "Free-text instructions (Textarea)",
        "Generate Preview button"
      ],
      "right": [
        "Reference key hook frame preview",
        "Generated still preview placeholder / result"
      ],
      "states": [
        "Upload validation",
        "Generation progress (multi-stage)",
        "Retry + 'edit prompt'"
      ]
    },
    "result_view": {
      "comparison": [
        "Side-by-side: Original hook frame vs Generated image",
        "Download button + Copy spec button"
      ],
      "generation_spec": [
        "Collapsible JSON-like panel (mono font)",
        "Copy-to-clipboard"
      ]
    },
    "history": {
      "layout": [
        "Table view on desktop (Table component)",
        "Card list on mobile",
        "Filters: niche, date range (Calendar), status"
      ]
    }
  },
  "components": {
    "component_path": {
      "navigation": [
        "/app/frontend/src/components/ui/navigation-menu.jsx",
        "/app/frontend/src/components/ui/sheet.jsx",
        "/app/frontend/src/components/ui/breadcrumb.jsx"
      ],
      "inputs": [
        "/app/frontend/src/components/ui/input.jsx",
        "/app/frontend/src/components/ui/textarea.jsx",
        "/app/frontend/src/components/ui/select.jsx",
        "/app/frontend/src/components/ui/tabs.jsx",
        "/app/frontend/src/components/ui/command.jsx"
      ],
      "content": [
        "/app/frontend/src/components/ui/card.jsx",
        "/app/frontend/src/components/ui/badge.jsx",
        "/app/frontend/src/components/ui/avatar.jsx",
        "/app/frontend/src/components/ui/aspect-ratio.jsx",
        "/app/frontend/src/components/ui/scroll-area.jsx",
        "/app/frontend/src/components/ui/separator.jsx"
      ],
      "feedback": [
        "/app/frontend/src/components/ui/progress.jsx",
        "/app/frontend/src/components/ui/skeleton.jsx",
        "/app/frontend/src/components/ui/sonner.jsx",
        "/app/frontend/src/components/ui/alert.jsx",
        "/app/frontend/src/components/ui/dialog.jsx",
        "/app/frontend/src/components/ui/collapsible.jsx"
      ],
      "data_display": [
        "/app/frontend/src/components/ui/table.jsx",
        "/app/frontend/src/components/ui/tooltip.jsx",
        "/app/frontend/src/components/ui/hover-card.jsx",
        "/app/frontend/src/components/ui/accordion.jsx"
      ],
      "date": [
        "/app/frontend/src/components/ui/calendar.jsx"
      ]
    },
    "custom_components_to_create": [
      {
        "name": "VideoCard",
        "purpose": "Trending feed card with thumbnail + stats + Analyze CTA",
        "notes": "Use Card + AspectRatio + Badge; include data-testid on CTA and card root."
      },
      {
        "name": "Filmstrip",
        "purpose": "Horizontal frame scroller with snap + keyframe highlight",
        "notes": "Use ScrollArea; each frame button has data-testid='filmstrip-frame-button'."
      },
      {
        "name": "HookBreakdown",
        "purpose": "Structured analysis sections with icons + checklists",
        "notes": "Use Accordion or Tabs for density; keep sections as Cards."
      },
      {
        "name": "GenerationProgress",
        "purpose": "Multi-stage progress UI (download → extract → analyze → generate)",
        "notes": "Use Progress + stepper-like list; show retry actions."
      },
      {
        "name": "SideBySideCompare",
        "purpose": "Original vs generated image comparison",
        "notes": "Use Resizable for desktop optional; stack on mobile."
      },
      {
        "name": "JsonSpecPanel",
        "purpose": "Collapsible mono panel with copy button",
        "notes": "Use Collapsible + ScrollArea; code styling."
      }
    ]
  },
  "component_styles": {
    "buttons": {
      "shape": "rounded-xl (12px)",
      "variants": {
        "primary": "bg-[color:var(--brand-teal)] text-white hover:bg-[color:var(--brand-teal-dark)] focus-visible:ring-2 focus-visible:ring-[color:var(--brand-teal)]",
        "secondary": "bg-white border border-[color:var(--border)] text-[color:var(--foreground)] hover:bg-[color:rgba(99,102,241,0.06)]",
        "ghost": "hover:bg-[color:rgba(41,37,36,0.06)]"
      },
      "motion": "hover:-translate-y-[1px] active:translate-y-0 active:scale-[0.98] transition-colors transition-shadow (no transition-all)",
      "data_testid_examples": [
        "data-testid='analyze-hook-button'",
        "data-testid='generate-preview-button'",
        "data-testid='copy-generation-spec-button'"
      ]
    },
    "cards": {
      "base": "bg-[color:var(--surface_white)] border border-[color:var(--border)] rounded-2xl shadow-[var(--shadow-soft)]",
      "hover": "hover:shadow-[var(--shadow-tight)] hover:border-[color:rgba(99,102,241,0.35)] transition-shadow transition-colors",
      "header": "space-y-1",
      "padding": "p-4 md:p-5"
    },
    "chips_and_badges": {
      "niche_chip": "rounded-full px-3 py-1 text-xs font-medium bg-white border border-[color:var(--border)] hover:border-[color:rgba(99,102,241,0.45)]",
      "score_badge": "rounded-full px-2.5 py-1 text-xs font-semibold bg-[color:rgba(244,63,94,0.15)] text-[color:#9F1239]"
    },
    "filmstrip_frames": {
      "frame_button": "relative shrink-0 w-[120px] md:w-[140px] rounded-xl overflow-hidden border border-[color:var(--border)] focus-visible:ring-2 focus-visible:ring-[color:var(--brand-teal)]",
      "selected": "ring-2 ring-[color:var(--brand-teal)]",
      "timestamp_pill": "absolute bottom-2 left-2 rounded-full bg-black/70 text-white text-[11px] px-2 py-0.5"
    },
    "forms": {
      "input": "bg-white/80 border-[color:var(--border)] focus-visible:ring-[color:var(--brand-teal)]",
      "textarea": "min-h-[110px]",
      "dropzone": "border-dashed rounded-2xl bg-white/60 hover:bg-white/80"
    }
  },
  "motion_and_microinteractions": {
    "library": {
      "recommended": "framer-motion",
      "install": "npm i framer-motion",
      "usage": "Use for page transitions, card entrance, progress step transitions. Respect prefers-reduced-motion."
    },
    "principles": [
      "Entrance: fade + slight y (6-10px) for cards",
      "Hover: subtle lift (translateY -1px) + shadow tighten",
      "Loading: skeletons for thumbnails + progress for async stages",
      "Scroll: filmstrip snap + subtle gradient edge fade"
    ],
    "durations": {
      "fast": "150ms",
      "base": "220ms",
      "slow": "320ms"
    }
  },
  "async_states_and_empty_states": {
    "multi_stage_progress": [
      "Downloading video",
      "Extracting frames (0–3s)",
      "Analyzing hook mechanics",
      "Preparing generation spec",
      "Generating still preview"
    ],
    "empty_states": {
      "no_feed": "Show Card with 'Pick a niche' + example niches chips.",
      "no_history": "Show illustration placeholder + 'Analyze your first hook'.",
      "analysis_failed": "Alert with retry + 'Report issue' secondary action."
    },
    "error_patterns": [
      "Inline field errors under URL input",
      "Toast for transient errors",
      "Persistent Alert card for job failures with retry"
    ]
  },
  "accessibility": {
    "requirements": [
      "WCAG AA contrast for text on sand/cream",
      "Visible focus rings (ring uses teal)",
      "Keyboard navigable filmstrip (frame buttons)",
      "Use aria-label for icon-only buttons",
      "Respect prefers-reduced-motion"
    ]
  },
  "testing_attributes": {
    "rule": "All interactive and key informational elements must include data-testid (kebab-case, role-based).",
    "must_tag": [
      "niche selector",
      "paste URL input + submit",
      "Analyze Hook CTA",
      "frame selection buttons",
      "Use as reference button",
      "upload input/dropzone",
      "preset chips",
      "Generate Preview button",
      "comparison images",
      "copy/download buttons",
      "history filters"
    ]
  },
  "image_urls": {
    "decorative_textures": [
      {
        "url": "https://images.unsplash.com/photo-1656248396925-ec086a35c568?crop=entropy&cs=srgb&fm=jpg&ixlib=rb-4.1.0&q=85",
        "category": "background texture",
        "description": "Soft teal abstract texture for subtle hero overlay (opacity 6–10%)."
      },
      {
        "url": "https://images.unsplash.com/photo-1642754389554-50ec2f21a513?crop=entropy&cs=srgb&fm=jpg&ixlib=rb-4.1.0&q=85",
        "category": "background texture",
        "description": "Muted teal/green blur for section accent behind filmstrip (very low opacity)."
      },
      {
        "url": "https://images.unsplash.com/photo-1586631287056-67da5143b112?crop=entropy&cs=srgb&fm=jpg&ixlib=rb-4.1.0&q=85",
        "category": "background texture",
        "description": "Teal + warm stripe texture for empty states / onboarding cards (crop tightly)."
      }
    ],
    "editorial_creator_photos_optional": [
      {
        "url": "https://images.unsplash.com/photo-1637249772031-df4717fc3f2d?crop=entropy&cs=srgb&fm=jpg&ixlib=rb-4.1.0&q=85",
        "category": "empty state / header",
        "description": "Creator studio scene (use sparingly; avoid making it feel like a landing page)."
      }
    ]
  },
  "instructions_to_main_agent": {
    "global_css_cleanup": [
      "Remove CRA default centered App-header styles from /app/frontend/src/App.css or stop using them; do not center the whole app.",
      "Implement fonts via index.html <link> or @import in index.css.",
      "Update :root tokens in /app/frontend/src/index.css to the provided HSL values.",
      "Add a subtle noise overlay via a fixed pseudo-element on body or a top-level layout wrapper."
    ],
    "routing": [
      "Root route '/' must render Niche Feed (no landing/auth).",
      "Provide routes for /analysis/:id, /customize/:id, /history."
    ],
    "ui_build_notes_js": [
      "This repo uses .jsx (not .tsx). Keep components in .jsx and use prop-types only if needed.",
      "Use shadcn components from /app/frontend/src/components/ui/* as primary primitives.",
      "Use Sonner for toasts (/app/frontend/src/components/ui/sonner.jsx)."
    ],
    "data_testid_convention": [
      "Use kebab-case and role-based naming.",
      "Examples: niche-selector-tabs, tiktok-url-input, analyze-hook-button, filmstrip-frame-button-0, generate-preview-button, history-filter-date-range"
    ]
  },
  "general_ui_ux_design_guidelines_appendix": "<General UI UX Design Guidelines>  \n    - You must **not** apply universal transition. Eg: `transition: all`. This results in breaking transforms. Always add transitions for specific interactive elements like button, input excluding transforms\n    - You must **not** center align the app container, ie do not add `.App { text-align: center; }` in the css file. This disrupts the human natural reading flow of text\n   - NEVER: use AI assistant Emoji characters like`🤖🧠💭💡🔮🎯📚🎭🎬🎪🎉🎊🎁🎀🎂🍰🎈🎨🎰💰💵💳🏦💎🪙💸🤑📊📈📉💹🔢🏆🥇 etc for icons. Always use **FontAwesome cdn** or **lucid-react** library already installed in the package.json\n\n **GRADIENT RESTRICTION RULE**\nNEVER use dark/saturated gradient combos (e.g., purple/pink) on any UI element.  Prohibited gradients: blue-500 to purple 600, purple 500 to pink-500, green-500 to blue-500, red to pink etc\nNEVER use dark gradients for logo, testimonial, footer etc\nNEVER let gradients cover more than 20% of the viewport.\nNEVER apply gradients to text-heavy content or reading areas.\nNEVER use gradients on small UI elements (<100px width).\nNEVER stack multiple gradient layers in the same viewport.\n\n**ENFORCEMENT RULE:**\n    • Id gradient area exceeds 20% of viewport OR affects readability, **THEN** use solid colors\n\n**How and where to use:**\n   • Section backgrounds (not content backgrounds)\n   • Hero section header content. Eg: dark to light to dark color\n   • Decorative overlays and accent elements only\n   • Hero section with 2-3 mild color\n   • Gradients creation can be done for any angle say horizontal, vertical or diagonal\n\n- For AI chat, voice application, **do not use purple color. Use color like light green, ocean blue, peach orange etc**\n\n</Font Guidelines>\n\n- Every interaction needs micro-animations - hover states, transitions, parallax effects, and entrance animations. Static = dead. \n   \n- Use 2-3x more spacing than feels comfortable. Cramped designs look cheap.\n\n- Subtle grain textures, noise overlays, custom cursors, selection states, and loading animations: separates good from extraordinary.\n   \n- Before generating UI, infer the visual style from the problem statement (palette, contrast, mood, motion) and immediately instantiate it by setting global design tokens (primary, secondary/accent, background, foreground, ring, state colors), rather than relying on any library defaults. Don't make the background dark as a default step, always understand problem first and define colors accordingly\n    Eg: - if it implies playful/energetic, choose a colorful scheme\n           - if it implies monochrome/minimal, choose a black–white/neutral scheme\n\n**Component Reuse:**\n\t- Prioritize using pre-existing components from src/components/ui when applicable\n\t- Create new components that match the style and conventions of existing components when needed\n\t- Examine existing components to understand the project's component patterns before creating new ones\n\n**IMPORTANT**: Do not use HTML based component like dropdown, calendar, toast etc. You **MUST** always use `/app/frontend/src/components/ui/ ` only as a primary components as these are modern and stylish component\n\n**Best Practices:**\n\t- Use Shadcn/UI as the primary component library for consistency and accessibility\n\t- Import path: ./components/[component-name]\n\n**Export Conventions:**\n\t- Components MUST use named exports (export const ComponentName = ...)\n\t- Pages MUST use default exports (export default function PageName() {...})\n\n**Toasts:**\n  - Use `sonner` for toasts\"\n  - Sonner component are located in `/app/src/components/ui/sonner.tsx`\n\nUse 2–4 color gradients, subtle textures/noise overlays, or CSS-based noise to avoid flat visuals.\n</General UI UX Design Guidelines>"
}
