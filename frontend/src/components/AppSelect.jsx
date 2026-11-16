import { useEffect, useId, useRef, useState } from "react";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "../lib/utils";

/**
 * The app-drawn dropdown — the only dropdown in the app (ADRs 0162/0163).
 *
 * A native <select>'s open menu belongs to the browser/OS, which
 * ignores the page's styling — so the open and selected states the
 * one filter treatment (ADR 0161) promised were invisible exactly
 * where the founder went looking for them. ADR 0162 drew the filter
 * dropdowns' menus with this control; the founder then widened the
 * order to every dropdown in the app (ADR 0163), so the form-field
 * selects (render model and resolution, camera setup, the direction
 * picks, the Demo + CTA video fit) are this same control too. There
 * is no second dropdown component and no native select left.
 *
 * One component, two skins: the closed button wears whatever skin
 * the caller passes in — the shared filter pill (`PILL_SELECT_CLASS`)
 * in the filter bars, the form-field skin (`CONTROL_CLASS`) in
 * forms — and the open menu is always the same panel in the card
 * surface language, whose chosen option wears the selection indigo,
 * like every other "selected" in the app.
 *
 * Focus stays on the button while the menu is open and the active
 * option is named through `aria-activedescendant`, so Escape and
 * selection land the founder back on the control they opened — the
 * same contract a native select keeps. Options are plain data
 * ({ value, label, disabled? }); choosing one reports the value
 * through `onChange`, exactly as ADR 0162's control did — a re-pick
 * of the value already held reports too, because the History
 * filters treat a pick as a navigation (the URL param moves even
 * when the side picked is the side already showing).
 */
export function AppSelect({
  options,
  value,
  onChange,
  id,
  ariaLabel,
  testId,
  dataActive = false,
  className,
  placeholder,
  align = "start",
  disabled = false,
  block = false,
  wrapClassName,
}) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const wrapRef = useRef(null);
  const buttonRef = useRef(null);
  const typeaheadRef = useRef({ text: "", at: 0 });
  const reactId = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const listboxId = `${reactId}-listbox`;
  const optionId = (index) => `${reactId}-option-${index}`;

  const selectedIndex = options.findIndex((option) => option.value === value);
  const selected = selectedIndex >= 0 ? options[selectedIndex] : null;
  // What the closed control says: the chosen option's label. Before
  // anything is chosen a placeholder names the prompt (the native
  // select's disabled prompt option); with neither, a native select
  // shows its first option, and so does this.
  const buttonLabel = selected
    ? selected.label
    : placeholder && (value === "" || value == null)
      ? placeholder
      : (options[0]?.label ?? placeholder ?? "");

  const firstEnabled = () => options.findIndex((option) => !option.disabled);
  const lastEnabled = () => {
    for (let i = options.length - 1; i >= 0; i -= 1) {
      if (!options[i].disabled) return i;
    }
    return -1;
  };

  const openMenu = (fromEnd = false) => {
    if (disabled) return;
    setOpen(true);
    setActiveIndex(
      selectedIndex >= 0 ? selectedIndex : fromEnd ? lastEnabled() : firstEnabled()
    );
    // The menu's keyboard contract lives on the button; a mouse user
    // who opened by click holds no focus yet, so take it — the same
    // place a native select keeps focus while its menu is open.
    buttonRef.current?.focus();
  };

  const choose = (index) => {
    const option = options[index];
    setOpen(false);
    buttonRef.current?.focus();
    if (option && !option.disabled) onChange(option.value);
  };

  const moveActive = (delta) => {
    setActiveIndex((current) => {
      let index = current;
      for (let step = 0; step < options.length; step += 1) {
        index = (((index + delta) % options.length) + options.length) % options.length;
        if (!options[index].disabled) return index;
      }
      return current;
    });
  };

  // First-letter jumping, the native select's other keyboard habit:
  // typing moves the highlight to the next option starting with the
  // letters typed, wrapping once around the list.
  const typeahead = (char) => {
    const now = Date.now();
    const text =
      now - typeaheadRef.current.at > 600 ? char : typeaheadRef.current.text + char;
    typeaheadRef.current = { text, at: now };
    const needle = text.toLowerCase();
    for (let step = 1; step <= options.length; step += 1) {
      const index = (((activeIndex + step) % options.length) + options.length) % options.length;
      if (!options[index].disabled && options[index].label.toLowerCase().startsWith(needle)) {
        setActiveIndex(index);
        return;
      }
    }
  };

  const onButtonClick = () => {
    if (disabled) return;
    if (open) setOpen(false);
    else openMenu();
  };

  const onButtonKeyDown = (event) => {
    if (disabled) return;
    const { key } = event;
    if (!open) {
      if (key === "ArrowDown" || key === "ArrowUp") {
        event.preventDefault();
        openMenu(key === "ArrowUp");
      }
      // Enter and Space keep the button's native click, which opens.
      return;
    }
    switch (key) {
      case "ArrowDown":
        event.preventDefault();
        moveActive(1);
        break;
      case "ArrowUp":
        event.preventDefault();
        moveActive(-1);
        break;
      case "Home":
        event.preventDefault();
        setActiveIndex(firstEnabled());
        break;
      case "End":
        event.preventDefault();
        setActiveIndex(lastEnabled());
        break;
      case "Enter":
      case " ":
        // Cancel the button's own click activation, or the choice
        // would be followed at once by the toggle closing over it.
        event.preventDefault();
        if (activeIndex >= 0) choose(activeIndex);
        else setOpen(false);
        break;
      case "Escape":
        event.preventDefault();
        setOpen(false);
        break;
      case "Tab":
        setOpen(false);
        break;
      default:
        if (key.length === 1) typeahead(key);
        break;
    }
  };

  // A press anywhere outside the control closes the menu, as a
  // native menu closes when the founder clicks away from it.
  useEffect(() => {
    if (!open) return undefined;
    const onPointerDown = (event) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open ]);

  return (
    <span ref={wrapRef} className={cn("app-select", block && "app-select-block", wrapClassName)}>
      <button
        ref={buttonRef}
        type="button"
        id={id}
        disabled={disabled}
        data-testid={testId}
        data-active={dataActive ? "true" : undefined}
        data-value={value ?? ""}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        aria-activedescendant={open && activeIndex >= 0 ? optionId(activeIndex) : undefined}
        className={cn("app-select-button", className)}
        onClick={onButtonClick}
        onKeyDown={onButtonKeyDown}
      >
        <span className="app-select-label">{buttonLabel}</span>
        <ChevronDown
          aria-hidden="true"
          className={`h-3.5 w-3.5 shrink-0 ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div
          role="listbox"
          id={listboxId}
          aria-label={ariaLabel}
          className={cn("app-select-menu", align === "end" && "app-select-menu-end")}
        >
          {options.map((option, index) => {
            const isSelected = option.value === value;
            return (
              <div
                key={option.value}
                role="option"
                id={optionId(index)}
                data-value={option.value}
                aria-selected={isSelected}
                aria-disabled={option.disabled || undefined}
                data-highlighted={index === activeIndex ? "true" : undefined}
                className="app-select-option"
                onMouseEnter={() => {
                  if (!option.disabled) setActiveIndex(index);
                }}
                onClick={() => choose(index)}
              >
                <span className="app-select-check" aria-hidden="true">
                  {isSelected && <Check className="h-4 w-4" />}
                </span>
                <span>{option.label}</span>
              </div>
            );
          })}
        </div>
      )}
    </span>
  );
}

export default AppSelect;
