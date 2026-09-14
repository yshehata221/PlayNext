"""
Microsoft Store catalogue lookup - public and keyless. Given a Store product id
(the 9N... code in a store URL, also found in each Game Pass install's
MicrosoftGame.config), returns the portrait poster art the Xbox app shows.
"""
import logging

import httpx

from .cache import cached

log = logging.getLogger("uvicorn.error")

CATALOG = "https://displaycatalog.mp.microsoft.com/v7.0/products"

# look like a browser: the same request works from Chrome, and some Microsoft
# endpoints are picky about non-browser user agents and extra parameters
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Accept": "application/json",
}

# named art types, in order of preference. Poster/BoxArt/BrandedKeyArt are
# portrait; FeaturePromotionalSquareArt/Tile are square; the Hero ones are the
# landscape tiles the Xbox app itself falls back to. Small indie listings often
# have nothing but the landscape art.
PURPOSES = (
    "Poster", "BoxArt", "BrandedKeyArt",
    "FeaturePromotionalSquareArt", "Tile",
    "TitledHeroArt", "SuperHeroArt", "Hero", "Logo",
)


@cached(ttl=86400)
def fetch(store_id: str, market: str) -> list[dict]:
    lang = "neutral" if market == "neutral" else f"en-{market},neutral"
    r = httpx.get(
        CATALOG,
        params={"bigIds": store_id, "market": market, "languages": lang},
        headers=HEADERS,
        timeout=6,
    )
    r.raise_for_status()
    return r.json().get("Products", [])


def lookup(store_id: str, market: str = "GB") -> dict | None:
    """Some listings only resolve in certain markets, so try a few before giving up."""
    if not store_id or set(store_id) == {"0"}:
        return None
    for mkt in dict.fromkeys([market, "US", "neutral"]):
        try:
            products = fetch(store_id, mkt)
        except (httpx.HTTPError, ValueError) as e:
            log.warning("Microsoft Store lookup failed for %s (%s): %s", store_id, mkt, e)
            continue
        if products and poster_url(products[0]):
            log.info("Microsoft Store: %s -> %s", store_id, title(products[0]))
            return products[0]
        log.warning("Microsoft Store: %s returned %s in %s", store_id, "no product" if not products else "no usable image", mkt)
    return None


def images(product: dict) -> list[dict]:
    return product.get("LocalizedProperties", [{}])[0].get("Images", [])


def _url(img: dict) -> str:
    uri = img["Uri"]
    return f"https:{uri}" if uri.startswith("//") else uri


def poster_url(product: dict) -> str | None:
    imgs = [i for i in images(product) if i.get("Uri")]
    for purpose in PURPOSES:
        best = max((i for i in imgs if i.get("ImagePurpose") == purpose), key=lambda i: i.get("Height", 0), default=None)
        if best:
            return _url(best)
    # unknown purposes: take the tallest portrait-shaped image, then any square
    portrait = [i for i in imgs if i.get("Height", 0) > i.get("Width", 0) and i.get("ImagePurpose") != "Screenshot"]
    if portrait:
        return _url(max(portrait, key=lambda i: i["Height"]))
    square = [i for i in imgs if i.get("Height") == i.get("Width") and i.get("ImagePurpose") != "Screenshot"]
    if square:
        return _url(max(square, key=lambda i: i["Height"]))
    anything = [i for i in imgs if i.get("ImagePurpose") not in ("Screenshot", "Trailer")]
    if anything:
        return _url(max(anything, key=lambda i: i.get("Height", 0)))
    return None


def title(product: dict) -> str | None:
    return product.get("LocalizedProperties", [{}])[0].get("ProductTitle")


def describe(store_id: str) -> None:
    """Debug helper: python -c "from app.services import msstore; msstore.describe('9PJRQHMCFQGS')" """
    for mkt in ("GB", "US", "neutral"):
        try:
            products = fetch(store_id, mkt)
        except Exception as e:
            print(f"{mkt}: error {e}")
            continue
        if not products:
            print(f"{mkt}: no product")
            continue
        print(f"{mkt}: {title(products[0])}")
        for i in images(products[0]):
            print(f"   {i.get('ImagePurpose'):32} {i.get('Width')}x{i.get('Height')}  {_url(i)[:80]}")
        print(f"   -> picked: {poster_url(products[0])}")
