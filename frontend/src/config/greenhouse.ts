export type GreenhouseDisplayMeta = {
  rawName: string;
  displayName: string;
  group: string;
  area: string;
  order: number;
};

const greenhouseDisplayEntries: GreenhouseDisplayMeta[] = [
  {
    rawName: "1号温室南区 climate - Greenhouse Climate",
    displayName: "1号温室南区",
    group: "1号温室",
    area: "南区",
    order: 1,
  },
  {
    rawName: "1号温室北区 climate - Greenhouse Climate",
    displayName: "1号温室北区",
    group: "1号温室",
    area: "北区",
    order: 2,
  },
  {
    rawName: "2号温室南区 climate - Greenhouse Climate",
    displayName: "2号温室南区",
    group: "2号温室",
    area: "南区",
    order: 3,
  },
  {
    rawName: "2号温室北区 climate - Greenhouse Climate",
    displayName: "2号温室北区",
    group: "2号温室",
    area: "北区",
    order: 4,
  },
  {
    rawName: "3号温室南区 climate - Greenhouse Climate",
    displayName: "3号温室南区",
    group: "3号温室",
    area: "南区",
    order: 5,
  },
  {
    rawName: "3号温室北区 climate - Greenhouse Climate",
    displayName: "3号温室北区",
    group: "3号温室",
    area: "北区",
    order: 6,
  },
  {
    rawName: "4号温室南区 climate - Greenhouse Climate",
    displayName: "4号温室南区",
    group: "4号温室",
    area: "南区",
    order: 7,
  },
  {
    rawName: "4号温室北区 climate - Greenhouse Climate",
    displayName: "4号温室北区",
    group: "4号温室",
    area: "北区",
    order: 8,
  },
  {
    rawName: "1号温室育苗区 climate - Greenhouse Climate",
    displayName: "育苗区",
    group: "1号温室",
    area: "育苗区",
    order: 9,
  },
  {
    rawName: "2号温室采摘区 climate - Greenhouse Climate",
    displayName: "采摘区",
    group: "2号温室",
    area: "采摘区",
    order: 10,
  },
  {
    rawName: "2号温室展示区 climate - Greenhouse Climate",
    displayName: "展示区",
    group: "2号温室",
    area: "展示区",
    order: 11,
  },
  {
    rawName: "水肥间",
    displayName: "水肥间",
    group: "灌溉与营养",
    area: "水肥间",
    order: 12,
  },
  {
    rawName: "Greenhouse 01",
    displayName: "1号温室南区",
    group: "1号温室",
    area: "南区",
    order: 1,
  },
  {
    rawName: "Greenhouse 02",
    displayName: "1号温室北区",
    group: "1号温室",
    area: "北区",
    order: 2,
  },
  {
    rawName: "Greenhouse 03",
    displayName: "2号温室南区",
    group: "2号温室",
    area: "南区",
    order: 3,
  },
  {
    rawName: "Greenhouse 04",
    displayName: "2号温室北区",
    group: "2号温室",
    area: "北区",
    order: 4,
  },
];

function normalizeZoneName(zone: string) {
  return zone
    .replace(/\s+/g, "")
    .replace(/climate-GreenhouseClimate/gi, "")
    .replace(/-(EC|pH)measurement/gi, "")
    .replace(/-GreenhouseClimate/gi, "")
    .trim();
}

function buildFertigationMeta(zone: string): GreenhouseDisplayMeta | null {
  const compactZone = zone.replace(/\s+/g, "");
  const match = compactZone.match(/^(\d+)号温室(.*?施肥机.+?)(?:-(?:EC|pH)measurement)?$/i);
  if (!match) {
    return null;
  }

  const greenhouseId = `${match[1]}号温室`;
  const deviceName = match[2];
  return {
    rawName: zone,
    displayName: `${greenhouseId}${deviceName}`,
    group: greenhouseId,
    area: "水肥系统",
    order: Number(match[1]) * 10 + 8,
  };
}

export const greenhouseDisplayMap: Record<string, GreenhouseDisplayMeta> = Object.fromEntries(
  greenhouseDisplayEntries.flatMap((entry) => {
    const normalizedKeys = new Set<string>([
      entry.rawName,
      normalizeZoneName(entry.rawName),
      entry.displayName,
      normalizeZoneName(entry.displayName),
    ]);

    return Array.from(normalizedKeys).map((key) => [key, entry] as const);
  }),
);

export function getGreenhouseDisplayMeta(zone: string): GreenhouseDisplayMeta {
  const normalizedZone = normalizeZoneName(zone);
  const fertigationMeta = buildFertigationMeta(zone) ?? buildFertigationMeta(normalizedZone);
  return (
    greenhouseDisplayMap[zone] ??
    greenhouseDisplayMap[normalizedZone] ?? {
      ...(fertigationMeta ?? {}),
      rawName: zone,
      displayName: fertigationMeta?.displayName ?? zone,
      group: fertigationMeta?.group ?? "未分组",
      area: fertigationMeta?.area ?? zone,
      order: fertigationMeta?.order ?? Number.MAX_SAFE_INTEGER,
    }
  );
}
