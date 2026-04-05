import { type ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

type Variant = "default" | "primary" | "secondary" | "danger" | "ghost" | "green" | "red" | "orange";
type Size = "sm" | "md" | "lg" | "xl";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const variantStyles: Record<Variant, string> = {
  default:
    "bg-surface0 text-text hover:bg-surface1",
  primary:
    "bg-gradient-primary text-white font-semibold hover:shadow-[0_0_22px_rgba(255,86,56,0.4)] active:scale-[0.98]",
  secondary:
    "bg-[var(--ds-secondary-dim)] text-[#0a0a0a] font-semibold hover:shadow-[0_0_22px_rgba(0,218,243,0.4)] active:scale-[0.98]",
  danger:
    "bg-red text-white font-semibold hover:opacity-90",
  ghost:
    "bg-transparent text-subtext hover:bg-surface0 hover:text-text",
  green:
    "bg-green text-[#0a0a0a] font-semibold hover:opacity-90",
  red:
    "bg-red text-white font-semibold hover:opacity-90",
  orange:
    "bg-gradient-primary text-white font-semibold hover:shadow-[0_0_22px_rgba(255,86,56,0.4)] active:scale-[0.98]",
};

const sizeStyles: Record<Size, string> = {
  sm: "px-3 py-1.5 text-xs rounded-lg",
  md: "px-4 py-2 text-sm rounded-lg",
  lg: "px-6 py-2.5 text-sm rounded-lg",
  xl: "px-7 py-3.5 text-base rounded-xl",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "default", size = "md", className, disabled, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center gap-2 font-medium transition-all duration-200",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ds-primary-container)]/50",
        "disabled:opacity-40 disabled:pointer-events-none cursor-pointer",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      disabled={disabled}
      {...props}
    />
  )
);

Button.displayName = "Button";
