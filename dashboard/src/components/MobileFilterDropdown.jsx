import { useEffect, useMemo, useRef, useState } from "react";
import PropTypes from "prop-types";
import { Check, ChevronDown } from "lucide-react";

export default function MobileFilterDropdown({ value, onChange, options, ariaLabel = "Filtre" }) {
    const [open, setOpen] = useState(false);
    const rootRef = useRef(null);

    const selected = useMemo(
        () => options.find((option) => option.value === value) || options[0] || { label: "", value: "" },
        [options, value]
    );

    useEffect(() => {
        if (!open) return undefined;

        const handleClickOutside = (event) => {
            if (!rootRef.current?.contains(event.target)) {
                setOpen(false);
            }
        };

        const handleEscape = (event) => {
            if (event.key === "Escape") {
                setOpen(false);
            }
        };

        document.addEventListener("mousedown", handleClickOutside);
        document.addEventListener("touchstart", handleClickOutside);
        window.addEventListener("keydown", handleEscape);

        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
            document.removeEventListener("touchstart", handleClickOutside);
            window.removeEventListener("keydown", handleEscape);
        };
    }, [open]);

    return (
        <div ref={rootRef} className="relative md:hidden">
            <button
                type="button"
                aria-label={ariaLabel}
                aria-haspopup="listbox"
                aria-expanded={open}
                onClick={() => setOpen((prev) => !prev)}
                className="flex w-full items-center justify-between rounded-xl border border-slate-300 dark:border-white/10 bg-black/30 px-3 py-2.5 text-sm text-white"
            >
                <span className="truncate">{selected.label}</span>
                <ChevronDown size={16} className={`ml-2 shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
            </button>

            {open ? (
                <div className="absolute left-0 right-0 top-full z-50 mt-2 overflow-hidden rounded-xl border border-slate-300 dark:border-white/10 bg-zinc-900 shadow-2xl">
                    <div role="listbox" aria-label={ariaLabel} className="max-h-64 overflow-y-auto py-1">
                        {options.map((option) => {
                            const isActive = option.value === value;
                            return (
                                <button
                                    key={option.value || "all"}
                                    type="button"
                                    role="option"
                                    aria-selected={isActive}
                                    onClick={() => {
                                        onChange(option.value);
                                        setOpen(false);
                                    }}
                                    className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm transition-colors ${
                                        isActive ? "bg-primary/15 text-primary" : "text-zinc-200 hover:bg-white/10"
                                    }`}
                                >
                                    <span>{option.label}</span>
                                    {isActive ? <Check size={14} /> : null}
                                </button>
                            );
                        })}
                    </div>
                </div>
            ) : null}
        </div>
    );
}

MobileFilterDropdown.propTypes = {
    value: PropTypes.string.isRequired,
    onChange: PropTypes.func.isRequired,
    options: PropTypes.arrayOf(
        PropTypes.shape({
            value: PropTypes.string.isRequired,
            label: PropTypes.string.isRequired,
        })
    ).isRequired,
    ariaLabel: PropTypes.string,
};

