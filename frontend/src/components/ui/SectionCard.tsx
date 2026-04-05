import { cn } from "@/lib/utils";

type DensityVariant = "relaxed" | "compact";

interface SectionCardProps {
  title?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  variant?: DensityVariant;
}

export function SectionCard({ title, children, className, variant = "relaxed" }: SectionCardProps) {
  return (
    <section
      className={cn(
        "rounded-xl card-shadow dashboard-card",
        variant === "relaxed" && "bg-surface0 p-5",
        variant === "compact" && "bg-surface0/70 p-3",
        className
      )}
    >
      {title != null && (
        <h2 className="text-xs font-medium text-subtext mb-3 flex items-center gap-2 tracking-widest uppercase">
          {title}
        </h2>
      )}
      {children}
    </section>
  );
}
