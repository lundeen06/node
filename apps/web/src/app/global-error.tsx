"use client";

/**
 * Root-level error UI (must define its own <html> / <body>).
 * Prevents “missing required error components” when the root layout throws.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: "system-ui", padding: 24, background: "#09090b", color: "#fafafa" }}>
        <h1 style={{ fontSize: 18 }}>Application error</h1>
        <p style={{ opacity: 0.8, fontSize: 14 }}>{error.message}</p>
        <button
          type="button"
          style={{ marginTop: 16, padding: "8px 16px", cursor: "pointer" }}
          onClick={() => reset()}
        >
          Try again
        </button>
      </body>
    </html>
  );
}
