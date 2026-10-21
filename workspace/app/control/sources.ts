import "server-only";
import { clerkClient } from "@clerk/nextjs/server";
import Stripe from "stripe";

export type Signup = { id: string; name: string; company: string | null; country: string | null; plan: string | null; createdAt: number };
export type Signups = { total: number; recent: Signup[]; days: { day: string; value: number }[] };
const text = (value: unknown) => typeof value === "string" && value.trim() ? value : null;

export async function signupSource(): Promise<Signups> {
  const client = await clerkClient();
  const [total, users] = await Promise.all([
    client.users.getCount(), client.users.getUserList({ limit: 100, orderBy: "-created_at" }),
  ]);
  // A latest-100 sample is not used as a whole-population sparkline.
  const counts = new Map<string, number>();
  for (const user of users.data) {
    const day = new Date(user.createdAt).toISOString().slice(0, 10);
    counts.set(day, (counts.get(day) ?? 0) + 1);
  }
  return { total, days: total <= users.data.length ? [...counts].map(([day, value]) => ({ day, value })).sort((a,b) => a.day.localeCompare(b.day)) : [],
    recent: users.data.slice(0, 6).map(user => ({
      id: user.id, name: [user.firstName, user.lastName].filter(Boolean).join(" ") || "Name not provided",
      company: text(user.publicMetadata.company), country: text(user.publicMetadata.country),
      plan: text(user.publicMetadata.plan), createdAt: user.createdAt,
    })) };
}

export async function payingSource(): Promise<number> {
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) throw new Error("Stripe is not connected.");
  const stripe = new Stripe(key, { maxNetworkRetries: 1, timeout: 10000 });
  const customers = new Set<string>();
  for await (const subscription of stripe.subscriptions.list({ status: "active", limit: 100 })) {
    if (subscription.items.data.some(item => (item.price.unit_amount ?? 0) > 0)) {
      customers.add(typeof subscription.customer === "string" ? subscription.customer : subscription.customer.id);
    }
  }
  return customers.size;
}
