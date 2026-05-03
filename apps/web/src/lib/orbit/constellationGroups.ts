export type FleetFolderId =
  | "iss"
  | "starlink"
  | "planet"
  | "kuiper"
  | "galileo"
  | "gps"
  | "beidou"
  | "other";

export const FOLDER_ORDER: FleetFolderId[] = [
  "iss",
  "starlink",
  "planet",
  "kuiper",
  "galileo",
  "gps",
  "beidou",
  "other",
];

export const FOLDER_LABELS: Record<FleetFolderId, string> = {
  iss: "ISS & crewed",
  starlink: "Starlink",
  planet: "Planet Labs",
  kuiper: "Kuiper / Amazon",
  galileo: "Galileo",
  gps: "GPS (NAVSTAR)",
  beidou: "BeiDou",
  other: "Other",
};

/** Heuristic folder from catalog strings (aligned with Space-Track name families + import ``purpose``). */
export function inferFleetFolder(name: string, purpose: string, satId: string): FleetFolderId {
  const n = name.toUpperCase();
  const p = (purpose || "").toUpperCase();
  const id = satId.toLowerCase();

  if (id === "iss" || id === "demo-iss" || n.includes("ZARYA") || (n.includes("ISS") && n.includes("SPACE STATION")))
    return "iss";
  if (n.includes("STARLINK")) return "starlink";
  if (
    n.includes("SKYSAT") ||
    n.includes("FLOCK") ||
    n.includes("DOVE") ||
    (n.includes("PLANET") && !n.includes("PLANETARY"))
  ) {
    return "planet";
  }
  if (n.includes("KUIPER") || n.includes("AMAZON")) return "kuiper";

  if (n.includes("GALILEO")) return "galileo";
  if (n.includes("BEIDOU")) return "beidou";
  if (n.includes("NAVSTAR") || n.includes("GPS BIIF") || n.includes("GPS BIII")) return "gps";

  if (p.includes("CREW") || p.includes("STATION")) return "iss";
  if (p.includes("STARLINK")) return "starlink";
  if (p.includes("PLANET") || p.includes("FLOCK")) return "planet";
  if (p.includes("GALILEO")) return "galileo";
  if (p.includes("BEIDOU")) return "beidou";
  if (p.includes("GPS") || p.includes("NAVSTAR")) return "gps";

  return "other";
}
