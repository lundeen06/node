import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { MOCK_CONJUNCTION } from "@/lib/mock-data";

export function ImpactPanel() {
  return (
    <Card>
      <CardHeader className="p-4 pb-2">
        <CardTitle className="text-xs">Predicted impact (mock)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 p-4 pt-0 text-xs text-muted-foreground">
        <div className="flex items-center justify-between">
          <span>Post-burn Pc (Foster)</span>
          <span className="font-mono text-foreground">3.1e-06</span>
        </div>
        <div className="flex items-center justify-between">
          <span>Miss distance @ TCA</span>
          <span className="font-mono text-foreground">2.84 km</span>
        </div>
        <Separator />
        <div className="text-[11px] leading-relaxed">
          Screening window: <span className="font-mono text-foreground">±6h</span> around{" "}
          <span className="font-mono text-foreground">{MOCK_CONJUNCTION.tca.instant}</span>. Fuel delta (mock):{" "}
          <span className="font-mono text-foreground">0.62 kg</span>.
        </div>
      </CardContent>
    </Card>
  );
}
