import { Link, useLocation } from "react-router-dom";
import { AccountButton } from "./auth/AuthControls";
import { isClerkConfigured } from "../lib/clerk";
import {
  Sparkles,
  Compass,
  Repeat2,
  Bookmark,
  Briefcase,
  History as HistoryIcon,
  PanelLeftClose,
  PanelLeftOpen,
  X,
  ArrowUpRight,
} from "lucide-react";

/**
 * Sidebar navigation model.
 *
 * `testId` values are the canonical ones the rest of the app (and the
 * onboarding tour convention) expects — they must stay on the DESKTOP
 * sidebar instance. The mobile drawer renders the same model with
 * `mobile-`-prefixed test ids so the two instances never produce duplicate
 * selectors for `document.querySelector`.
 */
export const NAV_GROUPS = [
  {
    label: "Pipeline",
    items: [
      { to: "/discover", label: "Discover", icon: Compass, testId: "discover-nav-link", hint: "Trending hooks" },
      { to: "/face-swap", label: "Face Swap", icon: Repeat2, testId: "face-swap-nav-link", hint: "Swap yourself in" },
    ],
  },
  {
    label: "Library",
    items: [
      { to: "/templates", label: "Templates", icon: Bookmark, testId: "templates-nav-link", hint: "Saved hooks" },
      { to: "/history", label: "History", icon: HistoryIcon, testId: "history-nav-link", hint: "Everything you made" },
    ],
  },
  {
    label: "Setup",
    items: [
      { to: "/brand", label: "Your Brand", icon: Briefcase, testId: "brand-nav-link", hint: "Brand profile" },
    ],
  },
];

/**
 * A route is active for its own path and for any nested path beneath it, so
 * `/analysis/:id` no longer leaves the whole sidebar looking unselected the
 * way the old exact-match top nav did.
 */
function useIsActive() {
  const { pathname } = useLocation();
  return (to) => pathname === to || pathname.startsWith(`${to}/`);
}

function LogoMark({ size = "md" }) {
  const box = size === "sm" ? "h-8 w-8" : "h-9 w-9";
  const icon = size === "sm" ? "h-4 w-4" : "h-[18px] w-[18px]";
  return (
    <span
      className={`relative flex ${box} shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[color:var(--brand-teal)] to-[color:var(--brand-teal-dark)] text-white shadow-[var(--glow-indigo)]`}
    >
      <Sparkles className={icon} />
      {/* Lit top edge — reads as a physical, beveled tile. */}
      <span className="pointer-events-none absolute inset-0 rounded-xl bg-gradient-to-b from-white/25 to-transparent" />
    </span>
  );
}

function NavItem({ item, collapsed, active, onNavigate, testId }) {
  const Icon = item.icon;

  return (
    <Link
      to={item.to}
      onClick={onNavigate}
      data-testid={testId}
      aria-current={active ? "page" : undefined}
      title={collapsed ? item.label : undefined}
      className={`group relative flex items-center rounded-xl outline-none transition-colors duration-200 ${
        collapsed ? "h-10 w-10 justify-center" : "gap-3 px-3 py-2.5"
      } ${
        active
          ? "bg-[color:var(--indigo-10)] text-foreground"
          : "text-muted-foreground hover:bg-[color:var(--indigo-6)] hover:text-foreground"
      }`}
    >
      {/* Active rail — a 3px indigo bar pinned to the panel edge. */}
      <span
        aria-hidden="true"
        className={`absolute left-0 top-1/2 -translate-y-1/2 rounded-r-full bg-[color:var(--brand-teal)] transition-all duration-200 ${
          active ? "h-5 w-[3px] opacity-100" : "h-2 w-[3px] opacity-0"
        } ${collapsed ? "-left-2" : "-left-3"}`}
      />
      <Icon
        className={`h-[18px] w-[18px] shrink-0 transition-colors ${
          active ? "text-[color:var(--brand-teal)]" : "text-muted-foreground group-hover:text-foreground"
        }`}
      />
      {!collapsed && (
        <span className="flex min-w-0 flex-col">
          <span className={`truncate text-sm leading-tight ${active ? "font-semibold" : "font-medium"}`}>
            {item.label}
          </span>
          <span className="truncate text-[10.5px] leading-tight text-muted-foreground/70">{item.hint}</span>
        </span>
      )}
    </Link>
  );
}

function NavGroups({ collapsed, onNavigate, testIdPrefix = "" }) {
  const isActive = useIsActive();

  return (
    <nav className={`flex flex-col gap-5 ${collapsed ? "items-center px-4" : "px-4"}`} aria-label="Main">
      {NAV_GROUPS.map((group) => (
        <div key={group.label} className={`flex flex-col gap-1 ${collapsed ? "items-center" : ""}`}>
          {collapsed ? (
            <span aria-hidden="true" className="mb-1 h-px w-6 bg-border" />
          ) : (
            <span className="eyebrow mb-1 px-3 text-[10px]">{group.label}</span>
          )}
          {group.items.map((item) => (
            <NavItem
              key={item.to}
              item={item}
              collapsed={collapsed}
              active={isActive(item.to)}
              onNavigate={onNavigate}
              testId={`${testIdPrefix}${item.testId}`}
            />
          ))}
        </div>
      ))}
    </nav>
  );
}

function SidebarFooter({ collapsed }) {
  if (collapsed) {
    return (
      <div className="mt-auto flex flex-col items-center gap-3 px-4 pb-4">
        {isClerkConfigured && (
          <div className="flex justify-center">
            <AccountButton
              appearance={{ elements: { avatarBox: "h-8 w-8 rounded-lg" } }}
            />
          </div>
        )}
        <Link
          to="/"
          title="Show me around"
          className="flex h-10 w-10 items-center justify-center rounded-xl text-muted-foreground transition-colors hover:bg-[color:var(--indigo-6)] hover:text-foreground"
        >
          <ArrowUpRight className="h-[18px] w-[18px]" />
        </Link>
      </div>
    );
  }

  return (
    <div className="mt-auto px-4 pb-4 space-y-3">
      {/* User avatar + sign-out. Hidden entirely in no-auth mode, where there
          is no account to manage. */}
      {isClerkConfigured && (
        <div className="flex items-center gap-3 rounded-xl border border-[color:var(--hairline)] bg-secondary/30 px-3 py-2.5">
          <AccountButton
            appearance={{ elements: { avatarBox: "h-8 w-8 rounded-lg" } }}
          />
          <div className="min-w-0 flex-1">
            <p className="truncate text-[12px] font-medium leading-tight">Your Account</p>
            <p className="text-[10px] text-muted-foreground">Manage profile</p>
          </div>
        </div>
      )}

      {/* Only shown when the window is tall enough that it isn't stealing
          room from the nav list (see the `tall` screen in tailwind.config). */}
      <Link
        to="/"
        className="flex items-center gap-2.5 rounded-2xl border border-[color:var(--hairline)] bg-[color:var(--indigo-4)] p-3.5 transition-colors hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-8)] tall:flex hidden"
      >
        <ArrowUpRight className="h-4 w-4 shrink-0 text-[color:var(--brand-teal)]" />
        <span className="font-display text-[13px] font-semibold leading-tight">Show me around</span>
      </Link>
    </div>
  );
}

/**
 * Fixed left navigation panel (desktop / large tablet).
 *
 * Replaces the former sticky top navbar. Collapsible down to an icon rail;
 * the chosen width is published to `--app-sidebar-w` by AppShell so other
 * fixed-position chrome can avoid overlapping it.
 */
export function Sidebar({ collapsed, onToggleCollapsed }) {
  return (
    <aside
      className="fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-[color:var(--hairline)] bg-[hsl(228_14%_8%_/_0.86)] backdrop-blur-xl lg:flex"
      style={{ width: collapsed ? "var(--sidebar-w-collapsed)" : "var(--sidebar-w)" }}
      data-testid="app-sidebar"
    >
      {/* Vertical brand sheen down the panel's inner edge. */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-0 right-0 w-px bg-gradient-to-b from-[color:var(--indigo-35)] via-transparent to-transparent"
      />

      {/* Brand + collapse control */}
      <div className={`flex h-[60px] shrink-0 items-center ${collapsed ? "justify-center px-3" : "gap-2.5 px-5"}`}>
        <Link
          to="/discover"
          className="flex min-w-0 items-center gap-2.5 outline-none"
          data-testid="logo-home-link"
          title="HookForge — go to Discover"
        >
          <LogoMark />
          {!collapsed && (
            <span className="font-display truncate text-[17px] font-bold tracking-tight">HookForge</span>
          )}
        </Link>
        {!collapsed && (
          <button
            type="button"
            onClick={onToggleCollapsed}
            aria-label="Collapse sidebar"
            title="Collapse sidebar"
            data-testid="sidebar-collapse-button"
            className="ml-auto flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-[color:var(--indigo-8)] hover:text-foreground"
          >
            <PanelLeftClose className="h-4 w-4" />
          </button>
        )}
      </div>

      {collapsed && (
        <button
          type="button"
          onClick={onToggleCollapsed}
          aria-label="Expand sidebar"
          title="Expand sidebar"
          data-testid="sidebar-expand-button"
          className="mx-auto mb-3 flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-[color:var(--indigo-8)] hover:text-foreground"
        >
          <PanelLeftOpen className="h-4 w-4" />
        </button>
      )}

      <div className="mb-4 h-px bg-border/60" />

      <div className="flex-1 overflow-y-auto overflow-x-hidden">
        <NavGroups collapsed={collapsed} />
      </div>

      <SidebarFooter collapsed={collapsed} />
    </aside>
  );
}

/**
 * Off-canvas version of the same panel for small screens, opened from the
 * top bar's menu button. Uses `mobile-`-prefixed test ids so it never
 * shadows the desktop sidebar's canonical selectors.
 */
export function MobileSidebar({ open, onClose }) {
  return (
    /* z-45 deliberately sits above the tour's floating help button (z-40) so
       the drawer isn't punctured by it, while staying below Radix dialogs
       (z-50) and the onboarding tour overlay (z-100/101). */
    <div
      className={`fixed inset-0 z-[45] lg:hidden ${open ? "" : "pointer-events-none"}`}
      aria-hidden={!open}
      data-testid="mobile-sidebar"
    >
      <div
        onClick={onClose}
        className={`absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity duration-200 ${
          open ? "opacity-100" : "opacity-0"
        }`}
        data-testid="mobile-sidebar-backdrop"
      />
      <div
        className={`absolute inset-y-0 left-0 flex w-[272px] max-w-[82vw] flex-col border-r border-[color:var(--hairline)] bg-[hsl(228_14%_8%)] shadow-[var(--shadow-xl)] transition-transform duration-300 ease-out-expo ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
      >
        <div className="flex h-[60px] shrink-0 items-center gap-2.5 px-5">
          <Link
            to="/discover"
            onClick={onClose}
            className="flex min-w-0 items-center gap-2.5"
            data-testid="mobile-logo-home-link"
          >
            <LogoMark />
            <span className="font-display truncate text-[17px] font-bold tracking-tight">HookForge</span>
          </Link>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close navigation"
            data-testid="mobile-sidebar-close-button"
            className="ml-auto flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-[color:var(--indigo-8)] hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mb-4 h-px bg-border/60" />

        <div className="flex-1 overflow-y-auto">
          <NavGroups collapsed={false} onNavigate={onClose} testIdPrefix="mobile-" />
        </div>

        <SidebarFooter collapsed={false} />
      </div>
    </div>
  );
}

export default Sidebar;
