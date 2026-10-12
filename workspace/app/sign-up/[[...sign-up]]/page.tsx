import { SignUp } from "@clerk/nextjs";

export default function Page() {
  return (
    <div style={{ display: "grid", placeItems: "center", minHeight: "70vh" }}>
      <SignUp />
    </div>
  );
}
