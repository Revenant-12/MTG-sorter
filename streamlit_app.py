import streamlit as st
import pandas as pd
import sqlite3
import os
from sqlalchemy import create_engine, text
import scryfall_scanner

# Local fallback database file
DB_FILE = "mtg_collection.db"

def get_db_engine():
    """
    Checks Streamlit secrets for PostgreSQL / Supabase credentials.
    If found, returns a SQLAlchemy engine for Postgres.
    Otherwise, returns a SQLAlchemy engine for local SQLite.
    """
    try:
        url = None
        if "DATABASE_URL" in st.secrets:
            url = st.secrets["DATABASE_URL"]
        elif "connections" in st.secrets and "postgresql" in st.secrets["connections"]:
            c = st.secrets["connections"]["postgresql"]
            if "url" in c:
                url = c["url"]
            else:
                user = c.get("username", c.get("user", "postgres"))
                password = c.get("password", "")
                host = c.get("host", "localhost")
                port = c.get("port", 5432)
                dbname = c.get("database", c.get("dbname", "postgres"))
                url = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
        elif "postgres" in st.secrets or "supabase" in st.secrets:
            p = st.secrets.get("postgres") or st.secrets.get("supabase")
            user = p.get("username", p.get("user", "postgres"))
            password = p.get("password", "")
            host = p.get("host", "localhost")
            port = p.get("port", 5432)
            dbname = p.get("database", p.get("dbname", "postgres"))
            url = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

        if url:
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            engine = create_engine(url, pool_pre_ping=True)
            # Test connection
            with engine.connect() as test_conn:
                test_conn.execute(text("SELECT 1"))
            return engine, "postgres"
    except Exception as e:
        st.error(f"⚠️ Cloud Database Connection Error: {e}")
        pass

    # Fallback to local SQLite engine
    return create_engine(f"sqlite:///{DB_FILE}"), "sqlite"

engine, db_type = get_db_engine()

def create_table():
    with engine.begin() as conn:
        if db_type == "postgres":
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
                    storage TEXT,
                    CONSTRAINT unique_card_instance UNIQUE(name, card_category, set_code, collector_number)
                )
            """))
        else:
            conn.execute(text("""
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
                    set_code TEXT,
                    collector_number TEXT,
                    collection_id TEXT,
                    storage TEXT,
                    UNIQUE(name, card_category, set_code, collector_number)
                )
            """))
            for col_name in ["set_code", "collector_number", "collection_id", "storage"]:
                try:
                    conn.execute(text(f"ALTER TABLE cards ADD COLUMN {col_name} TEXT"))
                except Exception:
                    pass
        # Auto-migrate existing space-separated subtypes to comma-separated format
        try:
            rows = conn.execute(text("SELECT id, subtypes FROM cards WHERE subtypes IS NOT NULL AND subtypes != ''")).fetchall()
            for r_id, sub_str in rows:
                formatted_sub = format_subtypes(sub_str)
                if formatted_sub != sub_str:
                    conn.execute(text("UPDATE cards SET subtypes = :sub WHERE id = :id"), {"sub": formatted_sub, "id": r_id})
        except Exception:
            pass

def format_subtypes(subtypes_str):
    if not subtypes_str or str(subtypes_str).strip() in ["", "None", "nan"]:
        return ""
    raw = str(subtypes_str).replace(',', ' ')
    words = [w.strip() for w in raw.split() if w.strip()]
    return ", ".join(words)

def load_data():
    with engine.connect() as conn:
        df = pd.read_sql_query(text("SELECT * FROM cards ORDER BY name ASC"), conn)
    return df

def get_split_subtypes(df):
    if df.empty or 'subtypes' not in df.columns:
        return []
    unique_subs = set()
    for s_str in df['subtypes'].dropna():
        parts = [p.strip() for p in str(s_str).replace(',', ' ').split()]
        unique_subs.update(parts)
    return sorted([s for s in unique_subs if s])

def add_card(data):
    formatted_sub = format_subtypes(data.get('subtypes'))
    data['subtypes'] = formatted_sub
    params = {
        "name": data['name'],
        "card_category": data['card_category'],
        "set_code": data.get('set_code'),
        "collector_number": data.get('collector_number')
    }
    
    with engine.begin() as conn:
        query_check = text("""
            SELECT id, quantity FROM cards 
            WHERE name = :name 
              AND card_category = :card_category 
              AND ((set_code = :set_code) OR (set_code IS NULL AND :set_code IS NULL)) 
              AND ((collector_number = :collector_number) OR (collector_number IS NULL AND :collector_number IS NULL))
        """)
        result = conn.execute(query_check, params).fetchone()
        
        if result:
            row_id, existing_qty = result[0], result[1]
            new_qty = existing_qty + data['quantity']
            conn.execute(text("UPDATE cards SET quantity = :quantity, storage = :storage WHERE id = :id"), {"quantity": new_qty, "storage": data.get('storage'), "id": row_id})
            return row_id
        else:
            insert_params = {
                "name": data['name'],
                "color": data['color'],
                "quantity": data['quantity'],
                "card_category": data['card_category'],
                "mana_cost": data['mana_cost'],
                "power_toughness": data['power_toughness'],
                "subtypes": formatted_sub,
                "keywords": data['keywords'],
                "ability": data['ability'],
                "loyalty": data['loyalty'],
                "set_code": data.get('set_code'),
                "collector_number": data.get('collector_number'),
                "collection_id": data.get('collection_id'),
                "storage": data.get('storage')
            }
            if db_type == "postgres":
                res = conn.execute(text("""
                    INSERT INTO cards (name, color, quantity, card_category, mana_cost, power_toughness, subtypes, keywords, ability, loyalty, set_code, collector_number, collection_id, storage)
                    VALUES (:name, :color, :quantity, :card_category, :mana_cost, :power_toughness, :subtypes, :keywords, :ability, :loyalty, :set_code, :collector_number, :collection_id, :storage)
                    RETURNING id
                """), insert_params)
                row_id = res.fetchone()[0]
            else:
                res = conn.execute(text("""
                    INSERT INTO cards (name, color, quantity, card_category, mana_cost, power_toughness, subtypes, keywords, ability, loyalty, set_code, collector_number, collection_id, storage)
                    VALUES (:name, :color, :quantity, :card_category, :mana_cost, :power_toughness, :subtypes, :keywords, :ability, :loyalty, :set_code, :collector_number, :collection_id, :storage)
                """), insert_params)
                row_id = res.lastrowid
            return row_id

def update_card(card_id, data):
    formatted_sub = format_subtypes(data.get('subtypes'))
    update_params = {
        "id": card_id,
        "name": data['name'],
        "color": data['color'],
        "quantity": data['quantity'],
        "card_category": data['card_category'],
        "mana_cost": data['mana_cost'],
        "power_toughness": data['power_toughness'],
        "subtypes": formatted_sub,
        "keywords": data['keywords'],
        "ability": data['ability'],
        "loyalty": data['loyalty'],
        "set_code": data['set_code'],
        "collector_number": data['collector_number'],
        "collection_id": data.get('collection_id'),
        "storage": data.get('storage')
    }
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE cards SET 
                name = :name, color = :color, quantity = :quantity, card_category = :card_category, 
                mana_cost = :mana_cost, power_toughness = :power_toughness, subtypes = :subtypes, 
                keywords = :keywords, ability = :ability, loyalty = :loyalty, 
                set_code = :set_code, collector_number = :collector_number, collection_id = :collection_id,
                storage = :storage
            WHERE id = :id
        """), update_params)

def delete_card(card_id):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM cards WHERE id = :id"), {"id": card_id})

def export_to_excel(df, colors):
    from io import BytesIO
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Master List', index=False)
        for color in colors:
            if color == "Multicolor":
                color_df = df[df['color'].str.contains('/', na=False) | (df['color'] == 'Multicolor')]
            else:
                color_df = df[df['color'].apply(lambda x: color == x or (isinstance(x, str) and color in x.split('/')))]
            
            if not color_df.empty:
                color_df.to_excel(writer, sheet_name=color, index=False)
    return output.getvalue()

# Initialize App
st.set_page_config(page_title="MTG Collection Manager", layout="wide")
create_table()

# Initialize Session State
if 'session_active' not in st.session_state:
    st.session_state.session_active = False
if 'session_card_ids' not in st.session_state:
    st.session_state.session_card_ids = set()
if 'highlight_session' not in st.session_state:
    st.session_state.highlight_session = False
if 'editing_id' not in st.session_state:
    st.session_state.editing_id = None
if 'selected_card' not in st.session_state:
    st.session_state.selected_card = None
if 'should_rerun' not in st.session_state:
    st.session_state.should_rerun = False

st.title("🎴 MTG Card Collection Manager")

if db_type == "postgres":
    st.caption("🟢 Database Status: Connected to Cloud Database (Supabase PostgreSQL)")
else:
    st.caption("🟡 Database Status: Running locally (SQLite). Add Supabase secrets to connect to cloud database.")

# Session Manager Section
st.header("Session Manager")
s_col1, s_col2, s_col3, s_col4 = st.columns(4)

with s_col1:
    status_color = "green" if st.session_state.session_active else "red"
    st.markdown(f"**Status:** :{status_color}[{'Active' if st.session_state.session_active else 'Inactive'}]")

with s_col2:
    if not st.session_state.session_active:
        if st.button("Start Session", use_container_width=True):
            st.session_state.session_active = True
            st.session_state.session_card_ids = set()
            st.session_state.should_rerun = True
    else:
        if st.button("End Session", use_container_width=True):
            count = len(st.session_state.session_card_ids)
            st.session_state.session_active = False
            st.info(f"Session ended. {count} cards were added/modified.")
            st.session_state.should_rerun = True

with s_col3:
    if st.button("Highlight Session Cards", use_container_width=True):
        st.session_state.highlight_session = True
        if not st.session_state.session_card_ids:
            st.warning("No cards in current/last session to highlight.")

with s_col4:
    if st.button("Unhighlight Cards", use_container_width=True):
        st.session_state.highlight_session = False

# Camera & Scryfall Scanner Section
st.divider()
st.header("📷 Card Scanner & Quick Search")
tab_scan, tab_search = st.tabs(["📷 Camera / Image Scanner", "🔍 Scryfall Auto-Search"])

with tab_scan:
    scan_c1, scan_c2 = st.columns([1, 1])
    with scan_c1:
        camera_photo = st.camera_input("Snap Card Photo with Camera")
    with scan_c2:
        uploaded_photo = st.file_uploader("Or Upload Card Image File", type=["jpg", "jpeg", "png"])
        
    captured = camera_photo or uploaded_photo
    if captured:
        if st.button("⚡ Scan Photo & Extract Card Details", type="primary"):
            with st.spinner("Scanning card image and looking up Scryfall metadata..."):
                card_dict, raw_text = scryfall_scanner.scan_card_image(captured.getvalue())
                if card_dict:
                    st.session_state.selected_card = card_dict
                    st.success(f"Successfully identified: **{card_dict['name']}** ({card_dict['color']} {card_dict['card_category']})!")
                    st.session_state.should_rerun = True
                else:
                    st.warning("Could not automatically match card from image text. Try typing the name in Scryfall search below.")
                    if raw_text:
                        st.caption(f"Detected text snippet: {raw_text[:150]}")

with tab_search:
    sch_c1, sch_c2 = st.columns([2, 1])
    with sch_c1:
        search_query = st.text_input("Card Name (Fuzzy Search)", placeholder="e.g. Froghemoth, Sol Ring, Abandoned Air Temple")
        if search_query:
            suggestions = scryfall_scanner.autocomplete_card_name(search_query)
            if suggestions:
                selected_sug = st.selectbox("Suggestions from Scryfall:", suggestions)
                if st.button("Autofill Selected Card Details"):
                    c_data = scryfall_scanner.fetch_card_by_name(selected_sug)
                    if c_data:
                        st.session_state.selected_card = c_data
                        st.success(f"Autofilled details for **{c_data['name']}**!")
                        st.session_state.should_rerun = True
            else:
                if st.button("Search Scryfall directly"):
                    c_data = scryfall_scanner.fetch_card_by_name(search_query)
                    if c_data:
                        st.session_state.selected_card = c_data
                        st.success(f"Autofilled details for **{c_data['name']}**!")
                        st.session_state.should_rerun = True
                    else:
                        st.error("No card found matching that name on Scryfall.")
    with sch_c2:
        set_code_in = st.text_input("Set Code (Optional)", placeholder="e.g. AFR, TLA")
        coll_num_in = st.text_input("Collector # (Optional)", placeholder="e.g. 184, 0263")
        if set_code_in and coll_num_in:
            if st.button("Fetch by Set & Collector #"):
                c_data = scryfall_scanner.fetch_card_by_set_collector(set_code_in, coll_num_in)
                if c_data:
                    st.session_state.selected_card = c_data
                    st.success(f"Found **{c_data['name']}** ({set_code_in.upper()} #{coll_num_in})!")
                    st.session_state.should_rerun = True
                else:
                    st.error("No card found with that set code and collector number.")

st.divider()

# Sidebar - Add/Edit Card
if st.session_state.editing_id:
    st.sidebar.header(f"Editing: {st.session_state.selected_card['name']}")
    if st.sidebar.button("Cancel Edit"):
        st.session_state.editing_id = None
        st.session_state.selected_card = None
        st.session_state.printings_list = None
        st.session_state.should_rerun = True
else:
    st.sidebar.header("Add New Card")

# Scryfall Printing Finder for Editing / Auto-suggest Set & Collector #
if st.session_state.selected_card and st.session_state.selected_card.get('name'):
    card_n = st.session_state.selected_card['name']
    with st.sidebar.expander("✨ Suggest Set Code & Collector # (Scryfall)"):
        if st.button(f"🔍 Fetch Printings for '{card_n}'", use_container_width=True):
            with st.spinner("Searching Scryfall for card printings..."):
                import importlib
                importlib.reload(scryfall_scanner)
                fetch_func = getattr(scryfall_scanner, 'fetch_card_printings', scryfall_scanner.fetch_card_printings)
                st.session_state.printings_list = fetch_func(card_n)
        
        if st.session_state.get('printings_list'):
            printing_labels = [p['label'] for p in st.session_state.printings_list]
            selected_p_label = st.selectbox("Select Specific Printing / Set:", printing_labels)
            if st.button("Apply Selected Printing"):
                idx = printing_labels.index(selected_p_label)
                chosen_card = st.session_state.printings_list[idx]['card_data']
                
                # Preserve existing quantity, storage, collection_id, and ID
                if st.session_state.selected_card:
                    chosen_card['quantity'] = st.session_state.selected_card.get('quantity', 1)
                    chosen_card['storage'] = st.session_state.selected_card.get('storage', 'Blue')
                    chosen_card['collection_id'] = st.session_state.selected_card.get('collection_id')
                if st.session_state.editing_id:
                    chosen_card['id'] = st.session_state.editing_id

                st.session_state.selected_card = chosen_card
                st.success(f"Applied: {chosen_card['set_code']} #{chosen_card['collector_number']}")
                st.session_state.should_rerun = True

# Category selection
card_types = [
    "Land", "Legendary Creature", "Creature", "Instant", "Sorcery",
    "Legendary Enchantment", "Enchantment", "Planeswalker",
    "Legendary Artifact", "Artifact", "Artifact Equipment",
    "Artifact Vehicle", "Artifact Creature", "Artifact Treasure"
]

default_cat = "Land"
if st.session_state.selected_card:
    try:
        default_cat = st.session_state.selected_card['card_category']
    except: pass

category = st.sidebar.selectbox("Category", card_types, 
                               index=card_types.index(default_cat) if default_cat in card_types else 0)

# Logic for visibility based on category
show = {"mana": True, "pt": False, "sub": False, "key": False, "ab": True, "loy": False}
if category == "Land":
    show["mana"] = False
elif "Creature" in category or "Vehicle" in category:
    show["pt"] = True
    show["sub"] = True
    show["key"] = True
elif category == "Planeswalker":
    show["loy"] = True

with st.sidebar.form("card_form", clear_on_submit=(not st.session_state.editing_id)):
    def get_val(key, default=""):
        if st.session_state.selected_card and key in st.session_state.selected_card:
            val = st.session_state.selected_card[key]
            return val if val is not None and str(val) != 'nan' else default
        return default

    name = st.text_input("Card Name", value=get_val('name'))
    col_set1, col_set2 = st.columns(2)
    with col_set1:
        set_code = st.text_input("Set Code", value=get_val('set_code'), help="e.g. SNC, M21")
    with col_set2:
        collector_num = st.text_input("Collector #", value=get_val('collector_number'), help="Card number in set")
    
    colors_list = ["White", "Blue", "Black", "Red", "Green", "Colorless", "Multicolor"]
    current_color_str = get_val('color', 'White')
    
    if isinstance(current_color_str, str) and "/" in current_color_str:
        default_colors = [c.strip() for c in current_color_str.split("/")]
    elif current_color_str in colors_list:
        default_colors = [current_color_str]
    else:
        default_colors = ["White"]
        
    color = st.multiselect("Color", colors_list, default=default_colors)
    
    storage_options = ["Blue", "Black", "Red", "Green", "White", "Colorless"]
    current_storage = get_val('storage', 'Blue')
    storage_idx = storage_options.index(current_storage) if current_storage in storage_options else 0
    storage = st.selectbox("Storage", storage_options, index=storage_idx)
    
    quantity = st.number_input("Quantity", min_value=1, value=int(get_val('quantity', 1)))
    
    collection_id = st.text_input("Collection ID", value=get_val('collection_id'))
    
    mana_cost = st.text_input("Mana Cost", value=get_val('mana_cost')) if show["mana"] else ""
    pt = st.text_input("P/T", value=get_val('power_toughness')) if show["pt"] else ""
    subtypes = st.text_input("Subtypes", value=get_val('subtypes')) if show["sub"] else ""
    keywords = st.text_input("Keywords", value=get_val('keywords')) if show["key"] else ""
    ability = st.text_area("Ability", value=get_val('ability')) if show["ab"] else ""
    loyalty_val = get_val('loyalty', "")
    loyalty = st.text_input("Loyalty", value=str(loyalty_val) if loyalty_val else "") if show["loy"] else ""

    submit_label = "Save Changes" if st.session_state.editing_id else "Add Card"
    submitted = st.form_submit_button(submit_label)
    
    if submitted:
        if name:
            s_code = set_code.strip().upper()
            c_num = collector_num.strip()
            color_to_save = "/".join(color) if color else "Colorless"
            card_data = {
                "name": name, "color": color_to_save, "quantity": quantity,
                "card_category": category, "mana_cost": mana_cost, "power_toughness": pt,
                "subtypes": subtypes, "keywords": keywords, "ability": ability,
                "loyalty": int(loyalty) if (loyalty and str(loyalty).isdigit()) else None,
                "set_code": s_code if s_code else None,
                "collector_number": c_num if c_num else None,
                "collection_id": collection_id if collection_id else None,
                "storage": storage
            }
            
            if st.session_state.editing_id:
                update_card(st.session_state.editing_id, card_data)
                st.success(f"Updated {name}!")
                st.session_state.editing_id = None
                st.session_state.selected_card = None
            else:
                row_id = add_card(card_data)
                if st.session_state.session_active and row_id:
                    st.session_state.session_card_ids.add(row_id)
                st.success(f"Added {name}!")
            
            st.session_state.should_rerun = True
        else:
            st.error("Card Name is required.")

# Main Content
df = load_data()

# Filters
st.header("Collection Browser")
st.caption("Select a row to edit its details in the sidebar.")
f_col1, f_col2, f_col3, f_col4 = st.columns(4)

with f_col1:
    f_color = st.multiselect("Colors", ["White", "Blue", "Black", "Red", "Green", "Colorless", "Multicolor"], key="filter_color")
with f_col2:
    f_cat = st.multiselect("Categories", card_types, key="filter_cat")
with f_col3:
    all_costs = sorted(df['mana_cost'].dropna().unique()) if not df.empty else []
    f_cost = st.multiselect("Costs", all_costs, key="filter_cost")
with f_col4:
    all_subs = get_split_subtypes(df)
    f_sub = st.multiselect("Subtypes", all_subs, key="filter_sub")

search = st.text_input("Search Name", key="filter_search")

filtered_df = df.copy()
if f_color:
    color_mask = filtered_df['color'].apply(lambda x: any(c in str(x) for c in f_color))
    filtered_df = filtered_df[color_mask]
if f_cat:
    filtered_df = filtered_df[filtered_df['card_category'].isin(f_cat)]
if f_cost:
    filtered_df = filtered_df[filtered_df['mana_cost'].isin(f_cost)]
if f_sub:
    sub_mask = filtered_df['subtypes'].apply(lambda x: any(s in str(x) for s in f_sub))
    filtered_df = filtered_df[sub_mask]
if search:
    filtered_df = filtered_df[filtered_df['name'].str.contains(search, case=False)]

# Styling for Highlighting
def highlight_rows(row):
    if st.session_state.highlight_session and row.id in st.session_state.session_card_ids:
        return ['background-color: #FFFF99'] * len(row)
    return [''] * len(row)

if not filtered_df.empty:
    cols_to_show = [col for col in filtered_df.columns if col != 'id']
    essential = ['name', 'set_code', 'collector_number', 'color', 'quantity', 'card_category', 'storage']
    active_cols = [col for col in cols_to_show if col in essential or 
                   filtered_df[col].apply(lambda x: str(x).strip() not in ['', 'None', 'nan'] if x is not None else False).any()]
    
    styled_df = filtered_df.style.apply(highlight_rows, axis=1)
    
    selection = st.dataframe(
        styled_df, 
        use_container_width=True, 
        hide_index=True, 
        column_order=active_cols,
        on_select="rerun",
        selection_mode="single-row"
    )

    if selection and "selection" in selection and selection["selection"]["rows"]:
        selected_row_idx = selection["selection"]["rows"][0]
        selected_card = filtered_df.iloc[selected_row_idx]
        if st.session_state.editing_id != int(selected_card.id):
            st.session_state.editing_id = int(selected_card.id)
            st.session_state.selected_card = selected_card.to_dict()
            st.session_state.should_rerun = True

else:
    st.info("No cards match your filters.")

# Export and Actions
if not df.empty:
    st.divider()
    col_exp, col_del = st.columns([1, 1])
    
    with col_exp:
        excel_data = export_to_excel(df, ["White", "Blue", "Black", "Red", "Green", "Colorless", "Multicolor"])
        st.download_button(
            label="📥 Export Collection to Excel",
            data=excel_data,
            file_name="mtg_collection_export.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    with col_del:
        with st.expander("🗑️ Delete a Card"):
            card_to_delete = st.selectbox("Select Card to Delete", df['name'].unique())
            card_instances = df[df['name'] == card_to_delete]
            instance_labels = [f"{row.set_code or '??'} - {row.collector_number or '??'} ({row.card_category})" for _, row in card_instances.iterrows()]
            instance_to_delete = st.selectbox("Select specific version to delete", instance_labels)
            
            if st.button("Confirm Delete", type="primary"):
                idx = instance_labels.index(instance_to_delete)
                card_id = card_instances.iloc[idx]['id']
                delete_card(int(card_id))
                st.warning(f"Deleted {card_to_delete} version!")
                st.session_state.should_rerun = True

else:
    st.info("Your collection is currently empty. Add some cards in the sidebar!")

if st.session_state.should_rerun:
    st.session_state.should_rerun = False
    st.rerun()
