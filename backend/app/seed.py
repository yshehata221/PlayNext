"""
Seed a starter catalogue so the app is usable (and the recommender has something
to chew on) before any IGDB/Steam keys are configured.

Run:  python -m app.seed
Optionally also creates a demo account with a rated library:  python -m app.seed --demo

Hours are rough HowLongToBeat-style figures from memory - treat them as
placeholders, not data. Real metadata comes in via IGDB search.
"""
import sys

from .auth import hash_password
from .database import Base, SessionLocal, engine
from .models import Game, LibraryEntry, Status, User
from .services.igdb import slugify
from .services.steam import steam_cover

SP, MP, COOP = "Single player", "Multiplayer", "Co-operative"
FP, TP, ISO = "First person", "Third person", "Bird view / Isometric"

# title, developer, year, genres, themes, perspectives, modes, hours_main, hours_complete, session_min, critic
GAMES = [
    ("Red Dead Redemption 2", "Rockstar Games", 2018, ["Adventure", "Shooter"], ["Open world", "Action", "Historical", "Drama"], [FP, TP], [SP, MP], 50, 175, 90, 97),
    ("Grand Theft Auto V", "Rockstar North", 2013, ["Adventure", "Shooter", "Racing"], ["Open world", "Action", "Comedy"], [FP, TP], [SP, MP], 31, 80, 60, 96),
    ("Cyberpunk 2077", "CD Projekt Red", 2020, ["Role-playing (RPG)", "Shooter"], ["Open world", "Science fiction", "Action"], [FP], [SP], 25, 100, 75, 86),
    ("The Witcher 3: Wild Hunt", "CD Projekt Red", 2015, ["Role-playing (RPG)", "Adventure"], ["Open world", "Fantasy", "Action"], [TP], [SP], 52, 173, 90, 92),
    ("Elden Ring", "FromSoftware", 2022, ["Role-playing (RPG)", "Adventure"], ["Open world", "Fantasy", "Action"], [TP], [SP, MP, COOP], 60, 133, 90, 96),
    ("Baldur's Gate 3", "Larian Studios", 2023, ["Role-playing (RPG)", "Strategy", "Turn-based strategy (TBS)"], ["Fantasy", "Drama"], [ISO], [SP, COOP], 66, 150, 120, 96),
    ("Hades", "Supergiant Games", 2020, ["Role-playing (RPG)", "Hack and slash/Beat 'em up", "Indie"], ["Fantasy", "Action"], [ISO], [SP], 22, 95, 30, 93),
    ("Hollow Knight", "Team Cherry", 2017, ["Platform", "Adventure", "Indie"], ["Fantasy", "Action"], ["Side view"], [SP], 27, 63, 45, 90),
    ("Stardew Valley", "ConcernedApe", 2016, ["Simulator", "Role-playing (RPG)", "Indie"], ["Fantasy", "Non-fiction"], [ISO], [SP, COOP], 53, 155, 45, 89),
    ("Starfield", "Bethesda Game Studios", 2023, ["Role-playing (RPG)", "Shooter"], ["Open world", "Science fiction"], [FP, TP], [SP], 34, 140, 75, 83),
    ("The Elder Scrolls V: Skyrim", "Bethesda Game Studios", 2011, ["Role-playing (RPG)", "Adventure"], ["Open world", "Fantasy", "Action"], [FP, TP], [SP], 34, 230, 75, 94),
    ("Mass Effect Legendary Edition", "BioWare", 2021, ["Role-playing (RPG)", "Shooter"], ["Science fiction", "Action", "Drama"], [TP], [SP], 95, 150, 90, 87),
    ("Disco Elysium", "ZA/UM", 2019, ["Role-playing (RPG)", "Adventure", "Indie"], ["Drama", "Mystery"], [ISO], [SP], 22, 45, 60, 91),
    ("Assassin's Creed Valhalla", "Ubisoft Montreal", 2020, ["Role-playing (RPG)", "Adventure"], ["Open world", "Historical", "Action", "Stealth"], [TP], [SP], 61, 140, 75, 80),
    ("Ghost of Tsushima", "Sucker Punch Productions", 2020, ["Adventure"], ["Open world", "Historical", "Action", "Stealth"], [TP], [SP, MP], 25, 62, 75, 86),
    ("God of War Ragnarök", "Santa Monica Studio", 2022, ["Adventure", "Hack and slash/Beat 'em up"], ["Fantasy", "Action", "Drama"], [TP], [SP], 26, 55, 60, 94),
    ("Horizon Forbidden West", "Guerrilla Games", 2022, ["Role-playing (RPG)", "Adventure"], ["Open world", "Science fiction", "Action"], [TP], [SP], 30, 90, 75, 88),
    ("Portal 2", "Valve", 2011, ["Puzzle", "Platform"], ["Science fiction", "Comedy"], [FP], [SP, COOP], 9, 20, 45, 95),
    ("Half-Life: Alyx", "Valve", 2020, ["Shooter", "Adventure"], ["Science fiction", "Action", "Horror"], [FP, "Virtual Reality"], [SP], 12, 20, 60, 93),
    ("Celeste", "Maddy Makes Games", 2018, ["Platform", "Indie"], ["Drama"], ["Side view"], [SP], 8, 37, 30, 92),
    ("Slay the Spire", "Mega Crit", 2019, ["Card & Board Game", "Strategy", "Indie"], ["Fantasy"], ["Side view"], [SP], 25, 140, 30, 89),
    ("Civilization VI", "Firaxis Games", 2016, ["Strategy", "Turn-based strategy (TBS)", "Simulator"], ["Historical"], [ISO], [SP, MP], 22, 130, 120, 88),
    ("Factorio", "Wube Software", 2020, ["Simulator", "Strategy", "Indie"], ["Science fiction", "Survival"], [ISO], [SP, COOP], 45, 190, 120, 90),
    ("Counter-Strike 2", "Valve", 2023, ["Shooter"], ["Action"], [FP], [MP], None, None, 45, 80),
    ("Overwatch 2", "Blizzard Entertainment", 2022, ["Shooter"], ["Action", "Science fiction"], [FP], [MP], None, None, 30, 79),
    ("Resident Evil 4", "Capcom", 2023, ["Shooter", "Adventure"], ["Horror", "Action", "Survival"], [TP], [SP], 16, 33, 60, 92),
    ("Alan Wake 2", "Remedy Entertainment", 2023, ["Adventure", "Shooter"], ["Horror", "Mystery", "Drama"], [TP], [SP], 20, 33, 60, 89),
    ("Metaphor: ReFantazio", "Studio Zero", 2024, ["Role-playing (RPG)", "Turn-based strategy (TBS)"], ["Fantasy", "Drama"], [TP], [SP], 75, 110, 90, 93),
    ("Persona 5 Royal", "Atlus", 2019, ["Role-playing (RPG)", "Turn-based strategy (TBS)"], ["Drama", "Mystery"], [TP], [SP], 103, 143, 90, 95),
    ("Dave the Diver", "Mintrocket", 2023, ["Adventure", "Simulator", "Indie"], ["Comedy", "Survival"], ["Side view"], [SP], 27, 55, 45, 90),
    ("Balatro", "LocalThunk", 2024, ["Card & Board Game", "Indie"], [], ["Side view"], [SP], 30, 100, 20, 90),
    ("Max Payne 3", "Rockstar Studios", 2012, ["Shooter"], ["Action", "Drama"], [TP], [SP, MP], 10, 25, 45, 86),
    ("L.A. Noire", "Team Bondi", 2011, ["Adventure"], ["Mystery", "Historical", "Drama"], [TP], [SP], 20, 33, 60, 89),
    ("Bully", "Rockstar Vancouver", 2006, ["Adventure"], ["Open world", "Comedy"], [TP], [SP], 15, 30, 45, 87),
    ("Sekiro: Shadows Die Twice", "FromSoftware", 2019, ["Adventure", "Hack and slash/Beat 'em up"], ["Historical", "Action", "Fantasy"], [TP], [SP], 30, 70, 60, 90),
    ("Dark Souls III", "FromSoftware", 2016, ["Role-playing (RPG)", "Adventure"], ["Fantasy", "Action"], [TP], [SP, MP], 32, 100, 60, 89),
    ("Kingdom Come: Deliverance II", "Warhorse Studios", 2025, ["Role-playing (RPG)", "Adventure"], ["Open world", "Historical", "Drama"], [FP], [SP], 60, 140, 90, 88),
    ("Death Stranding", "Kojima Productions", 2019, ["Adventure"], ["Open world", "Science fiction", "Drama", "Survival"], [TP], [SP], 40, 115, 75, 82),
]

# Steam app IDs, so we can pull cover art from Steam's public CDN without an API key.
# Games not listed here (Epic exclusives etc.) show a title tile until IGDB fills them in.
STEAM_APPIDS = {
    'Red Dead Redemption 2': 1174180,
    'Grand Theft Auto V': 271590,
    'Cyberpunk 2077': 1091500,
    'The Witcher 3: Wild Hunt': 292030,
    'Elden Ring': 1245620, "Baldur's Gate 3": 1086940,
    'Hades': 1145360,
    'Hollow Knight': 367520,
    'Stardew Valley': 413150,
    'Starfield': 1716740,
    'The Elder Scrolls V: Skyrim': 489830,
    'Mass Effect Legendary Edition': 1328670,
    'Disco Elysium': 632470, "Assassin's Creed Valhalla": 2208920,
    'Ghost of Tsushima': 2215430,
    'God of War Ragnarök': 2322010,
    'Horizon Forbidden West': 2420110,
    'Portal 2': 620,
    'Half-Life: Alyx': 546560,
    'Celeste': 504230,
    'Slay the Spire': 646570,
    'Civilization VI': 289070,
    'Factorio': 427520,
    'Counter-Strike 2': 730,
    'Overwatch 2': 2357570,
    'Resident Evil 4': 2050650,
    'Metaphor: ReFantazio': 2679460,
    'Persona 5 Royal': 1687950,
    'Dave the Diver': 1868140,
    'Balatro': 2379780,
    'Max Payne 3': 204100,
    'L.A. Noire': 110800,
    'Bully': 12200,
    'Sekiro: Shadows Die Twice': 814380,
    'Dark Souls III': 374320,
    'Kingdom Come: Deliverance II': 1771300,
    'Death Stranding': 1190460,
}


# a demo user's history, to show the recommender doing something sensible
DEMO_LIBRARY = [
    ("Red Dead Redemption 2", Status.completed, 10, 92.0),
    ("Grand Theft Auto V", Status.completed, 9, 140.0),
    ("Cyberpunk 2077", Status.playing, 9, 18.0),
    ("The Witcher 3: Wild Hunt", Status.completed, 9, 88.0),
    ("Overwatch 2", Status.playing, 7, 310.0),
    ("Civilization VI", Status.abandoned, 4, 6.0),
    ("Celeste", Status.abandoned, 5, 2.0),
    ("Elden Ring", Status.backlog, None, 0.0),
    ("Ghost of Tsushima", Status.backlog, None, 0.0),
    ("Hades", Status.backlog, None, 1.5),
    ("Starfield", Status.backlog, None, 0.0),
    ("Baldur's Gate 3", Status.backlog, None, 0.0),
    ("Portal 2", Status.backlog, None, 0.0),
    ("Max Payne 3", Status.wishlist, None, 0.0),
]


def seed_games(db) -> int:
    added = 0
    for row in GAMES:
        title, dev, year, genres, themes, persp, modes, h_main, h_comp, session, critic = row
        slug = slugify(title)
        appid = STEAM_APPIDS.get(title)
        existing = db.query(Game).filter(Game.slug == slug).first()
        if existing:
            # re-running the seed backfills art/appids on rows that predate them
            if appid and existing.steam_appid is None:
                existing.steam_appid = appid
            if appid and existing.cover_url is None:
                existing.cover_url = steam_cover(appid)
            continue
        db.add(
            Game(
                title=title, slug=slug, developer=dev, release_year=year,
                genres=genres, themes=themes, perspectives=persp, modes=modes,
                hours_main=h_main, hours_complete=h_comp, avg_session_minutes=session,
                critic_score=critic, steam_appid=appid,
                cover_url=steam_cover(appid) if appid else None,
            )
        )
        added += 1
    db.commit()
    return added


def seed_demo(db) -> None:
    if db.query(User).filter(User.email == "demo@playnext.app").first():
        return
    user = User(email="demo@playnext.app", display_name="Demo", password_hash=hash_password("demo1234"))
    db.add(user)
    db.flush()
    for title, status, rating, hours in DEMO_LIBRARY:
        game = db.query(Game).filter(Game.slug == slugify(title)).one()
        db.add(LibraryEntry(user_id=user.id, game_id=game.id, status=status, rating=rating, hours_played=hours))
    db.commit()


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        n = seed_games(db)
        print(f"seeded {n} games")
        if "--demo" in sys.argv:
            seed_demo(db)
            print("demo account: demo@playnext.app / demo1234")
