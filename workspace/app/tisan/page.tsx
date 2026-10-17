import { auth } from "@clerk/nextjs/server";
import { isListedFounder } from "../review/founder";
import { Tisan } from "./tisan";

export const dynamic = "force-dynamic";

export default async function TisanPage() {
  let founder = false;
  try {
    const { userId } = await auth();
    founder = isListedFounder(userId, process.env.TERVORY_ADMIN_USER_IDS);
  } catch {
    founder = false;
  }
  return <Tisan founder={founder} />;
}
