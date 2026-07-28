"""
Migration Script: Local SQLite -> Supabase PostgreSQL
---------------------------------------------------
Run this script after configuring your Supabase database string to upload all
existing cards from your local `mtg_collection.db` to Supabase.
"""

import sqlite3
import pandas as pd
import sys
import os
from sqlalchemy import create_engine, text

SQLITE_DB = "mtg_collection.db"

def migrate():
    if not os.path.exists(SQLITE_DB):
        print(f"❌ Error: Local SQLite file '{SQLITE_DB}' not found.")
        return

    # Check for connection string
    db_url = os.environ.get("DATABASE_URL")
    if not db_url and len(sys.argv) > 1:
        db_url = sys.argv[1]

    if not db_url:
        print("\n❌ Error: Missing Supabase Connection URI.")
        print("Usage:")
        print("  python migrate_to_supabase.py 'postgresql://postgres.xxx:password@aws-0-us-east-1.pooler.supabase.com:6543/postgres'")
        print("or set DATABASE_URL environment variable.")
        return

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    print(f"📖 Reading cards from local SQLite database '{SQLITE_DB}'...")
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    df = pd.read_sql_query("SELECT * FROM cards", sqlite_conn)
    sqlite_conn.close()

    print(f"Found {len(df)} cards in local database.")

    if df.empty:
        print("No cards to migrate.")
        return

    print("🔌 Connecting to Supabase PostgreSQL database...")
    pg_engine = create_engine(db_url)

    with pg_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS cards (
                id SERIAL PRIMARY KEY,
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
                collection_id TEXT,
                CONSTRAINT unique_card_instance UNIQUE(name, card_category, set_code, collector_number)
            )
        """))

        migrated_count = 0
        skipped_count = 0

        for _, row in df.iterrows():
            params = {
                "name": row.get("name"),
                "color": row.get("color"),
                "quantity": int(row.get("quantity")) if pd.notna(row.get("quantity")) else 1,
                "card_category": row.get("card_category"),
                "mana_cost": row.get("mana_cost") if pd.notna(row.get("mana_cost")) else "",
                "power_toughness": row.get("power_toughness") if pd.notna(row.get("power_toughness")) else "",
                "subtypes": row.get("subtypes") if pd.notna(row.get("subtypes")) else "",
                "keywords": row.get("keywords") if pd.notna(row.get("keywords")) else "",
                "ability": row.get("ability") if pd.notna(row.get("ability")) else "",
                "loyalty": int(row["loyalty"]) if pd.notna(row.get("loyalty")) else None,
                "set_code": row.get("set_code") if pd.notna(row.get("set_code")) else None,
                "collector_number": row.get("collector_number") if pd.notna(row.get("collector_number")) else None,
                "collection_id": row.get("collection_id") if pd.notna(row.get("collection_id")) else None,
            }

            check_q = text("""
                SELECT id FROM cards 
                WHERE name = :name 
                  AND card_category = :card_category 
                  AND ((set_code = :set_code) OR (set_code IS NULL AND :set_code IS NULL)) 
                  AND ((collector_number = :collector_number) OR (collector_number IS NULL AND :collector_number IS NULL))
            """)
            res = conn.execute(check_q, params).fetchone()

            if res:
                skipped_count += 1
            else:
                insert_q = text("""
                    INSERT INTO cards (name, color, quantity, card_category, mana_cost, power_toughness, subtypes, keywords, ability, loyalty, set_code, collector_number, collection_id)
                    VALUES (:name, :color, :quantity, :card_category, :mana_cost, :power_toughness, :subtypes, :keywords, :ability, :loyalty, :set_code, :collector_number, :collection_id)
                """)
                conn.execute(insert_q, params)
                migrated_count += 1

    print(f"\n✅ Migration Complete!")
    print(f"   • Migrated: {migrated_count} cards")
    print(f"   • Already Existed: {skipped_count} cards")

if __name__ == "__main__":
    migrate()
