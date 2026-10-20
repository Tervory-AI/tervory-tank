"use client";
import { useClerk } from "@clerk/nextjs";
export function RadixSettings() {
  const { openUserProfile } = useClerk();
  return <button type="button" onClick={() => openUserProfile()}>Settings</button>;
}
