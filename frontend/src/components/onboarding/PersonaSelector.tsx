import { Zap, Wrench, Building2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { usePersona } from "@/contexts/PersonaContext";
import type { PersonaTier } from "@/stores/personaStore";
import { cn } from "@/lib/utils";

const TIERS: {
  id: PersonaTier;
  title: string;
  description: string;
  icon: typeof Zap;
}[] = [
  {
    id: "onetime",
    title: "I just need a quick answer",
    description: "Simple questions, plain English results. Get an answer in under 60 seconds.",
    icon: Zap,
  },
  {
    id: "diy",
    title: "I want to learn and fix it myself",
    description: "Structured guidance with optional technical details. Learn as you diagnose.",
    icon: Wrench,
  },
  {
    id: "enterprise",
    title: "I run a shop / need full details",
    description: "All data visible, keyboard shortcuts, repair logging, and shop analytics.",
    icon: Building2,
  },
];

interface PersonaSelectorProps {
  onSelect?: () => void;
  compact?: boolean;
}

export function PersonaSelector({ onSelect, compact = false }: PersonaSelectorProps) {
  const { setPersonaTier } = usePersona();

  const handleSelect = (tier: PersonaTier) => {
    setPersonaTier(tier);
    onSelect?.();
  };

  if (compact) {
    return (
      <div className="flex flex-wrap gap-2">
        {TIERS.map(({ id, title, icon: Icon }) => (
          <Button
            key={id}
            variant="default"
            size="sm"
            onClick={() => handleSelect(id)}
            className="gap-2"
          >
            <Icon size={14} />
            {title}
          </Button>
        ))}
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <p className="text-center text-subtext text-sm">
        Choose how you want to use Autopilot
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {TIERS.map(({ id, title, description, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => handleSelect(id)}
            className={cn(
              "flex flex-col items-start gap-3 p-5 rounded-xl border border-surface1/80",
              "bg-mantle/80 hover:bg-mantle hover:border-primary/40",
              "text-left transition-all duration-150",
              "focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
            )}
          >
            <div className="p-2 rounded-lg bg-primary/10">
              <Icon size={24} className="text-primary" />
            </div>
            <div>
              <h3 className="font-semibold text-text mb-1">{title}</h3>
              <p className="text-sm text-subtext">{description}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
