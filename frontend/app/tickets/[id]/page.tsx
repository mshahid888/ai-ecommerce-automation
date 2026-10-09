import { Suspense } from "react";
import TicketDetailView from "./TicketDetailView";

// Dynamic route (per-ticket id) rendered on demand at request time —
// opting out of instant-navigation validation so prerender doesn't block.
export const instant = false;

export default async function TicketDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <Suspense
      fallback={
        <p role="status" className="text-sm text-slate-600">
          Loading ticket …
        </p>
      }
    >
      <TicketDetailView id={id} />
    </Suspense>
  );
}
