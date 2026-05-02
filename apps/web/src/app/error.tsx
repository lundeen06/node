"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[app/error]", error);
  }, [error]);

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 bg-background p-8 text-center">
      <h1 className="text-lg font-semibold text-foreground">Something went wrong</h1>
      <p className="max-w-md text-sm text-muted-foreground">{error.message}</p>
      <button
        type="button"
        className="rounded-md border border-border bg-card px-4 py-2 text-sm font-medium text-foreground hover:bg-muted"
        onClick={() => reset()}
      >
        Try again
      </button>
    </div>
  );
}
