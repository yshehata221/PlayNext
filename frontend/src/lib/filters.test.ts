import { describe, expect, it } from "vitest";
import { coverCandidates, parseQuery } from "./filters";

describe("parseQuery", () => {
  it("splits free text from key:value tokens", () => {
    const q = parseQuery("red dead genre:Adventure platform:steam");
    expect(q.text).toEqual(["red", "dead"]);
    expect(q.genre).toBe("adventure");
    expect(q.platform).toBe("steam");
  });

  it("ignores unknown keys, treating them as text", () => {
    expect(parseQuery("publisher:rockstar").text).toEqual(["publisher:rockstar"]);
  });

  it("copes with extra whitespace and an empty string", () => {
    expect(parseQuery("   ").text).toEqual([]);
    expect(parseQuery("  hades   status:playing ").status).toBe("playing");
  });

  it("is case insensitive on keys and values", () => {
    expect(parseQuery("GENRE:RPG").genre).toBe("rpg");
  });
});

describe("coverCandidates", () => {
  it("asks IGDB for the 2x cover before the stored size", () => {
    const [first, second] = coverCandidates("https://images.igdb.com/igdb/image/upload/t_cover_big/abc.jpg");
    expect(first).toContain("t_cover_big_2x");
    expect(second).toContain("t_cover_big/");
  });

  it("tries the stored Steam URL first, then derives the other sizes", () => {
    const urls = coverCandidates(
      "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/730/hash/library_600x900.jpg",
    );
    expect(urls[0]).toContain("/hash/library_600x900.jpg");
    // the header always exists, so it must be in the chain as a last resort
    expect(urls.some((u) => u.endsWith("/730/header.jpg"))).toBe(true);
    expect(new Set(urls).size).toBe(urls.length); // no duplicates
  });

  it("leaves unrecognised URLs alone", () => {
    expect(coverCandidates("https://example.com/art.png")).toEqual(["https://example.com/art.png"]);
  });
});
