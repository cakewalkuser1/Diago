import { Star } from "lucide-react";

interface StarRatingProps {
  rating: number;
  max?: number;
  size?: number;
  className?: string;
}

export function StarRating({ rating, max = 5, size = 14, className = "" }: StarRatingProps) {
  const value = Math.min(max, Math.max(0, rating));
  const full = Math.floor(value);
  const hasHalf = value - full >= 0.5;

  return (
    <span className={`inline-flex items-center gap-0.5 text-amber-500 ${className}`} title={`${value.toFixed(1)} / ${max}`}>
      {Array.from({ length: full }, (_, i) => (
        <Star key={i} size={size} className="fill-current" />
      ))}
      {hasHalf && <Star size={size} className="fill-current opacity-70" />}
      {Array.from({ length: max - full - (hasHalf ? 1 : 0) }, (_, i) => (
        <Star key={`e-${i}`} size={size} className="text-overlay0" />
      ))}
    </span>
  );
}
