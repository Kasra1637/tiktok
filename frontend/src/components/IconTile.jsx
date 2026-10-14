import { cn } from "../lib/utils";

const SIZES = {
  page: { box: "h-10 w-10 rounded-xl", icon: "h-[18px] w-[18px]" },
  section: { box: "h-8 w-8 rounded-lg", icon: "h-4 w-4" },
  empty: { box: "h-14 w-14 rounded-2xl shadow-[var(--shadow-md)]", icon: "h-6 w-6" },
};

/** The tinted indigo square behind a page, section or empty-state icon. */
export function IconTile({ icon: Icon, size = "section", className }) {
  const s = SIZES[size] || SIZES.section;
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex shrink-0 items-center justify-center border border-[color:var(--indigo-25)] bg-gradient-to-b from-[color:var(--indigo-15)] to-[color:var(--indigo-6)] text-[color:var(--brand-indigo)] shadow-[inset_0_1px_0_0_rgba(129,140,248,0.28),var(--shadow-xs)]",
        s.box,
        className
      )}
    >
      <Icon className={s.icon} />
    </span>
  );
}

export default IconTile;
