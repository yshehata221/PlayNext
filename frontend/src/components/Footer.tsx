/**
 * Attribution. IGDB's and Steam's terms both require crediting them when their
 * data is displayed, and it's the honest thing to do regardless - almost every
 * cover, description and trailer in here came from one of them.
 */
export default function Footer() {
  return (
    <footer className="mt-16 border-t border-line px-6 py-8 text-xs text-fog sm:px-8">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2">
        <span className="font-semibold text-snow/80">PlayNext</span>
        <span>
          Game data from{" "}
          <a href="https://www.igdb.com" target="_blank" rel="noreferrer" className="underline hover:text-snow">IGDB</a>
          {" "}and the{" "}
          <a href="https://store.steampowered.com" target="_blank" rel="noreferrer" className="underline hover:text-snow">Steam</a>
          {" "}and{" "}
          <a href="https://www.xbox.com" target="_blank" rel="noreferrer" className="underline hover:text-snow">Microsoft</a>
          {" "}stores.
        </span>
        <span>Artwork and trademarks belong to their respective publishers.</span>
        <a href="https://github.com/yshehata221" target="_blank" rel="noreferrer" className="ml-auto underline hover:text-snow">Source</a>
      </div>
    </footer>
  );
}
