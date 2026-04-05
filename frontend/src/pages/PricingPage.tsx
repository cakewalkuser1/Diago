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
    pricePeriod: null,
    icon: Zap,
    features: ["Text + audio diagnosis", "Failure mode ranking", "Confirm tests"],
  },
  {
    id: "diy" as const,
    name: "D.I.Y",
    limit: "50 diagnoses / month",
    description: "For home mechanics and hobbyists.",
    price: "$4.99",
    pricePeriod: "/month",
    priceId: "diy" as const,
    icon: Wrench,
    features: [
      "Everything in Free",
      "50 diagnoses per month",
      "DiagBot chat",
      "Repair guides & service manuals",
    ],
  },
  {
    id: "pro_mechanic" as const,
    name: "Pro Mechanic",
    limit: "500 diagnoses / month",
    description: "For professional mechanics.",
    price: "$19.99",
    pricePeriod: "/month",
    priceId: "pro_mechanic" as const,
    icon: Wrench,
    features: [
      "Everything in D.I.Y",
      "500 diagnoses per month",
      "Unlimited DiagBot chat",
      "Priority queue",
      "Dispatch & mechanic matching",
    ],
  },
  {
    id: "shop" as const,
    name: "Shop",
    limit: "10,000+ / month",
    description: "For shops and multi-technician teams.",
    price: "$99.99",
    pricePeriod: "/month",
    priceId: "shop" as const,
    icon: Building2,
    features: [
      "Everything in Pro Mechanic",
      "10,000+ diagnoses per month",
      "API access",
      "Shop analytics dashboard",
      "Multi-technician seats",
    ],
  },
];

export function PricingPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const session = useAuthStore((s) => s.session);
  const tier = useAuthStore((s) => s.tier);
  const [loadingTier, setLoadingTier] = useState<"diy" | "pro_mechanic" | "shop" | null>(null);
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

  const handleUpgrade = async (tierId: "diy" | "pro_mechanic" | "shop") => {
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
          <div className="mb-6 p-4 rounded-xl bg-surface0">
            <p className="text-sm text-text">
              Your plan:{" "}
              <strong className="capitalize" style={{ color: "var(--ds-primary-container)" }}>
                {subscription.tier}
              </strong>
              {" · "}
              <span style={{ color: "var(--ds-secondary-dim)" }}>{subscription.used}</span>
              {" of "}
              {subscription.limit} diagnoses used
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
                className={`rounded-xl p-5 flex flex-col transition-all duration-200 ${
                  isCurrent
                    ? "bg-surface1 shadow-[0_0_0_1.5px_var(--ds-primary-container),0_20px_40px_rgba(255,86,56,0.1)]"
                    : "bg-surface0 hover:bg-surface1 card-shadow"
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <Icon size={20} className="text-primary" />
                  <h2 className="font-semibold text-text">{t.name}</h2>
                </div>
                <p className="text-xs text-overlay0 mb-1">{t.limit}</p>
                <p className="text-sm text-subtext mb-4">{t.description}</p>
                {t.price != null && (
                  <div className="mb-3">
                    <span className="text-2xl font-bold text-text">{t.price}</span>
                    {t.pricePeriod && (
                      <span className="text-sm text-subtext ml-0.5">{t.pricePeriod}</span>
                    )}
                  </div>
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
