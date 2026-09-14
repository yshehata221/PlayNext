/**
 * Library search syntax: free text plus `key:value` tokens, so
 * "witcher genre:rpg platform:gog" filters as well as searching.
 * Kept separate from the page so it can be unit tested.
 */
export interface ParsedQuery {
  text: string[];
  genre?: string;
  platform?: string;
  status?: string;
  year?: string;
}

export function parseQuery(q: string): ParsedQuery {
  const out: ParsedQuery = { text: [] };
  for (const token of q.trim().split(/\s+/).filter(Boolean)) {
    const match = token.match(/^(genre|platform|status|year):(.+)$/i);
    if (match) {
      (out as unknown as Record<string, string>)[match[1].toLowerCase()] = match[2].toLowerCase();
    } else {
      out.text.push(token.toLowerCase());
    }
  }
  return out;
}

/**
 * Steam hosts artwork on two CDNs and puts newer games inside a hashed folder,
 * so a portrait URL can't reliably be constructed - the stored one is tried
 * first, then every derived variant. IGDB just needs its size swapped.
 */
const STEAM_HOSTS = [
  "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps",
  "https://cdn.cloudflare.steamstatic.com/steam/apps",
];

export function coverCandidates(url: string): string[] {
  if (url.includes("images.igdb.com")) {
    const hi = url.replace(/\/t_[a-z0-9_]+\//, "/t_cover_big_2x/");
    return Array.from(new Set([hi, url]));
  }
  const match = url.match(/\/steam\/apps\/(\d+)\//);
  if (!match) return [url];
  const appid = match[1];
  const derived = ["library_600x900.jpg", "library_hero.jpg", "header.jpg"]
    .flatMap((file) => STEAM_HOSTS.map((host) => `${host}/${appid}/${file}`));
  return Array.from(new Set([url, ...derived]));
}
