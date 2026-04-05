/**
 * Stripe PaymentElement for parts order payment.
 * Used in the dispatch flow when user selects part + retailer.
 */

import { useState } from "react";
import { PaymentElement, useStripe, useElements } from "@stripe/react-stripe-js";
import { Button } from "@/components/ui/Button";
import { Loader2 } from "lucide-react";

interface PartPaymentFormProps {
  amountCents: number;
  onSuccess: (paymentIntentId: string) => void;
  onError: (message: string) => void;
}

export function PartPaymentForm({ amountCents, onSuccess, onError }: PartPaymentFormProps) {
  const stripe = useStripe();
  const elements = useElements();
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stripe || !elements) return;
    setLoading(true);
    try {
      const { error, paymentIntent } = await stripe.confirmPayment({
        elements,
        confirmParams: {
          return_url: `${window.location.origin}`,
        },
        redirect: "if_required",
      });
      if (error) {
        onError(error.message ?? "Payment failed");
      } else if (paymentIntent?.status === "succeeded" && paymentIntent.id) {
        onSuccess(paymentIntent.id);
      } else {
        onError("Payment could not be confirmed");
      }
    } catch (err) {
      onError(err instanceof Error ? err.message : "Payment failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <PaymentElement />
      <p className="text-sm text-subtext">Amount: ${(amountCents / 100).toFixed(2)}</p>
      <Button type="submit" size="sm" variant="primary" disabled={!stripe || !elements || loading}>
        {loading ? <Loader2 size={14} className="animate-spin" /> : null}
        {loading ? "Processing…" : "Pay now"}
      </Button>
    </form>
  );
}
