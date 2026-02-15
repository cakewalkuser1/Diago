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
        "rounded-[10px] border border-surface1 card-shadow",
        variant === "relaxed" && "bg-surface0/80 p-5",
        variant === "compact" && "bg-surface0/60 p-3",
        className
      )}
    >
      {title != null && (
        <h2 className="text-sm font-semibold text-text mb-3 flex items-center gap-2">
          {title}
        </h2>
      )}
      {children}
    </section>
  );
}
