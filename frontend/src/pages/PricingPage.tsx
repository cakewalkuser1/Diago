import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Check, Loader2, Zap, Wrench, Building2 } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { Button } from "@/components/ui/Button";
import { useAuthStore } from "@/stores/authStore";
import { createCheckout, getSubscriptionStatus } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import { useToastStore } from "@/stores/toastStore";

const TIERS = [
  {
    id: "free" as const,
    name: "Free",
    limit: "3 diagnoses / month",
    description: "Full diagnostic flow, symptoms, codes, failure modes.",
    price: null,
    icon: Zap,
    features: ["Text + audio diagnosis", "Failure mode ranking", "Confirm tests"],
  },
  {
    id: "pro" as const,
    name: "Pro",
    limit: "500 diagnoses / month",
    description: "For DIYers and enthusiasts.",
    price: "Monthly subscription",
    priceId: "pro" as const,
    icon: Wrench,
    features: ["Everything in Free", "Higher diagnosis cap", "Priority support (coming soon)"],
  },
  {
    id: "premium" as const,
    name: "Premium",
    limit: "10,000+ / month",
    description: "For shops and power users.",
    price: "Higher monthly",
    priceId: "premium" as const,
    icon: Building2,
    features: ["Everything in Pro", "Highest cap", "API access (coming soon)"],
  },
];

export function PricingPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const session = useAuthStore((s) => s.session);
  const tier = useAuthStore((s) => s.tier);
  const [loadingTier, setLoadingTier] = useState<"pro" | "premium" | null>(null);
  const toast = useToastStore((s) => s.show);

  const success = searchParams.get("success");
  const cancelled = searchParams.get("cancel");

  const { data: subscription, refetch: refetchSubscription } = useQuery({
    queryKey: ["subscription", session?.access_token],
    queryFn: () => getSubscriptionStatus(session!.access_token),
    enabled: Boolean(session?.access_token),
  });

  useEffect(() => {
    if (success && session) refetchSubscription();
  }, [success, session, refetchSubscription]);

  const handleUpgrade = async (tierId: "pro" | "premium") => {
    if (!session?.access_token) {
      toast("Sign in to upgrade", "error");
      return;
    }
    setLoadingTier(tierId);
    try {
      const base = window.location.origin;
      const { checkout_url } = await createCheckout(
        {
          tier: tierId,
          success_url: `${base}/pricing?success=1`,
          cancel_url: `${base}/pricing?cancel=1`,
        },
        session.access_token
      );
      window.location.href = checkout_url;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Checkout failed";
      toast(msg, "error");
      setLoadingTier(null);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-mantle">
      <Header />
      <main className="flex-1 p-6 max-w-4xl mx-auto w-full">
        <h1 className="text-2xl font-bold text-text mb-1">Plans</h1>
        <p className="text-subtext text-sm mb-6">
          Diagnoses per calendar month. Upgrade anytime.
        </p>

        {success && (
          <div className="mb-4 p-3 rounded-lg bg-green/15 border border-green/30 text-green text-sm">
            <Check size={16} className="inline mr-2" />
            Payment successful. Your account has been upgraded. Refresh the app to see your new limit.
          </div>
        )}
        {cancelled && (
          <div className="mb-4 p-3 rounded-lg bg-yellow/15 border border-yellow/30 text-yellow text-sm">
            Checkout was cancelled. You can try again anytime.
          </div>
        )}

        {session && subscription && (
          <div className="mb-6 p-4 rounded-lg bg-surface0 border border-surface1">
            <p className="text-sm text-text">
              Your plan: <strong className="capitalize">{subscription.tier}</strong>
              {" · "}
              {subscription.used} of {subscription.limit} diagnoses used this month
              {" · "}
              <span className="text-overlay0">{subscription.remaining} remaining</span>
            </p>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-3">
          {TIERS.map((t) => {
            const Icon = t.icon;
            const isCurrent = tier === t.id;
            const isPaid = t.priceId != null;
            return (
              <div
                key={t.id}
                className={`
                  rounded-xl border p-5 flex flex-col
                  ${isCurrent ? "border-primary bg-primary/5" : "border-surface1 bg-surface0"}
                `}
              >
                <div className="flex items-center gap-2 mb-2">
                  <Icon size={20} className="text-primary" />
                  <h2 className="font-semibold text-text">{t.name}</h2>
                </div>
                <p className="text-xs text-overlay0 mb-1">{t.limit}</p>
                <p className="text-sm text-subtext mb-4">{t.description}</p>
                {t.price != null && (
                  <p className="text-sm font-medium text-text mb-3">{t.price}</p>
                )}
                <ul className="space-y-2 mb-6 flex-1">
                  {t.features.map((f) => (
                    <li key={f} className="flex items-center gap-2 text-xs text-subtext">
                      <Check size={14} className="text-green shrink-0" />
                      {f}
                    </li>
                  ))}
                </ul>
                {isCurrent && (
                  <Button variant="ghost" size="sm" className="w-full" disabled>
                    Current plan
                  </Button>
                )}
                {isPaid && !isCurrent && (
                  <Button
                    variant="primary"
                    size="sm"
                    className="w-full"
                    disabled={!session || loadingTier !== null}
                    onClick={() => handleUpgrade(t.priceId!)}
                  >
                    {loadingTier === t.priceId ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      "Upgrade"
                    )}
                  </Button>
                )}
                {t.id === "free" && !isCurrent && (
                  <p className="text-xs text-overlay0">Free tier is default when not subscribed.</p>
                )}
              </div>
            );
          })}
        </div>

        <div className="mt-8 flex gap-2">
          <Button variant="ghost" size="sm" onClick={() => navigate("/")}>
            Back to Home
          </Button>
          <Button variant="default" size="sm" onClick={() => navigate("/diagnose")}>
            Go to Diagnose
          </Button>
        </div>
      </main>
    </div>
  );
}
