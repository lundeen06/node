export function OrbitLayer() {
  return (
    <div className="absolute inset-0 opacity-40">
      <svg viewBox="0 0 100 100" className="h-full w-full" preserveAspectRatio="none">
        <path
          d="M5 52 C 25 30, 75 74, 95 48"
          fill="none"
          stroke="hsl(210 80% 60% / 0.35)"
          strokeWidth="0.6"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </div>
  );
}
