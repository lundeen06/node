import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function ImpactPanel() {
  return (
    <Card>
      <CardHeader className="p-4 pb-2">
        <CardTitle className="text-xs">Predicted impact</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 p-4 pt-0 text-xs text-muted-foreground">
        <p className="text-[11px] leading-relaxed">
          No conjunction screening results available. Wire the conjunction API when ready.
        </p>
      </CardContent>
    </Card>
  );
}
