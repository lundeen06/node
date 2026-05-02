import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";

export function BurnVectorEditor() {
  return (
    <Card>
      <CardHeader className="p-4 pb-2">
        <CardTitle className="text-xs">Δv vector (RIC, m/s)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 p-4 pt-0">
        <div className="grid grid-cols-3 gap-2">
          <div>
            <div className="mb-1 text-[10px] text-muted-foreground">Radial</div>
            <Input disabled defaultValue="0.052" className="h-9 font-mono text-xs" />
          </div>
          <div>
            <div className="mb-1 text-[10px] text-muted-foreground">In-track</div>
            <Input disabled defaultValue="-0.011" className="h-9 font-mono text-xs" />
          </div>
          <div>
            <div className="mb-1 text-[10px] text-muted-foreground">Cross-track</div>
            <Input disabled defaultValue="0.004" className="h-9 font-mono text-xs" />
          </div>
        </div>
        <Separator />
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>‖Δv‖</span>
          <span className="font-mono text-foreground">0.0540 m/s</span>
        </div>
        <p className="text-[10px] text-muted-foreground">Editor is read-only in the scaffold.</p>
      </CardContent>
    </Card>
  );
}
