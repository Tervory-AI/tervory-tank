import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { readContent } from "@/lib/content";
import { RenderSections } from "@/sections/registry";

type RouteProps = { params: Promise<{ path?: string[] }> };
export const dynamic = "force-dynamic";

async function findPage({ params }: RouteProps) {
  const { path } = await params;
  const pathname = `/${(path || []).join("/")}`;
  return { pathname, page: readContent()?.pages.find((page) => page.path === pathname) };
}

export async function generateMetadata(props: RouteProps): Promise<Metadata> {
  const { page } = await findPage(props);
  return page ? { title: page.title } : {};
}

export default async function ContentRoute(props: RouteProps) {
  const { pathname, page } = await findPage(props);
  if (!page) {
    if (pathname === "/") return null;
    notFound();
  }
  return <RenderSections sections={page.sections} />;
}
