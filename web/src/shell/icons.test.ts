import { describe, expect, it } from "vitest";
import { ChartColumn, CircleHelp, LifeBuoy, Plane, Sparkles, Gamepad2 } from "lucide-react";
import { DEFAULT_STARTER_ICON, iconKey, starterIcon } from "./icons";

describe("iconKey", () => {
  it("normalises every naming style to lucide kebab-case", () => {
    for (const n of ["life-buoy", "life_buoy", "LifeBuoy", "lifeBuoy", "Life Buoy", " LIFE-BUOY ", "LifeBuoyIcon"]) {
      expect(iconKey(n)).toBe("life-buoy");
    }
    expect(iconKey("Gamepad2")).toBe("gamepad-2");
    expect(iconKey("chart.bar")).toBe("chart-bar");
  });
});

describe("starterIcon", () => {
  it("maps the demo's icons (regression: life-buoy fell back to sparkles)", () => {
    expect(starterIcon("life-buoy")).toBe(LifeBuoy);
    expect(starterIcon("sparkles")).toBe(Sparkles);
    expect(starterIcon("chart")).toBe(ChartColumn);
    expect(starterIcon("plane")).toBe(Plane);
  });

  it("accepts lucide names in any case and common synonyms", () => {
    expect(starterIcon("LifeBuoy")).toBe(LifeBuoy);
    expect(starterIcon("support")).toBe(LifeBuoy);
    expect(starterIcon("help-circle")).toBe(CircleHelp);
    expect(starterIcon("CircleHelp")).toBe(CircleHelp);
    expect(starterIcon("gamepad-2")).toBe(Gamepad2);
    expect(starterIcon("Gamepad2")).toBe(Gamepad2);
  });

  it("falls back to a neutral icon for unknown or empty names", () => {
    expect(starterIcon("definitely-not-an-icon")).toBe(DEFAULT_STARTER_ICON);
    expect(starterIcon("")).toBe(DEFAULT_STARTER_ICON);
    expect(starterIcon(null)).toBe(DEFAULT_STARTER_ICON);
    expect(starterIcon(undefined)).toBe(DEFAULT_STARTER_ICON);
    expect(DEFAULT_STARTER_ICON).not.toBe(Sparkles);
  });
});
