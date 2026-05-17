import sqlite3
import os

DB_FILE = "test_mtg.db"
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)

conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        color TEXT,
        quantity INTEGER,
        card_category TEXT,
        mana_cost TEXT,
        power_toughness TEXT,
        subtypes TEXT,
        keywords TEXT,
        ability TEXT,
        loyalty INTEGER,
        UNIQUE(name, card_category)
    )
""")
c.execute("ALTER TABLE cards ADD COLUMN set_code TEXT")
c.execute("ALTER TABLE cards ADD COLUMN collector_number TEXT")
c.execute("INSERT INTO cards (name, card_category) VALUES ('Test Card', 'Creature')")
conn.commit()

def create_table():
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='cards'")
    row = cursor.fetchone()
    if row:
        sql = row[0]
        if "UNIQUE(name, card_category, set_code, collector_number)" not in sql:
            cursor.execute("ALTER TABLE cards RENAME TO cards_old")
            cursor.execute("""
                CREATE TABLE cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    color TEXT,
                    quantity INTEGER,
                    card_category TEXT,
                    mana_cost TEXT,
                    power_toughness TEXT,
                    subtypes TEXT,
                    keywords TEXT,
                    ability TEXT,
                    loyalty INTEGER,
                    set_code TEXT,
                    collector_number TEXT,
                    UNIQUE(name, card_category, set_code, collector_number)
                )
            """)
            cursor.execute("PRAGMA table_info(cards_old)")
            cols = [col[1] for col in cursor.fetchall()]
            
            if 'set_code' in cols and 'collector_number' in cols:
                cursor.execute("""
                    INSERT INTO cards (id, name, color, quantity, card_category, mana_cost, power_toughness, subtypes, keywords, ability, loyalty, set_code, collector_number)
                    SELECT id, name, color, quantity, card_category, mana_cost, power_toughness, subtypes, keywords, ability, loyalty, set_code, collector_number
                    FROM cards_old
                """)
            else:
                cursor.execute("""
                    INSERT INTO cards (id, name, color, quantity, card_category, mana_cost, power_toughness, subtypes, keywords, ability, loyalty)
                    SELECT id, name, color, quantity, card_category, mana_cost, power_toughness, subtypes, keywords, ability, loyalty
                    FROM cards_old
                """)
            cursor.execute("DROP TABLE cards_old")
    conn.commit()

create_table()

# Test new unique constraint
c.execute("INSERT INTO cards (name, card_category, set_code) VALUES ('Test Card', 'Creature', 'M21')")
conn.commit()
print("Success!")
