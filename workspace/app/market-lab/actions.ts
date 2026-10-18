"use server";

import { revalidatePath } from "next/cache";

/** Ask the server to render the page again. Off feeds are still not called. */
export async function refreshFeeds(): Promise<void> {
  revalidatePath("/market-lab");
}
