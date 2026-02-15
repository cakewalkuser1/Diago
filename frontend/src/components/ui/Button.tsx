import { type ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

type Variant = "default" | "primary" | "danger" | "ghost" | "green" | "red";
type Size = "sm" | "md" | "lg" | "xl";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const variantStyles: Record<Variant, string> = {
  default:
    "bg-surface0 text-text hover:bg-surface1 border border-surface1",
  primary:
    "bg-gradient-primary text-white hover:opacity-90 font-semibold",
  danger:
    "bg-red text-crust hover:opacity-90 font-semibold",
  ghost:
    "bg-transparent text-subtext hover:bg-surface0 hover:text-text",
  green:
    "bg-green text-crust hover:opacity-90 font-semibold",
  red:
    "bg-red text-crust hover:opacity-90 font-semibold",
};

const sizeStyles: Record<Size, string> = {
  sm: "px-2.5 py-1 text-xs rounded-lg",
  md: "px-4 py-2 text-sm rounded-lg",
  lg: "px-6 py-2.5 text-base rounded-lg",
  xl: "px-8 py-4 text-lg rounded-xl",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "default", size = "md", className, disabled, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center gap-2 font-medium transition-all duration-150",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50",
        "disabled:opacity-50 disabled:pointer-events-none cursor-pointer",
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
