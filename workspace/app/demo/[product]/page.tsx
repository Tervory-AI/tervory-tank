import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { DEMO_PRODUCTS, demoProductFor } from "@/lib/demo-fixtures";
import { DemoView } from "./demo-view";

export const dynamicParams = false;

export function generateStaticParams() {
  return DEMO_PRODUCTS.map((p) => ({ product: p.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ product: string }> }): Promise<Metadata> {
  const product = demoProductFor((await params).product);
  return { title: product ? `${product.name} demo · Tervory` : "Tervory" };
}

export default async function DemoPage({ params }: { params: Promise<{ product: string }> }) {
  const product = demoProductFor((await params).product);
  if (!product) notFound();
  return <DemoView product={product} />;
}
