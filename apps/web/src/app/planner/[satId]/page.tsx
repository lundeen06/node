import Link from "next/link";

import { BurnVectorEditor } from "@/components/planner/BurnVectorEditor";
import { ImpactPanel } from "@/components/planner/ImpactPanel";
import { ManeuverDiff } from "@/components/planner/ManeuverDiff";
import { TopBar } from "@/components/shell/TopBar";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function PlannerPage({ params }: { params: { satId: string } }) {
  const satId = decodeURIComponent(params.satId);

  return (
    <div className="min-h-screen bg-background">
      <TopBar />
      <div className="mx-auto max-w-6xl space-y-4 p-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="text-xs text-muted-foreground">Maneuver planner</div>
            <div className="text-lg font-semibold tracking-tight">
              <span className="font-mono text-foreground">{satId}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline">stub</Badge>
            <Link className="text-xs text-muted-foreground hover:text-foreground" href="/ops">
              ← Back to ops
            </Link>
          </div>
        </div>

        <Tabs defaultValue="dv" className="w-full">
          <TabsList>
            <TabsTrigger value="chat">Chat</TabsTrigger>
            <TabsTrigger value="constraints">Constraints</TabsTrigger>
            <TabsTrigger value="dv">Δv vector</TabsTrigger>
            <TabsTrigger value="target">Target state</TabsTrigger>
          </TabsList>

          <TabsContent value="chat">
            <Card>
              <CardHeader className="p-4 pb-2">
                <CardTitle className="text-xs">Planner chat</CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-0 text-sm text-muted-foreground">
                Operator ↔ agent transcript will live here. For now, this is a typed shell only.
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="constraints">
            <Card>
              <CardHeader className="p-4 pb-2">
                <CardTitle className="text-xs">Constraints</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 p-4 pt-0 text-sm text-muted-foreground">
                <div>
                  Keep-out volumes, ground exclusion windows, and thruster limits will render here as structured
                  controls.
                </div>
                <div className="font-mono text-xs text-foreground">max ‖Δv‖: 0.20 m/s · reserve fuel: 6.0 kg</div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="dv" className="space-y-3">
            <BurnVectorEditor />
            <ManeuverDiff />
          </TabsContent>

          <TabsContent value="target">
            <Card>
              <CardHeader className="p-4 pb-2">
                <CardTitle className="text-xs">Target state</CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-0 text-sm text-muted-foreground">
                Osculating target (Cartesian / equinoctial) and epoch will appear here for differential correction
                loops.
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        <ImpactPanel />
      </div>
    </div>
  );
}
