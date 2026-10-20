// Stripe webhook for the Workspace. Server-side only.
// Stripe's library checks the signature. The same event id is applied once.

import Stripe from "stripe";

export type WebhookEffect = (event: { id: string; type: string }) => void | Promise<void>;

export type WebhookStore = {
  /** True when this caller is the first to take the event id. */
  claim(eventId: string): boolean;
  /** Drop a claim when handling failed, so Stripe's retry can run once. */
  release(eventId: string): void;
};

export function memoryWebhookStore(): WebhookStore {
  const seen = new Set<string>();
  return {
    claim(eventId: string) {
      if (seen.has(eventId)) return false;
      seen.add(eventId);
      return true;
    },
    release(eventId: string) {
      seen.delete(eventId);
    },
  };
}

/** One Workspace process. A repeat delivery to this process does not run the effect again. */
const processStore = memoryWebhookStore();

export type WebhookResponse = {
  status: number;
  body: { received?: boolean; duplicate?: boolean; error?: string };
};

export async function receiveStripeWebhook(input: {
  rawBody: string;
  signature: string | null;
  secret: string | undefined;
  store?: WebhookStore;
  effect?: WebhookEffect;
}): Promise<WebhookResponse> {
  const secret = input.secret?.trim() ?? "";
  if (!secret) {
    return { status: 500, body: { error: "Billing webhook is not configured." } };
  }
  const signature = input.signature?.trim() ?? "";
  if (!signature) {
    return { status: 400, body: { error: "Missing Stripe signature." } };
  }

  let event: Stripe.Event;
  try {
    event = Stripe.webhooks.constructEvent(input.rawBody, signature, secret);
  } catch {
    return { status: 400, body: { error: "Invalid Stripe signature." } };
  }

  const eventId = typeof event.id === "string" ? event.id.trim() : "";
  if (!eventId) {
    return { status: 400, body: { error: "Invalid Stripe event." } };
  }

  const store = input.store ?? processStore;
  if (!store.claim(eventId)) {
    return { status: 200, body: { received: true, duplicate: true } };
  }

  try {
    if (input.effect) await input.effect({ id: eventId, type: event.type });
  } catch {
    store.release(eventId);
    return { status: 500, body: { error: "Billing webhook could not be recorded." } };
  }

  return { status: 200, body: { received: true } };
}
