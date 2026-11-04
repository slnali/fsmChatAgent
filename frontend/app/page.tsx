import { Suspense } from "react";

import { ChatApp } from "@/components/ChatApp";

export default function Page() {
  return (
    <Suspense fallback={<p className="m-6 text-sm">Loading…</p>}>
      <ChatApp />
    </Suspense>
  );
}
