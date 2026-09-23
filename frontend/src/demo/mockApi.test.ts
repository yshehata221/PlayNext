import { describe, expect, it } from "vitest";
import { apiPath } from "./mockApi";

/**
 * The demo intercepts fetch, so it has to recognise an API call however the
 * bundle was built. Getting this wrong is silent: requests escape to the real
 * network and every page fails to load, which is what happened on the first
 * deploy.
 */
describe("apiPath", () => {
  it("matches the dev proxy prefix", () => {
    expect(apiPath("/api/library?sort=added")).toBe("/library?sort=added");
    expect(apiPath("http://localhost:5173/api/auth/me")).toBe("/auth/me");
  });

  it("matches bare API paths, which is what a demo build produces", () => {
    expect(apiPath("/auth/me")).toBe("/auth/me");
    expect(apiPath("/stats")).toBe("/stats");
    expect(apiPath("/recommendations?source=backlog&limit=8")).toBe("/recommendations?source=backlog&limit=8");
  });

  it("copes with the base path of a project site", () => {
    expect(apiPath("/playnext/library/12")).toBe("/library/12");
    expect(apiPath("https://someone.github.io/playnext/friends")).toBe("/friends");
  });

  it("leaves everything else alone", () => {
    expect(apiPath("https://images.igdb.com/igdb/image/upload/t_cover_big_2x/abc.jpg")).toBeNull();
    expect(apiPath("/assets/index-abc123.js")).toBeNull();
    expect(apiPath("https://fonts.googleapis.com/css2?family=Bricolage")).toBeNull();
  });

  it("does not match a longer word that merely starts with a root", () => {
    expect(apiPath("/authentication-docs")).toBeNull();
    expect(apiPath("/libraries.json")).toBeNull();
  });
});
