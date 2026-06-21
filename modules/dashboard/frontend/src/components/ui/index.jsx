import { createContext, useContext, useEffect, useRef, useState } from "react";
import { ChevronDown, X, Check, Search } from "lucide-react";
import { cn } from "../../lib/utils";

/* ---------------- Button ---------------- */
const btnVariants = {
  default: "bg-primary text-primary-foreground hover:opacity-90 shadow-sm",
  secondary: "bg-surface text-foreground border border-border hover:bg-muted",
  outline: "border border-border bg-transparent hover:bg-muted text-foreground",
  ghost: "hover:bg-muted text-foreground",
  danger: "bg-danger text-white hover:opacity-90",
  link: "text-primary underline-offset-4 hover:underline",
};
const btnSizes = {
  default: "h-9 px-4 text-sm",
  sm: "h-8 px-3 text-xs",
  lg: "h-11 px-6 text-base",
  icon: "h-9 w-9",
};
export function Button({ className, variant = "default", size = "default", ...props }) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-btn font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 whitespace-nowrap",
        btnVariants[variant],
        btnSizes[size],
        className
      )}
      {...props}
    />
  );
}

/* ---------------- Card ---------------- */
export function Card({ className, ...props }) {
  return <div className={cn("rounded-card border border-border bg-card text-card-foreground shadow-sm", className)} {...props} />;
}
export function CardHeader({ className, ...props }) {
  return <div className={cn("flex flex-col space-y-1 p-5", className)} {...props} />;
}
export function CardTitle({ className, ...props }) {
  return <h3 className={cn("font-semibold leading-tight tracking-tight", className)} {...props} />;
}
export function CardDescription({ className, ...props }) {
  return <p className={cn("text-sm text-muted-foreground", className)} {...props} />;
}
export function CardContent({ className, ...props }) {
  return <div className={cn("p-5 pt-0", className)} {...props} />;
}
export function CardFooter({ className, ...props }) {
  return <div className={cn("flex items-center p-5 pt-0", className)} {...props} />;
}

/* ---------------- Badge ---------------- */
const badgeVariants = {
  default: "bg-muted text-foreground border-border",
  primary: "bg-primary/10 text-primary border-primary/20",
  success: "bg-success/10 text-success border-success/20",
  warning: "bg-warning/10 text-warning border-warning/20",
  danger: "bg-danger/10 text-danger border-danger/20",
  info: "bg-info/10 text-info border-info/20",
  outline: "border-border text-muted-foreground",
};
export function Badge({ className, variant = "default", ...props }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
        badgeVariants[variant],
        className
      )}
      {...props}
    />
  );
}

/* Severity badge helper */
export function SeverityBadge({ level }) {
  const map = {
    Critical: "danger",
    High: "warning",
    Medium: "info",
    Low: "success",
    Info: "outline",
  };
  return (
    <Badge variant={map[level] || "default"}>
      <span className={cn("h-1.5 w-1.5 rounded-full", {
        "bg-danger": level === "Critical",
        "bg-warning": level === "High",
        "bg-info": level === "Medium",
        "bg-success": level === "Low",
        "bg-muted-foreground": level === "Info",
      })} />
      {level}
    </Badge>
  );
}

/* ---------------- Input ---------------- */
export function Input({ className, ...props }) {
  return (
    <input
      className={cn(
        "flex h-9 w-full rounded-btn border border-input bg-background px-3 py-1 text-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-ring disabled:opacity-50",
        className
      )}
      {...props}
    />
  );
}
export function Textarea({ className, ...props }) {
  return (
    <textarea
      className={cn(
        "flex min-h-[80px] w-full rounded-btn border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none",
        className
      )}
      {...props}
    />
  );
}
export function Label({ className, ...props }) {
  return <label className={cn("text-sm font-medium text-foreground", className)} {...props} />;
}

/* ---------------- Search input ---------------- */
export function SearchInput({ className, ...props }) {
  return (
    <div className={cn("relative", className)}>
      <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <Input className="pl-9" {...props} />
    </div>
  );
}

/* ---------------- Switch ---------------- */
export function Switch({ checked, onChange, className }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={() => onChange?.(!checked)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        checked ? "bg-primary" : "bg-muted-foreground/30",
        className
      )}
    >
      <span className={cn("inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform", checked ? "translate-x-4" : "translate-x-0.5")} />
    </button>
  );
}

/* ---------------- Tabs ---------------- */
const TabsCtx = createContext(null);
export function Tabs({ value, onValueChange, children, className }) {
  return <div className={className}><TabsCtx.Provider value={{ value, onValueChange }}>{children}</TabsCtx.Provider></div>;
}
export function TabsList({ className, children }) {
  return <div className={cn("inline-flex items-center gap-1 rounded-btn bg-surface border border-border p-1", className)}>{children}</div>;
}
export function TabsTrigger({ value, children, className }) {
  const ctx = useContext(TabsCtx);
  const active = ctx.value === value;
  return (
    <button
      onClick={() => ctx.onValueChange(value)}
      className={cn(
        "rounded-[6px] px-3 py-1.5 text-sm font-medium transition-all",
        active ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
        className
      )}
    >
      {children}
    </button>
  );
}

/* ---------------- Dropdown (simple) ---------------- */
export function Dropdown({ trigger, children, align = "right", className }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    function onClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);
  return (
    <div className="relative" ref={ref}>
      <div onClick={() => setOpen((o) => !o)}>{trigger}</div>
      {open && (
        <div
          className={cn(
            "absolute z-50 mt-2 min-w-[200px] rounded-card border border-border bg-popover p-1.5 shadow-lg animate-fade-in",
            align === "right" ? "right-0" : "left-0",
            className
          )}
          onClick={() => setOpen(false)}
        >
          {children}
        </div>
      )}
    </div>
  );
}
export function DropdownItem({ className, children, ...props }) {
  return (
    <button
      className={cn("flex w-full items-center gap-2 rounded-[6px] px-2.5 py-2 text-sm text-foreground hover:bg-muted transition-colors text-left", className)}
      {...props}
    >
      {children}
    </button>
  );
}

/* ---------------- Select (native styled) ---------------- */
export function Select({ className, children, ...props }) {
  return (
    <div className={cn("relative", className)}>
      <select
        className="h-9 w-full appearance-none rounded-btn border border-input bg-background pl-3 pr-8 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        {...props}
      >
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
    </div>
  );
}

/* ---------------- Modal / Dialog ---------------- */
export function Modal({ open, onClose, title, description, children, footer, className }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm animate-fade-in" onClick={onClose} />
      <div className={cn("relative z-10 w-full max-w-lg rounded-dialog border border-border bg-card p-6 shadow-lg animate-fade-in", className)}>
        <button onClick={onClose} className="absolute right-4 top-4 rounded-btn p-1 text-muted-foreground hover:bg-muted">
          <X className="h-4 w-4" />
        </button>
        {title && <h2 className="text-lg font-semibold">{title}</h2>}
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
        <div className="mt-4">{children}</div>
        {footer && <div className="mt-6 flex justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
}

/* ---------------- Progress ---------------- */
export function Progress({ value = 0, className, barClassName }) {
  return (
    <div className={cn("h-2 w-full overflow-hidden rounded-full bg-muted", className)}>
      <div className={cn("h-full rounded-full bg-primary transition-all", barClassName)} style={{ width: `${value}%` }} />
    </div>
  );
}

/* ---------------- Tooltip (title-based, lightweight) ---------------- */
export function Avatar({ name, src, className }) {
  const initials = name?.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  return src ? (
    <img src={src} alt={name} className={cn("h-9 w-9 rounded-full object-cover", className)} />
  ) : (
    <div className={cn("flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary", className)}>
      {initials}
    </div>
  );
}

/* ---------------- Skeleton ---------------- */
export function Skeleton({ className }) {
  return <div className={cn("shimmer rounded-md bg-muted", className)} />;
}

/* ---------------- Checkbox ---------------- */
export function Checkbox({ checked, onChange, className }) {
  return (
    <button
      role="checkbox"
      aria-checked={checked}
      onClick={() => onChange?.(!checked)}
      className={cn(
        "flex h-4 w-4 items-center justify-center rounded border transition-colors",
        checked ? "bg-primary border-primary text-primary-foreground" : "border-input bg-background",
        className
      )}
    >
      {checked && <Check className="h-3 w-3" strokeWidth={3} />}
    </button>
  );
}

/* ---------------- Separator ---------------- */
export function Separator({ className, orientation = "horizontal" }) {
  return <div className={cn(orientation === "horizontal" ? "h-px w-full" : "w-px h-full", "bg-border", className)} />;
}
