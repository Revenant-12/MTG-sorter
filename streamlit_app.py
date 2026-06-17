import streamlit as st
import pandas as pd
import sqlite3
import os

# Database file location
DB_FILE = "mtg_collection.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.isolation_level = None  # Enable autocommit mode
    return conn

def create_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
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
            UNIQUE(name, card_category, set_code, collector_number)
        )
    """)
    # Migration for existing tables
    try:
        cursor.execute("ALTER TABLE cards ADD COLUMN set_code TEXT")
    except sqlite3.OperationalError: pass
    try:
        cursor.execute("ALTER TABLE cards ADD COLUMN collector_number TEXT")
    except sqlite3.OperationalError: pass
    try:
        cursor.execute("ALTER TABLE cards ADD COLUMN collection_id TEXT")
    except sqlite3.OperationalError: pass
    
    conn.commit()
    conn.close()

def load_data():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM cards ORDER BY name ASC", conn)
    conn.close()
    return df

def get_split_subtypes(df):
    if df.empty or 'subtypes' not in df.columns:
        return []
    unique_subs = set()
    for s_str in df['subtypes'].dropna():
        parts = [p.strip() for p in str(s_str).split(',')]
        unique_subs.update(parts)
    return sorted([s for s in unique_subs if s])

def add_card(data):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, quantity FROM cards WHERE name=? AND card_category=? AND set_code IS ? AND collector_number IS ?", 
                  (data['name'], data['card_category'], data.get('set_code'), data.get('collector_number')))
    result = cursor.fetchone()
    row_id = None
    if result:
        row_id = result[0]
        cursor.execute("UPDATE cards SET quantity=? WHERE id=?", (result[1] + data['quantity'], row_id))
    else:
        cursor.execute("""
            INSERT INTO cards (name, color, quantity, card_category, mana_cost, power_toughness, subtypes, keywords, ability, loyalty, set_code, collector_number, collection_id) 
            VALUES (:name, :color, :quantity, :card_category, :mana_cost, :power_toughness, :subtypes, :keywords, :ability, :loyalty, :set_code, :collector_number, :collection_id)
        """, {**data, 'collection_id': None})
        row_id = cursor.lastrowid
    conn.close()
    return row_id

def update_card(card_id, data):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE cards SET 
            name=?, color=?, quantity=?, card_category=?, 
            mana_cost=?, power_toughness=?, subtypes=?, 
            keywords=?, ability=?, loyalty=?, 
            set_code=?, collector_number=?, collection_id=? 
        WHERE id=?
    """, (
        data['name'], data['color'], data['quantity'], data['card_category'],
        data['mana_cost'], data['power_toughness'], data['subtypes'],
        data['keywords'], data['ability'], data['loyalty'],
        data['set_code'], data['collector_number'], data.get('collection_id'), card_id
    ))
    conn.close()

def delete_card(card_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cards WHERE id=?", (card_id,))
    conn.commit()
    conn.close()

def export_to_excel(df, colors):
    from io import BytesIO
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Master List', index=False)
        for color in colors:
            if color == "Multicolor":
                # Match anything with '/' OR explicitly 'Multicolor'
                color_df = df[df['color'].str.contains('/', na=False) | (df['color'] == 'Multicolor')]
            else:
                # Match exact or as part of a list
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

# Sidebar - Add/Edit Card
if st.session_state.editing_id:
    st.sidebar.header(f"Editing: {st.session_state.selected_card['name']}")
    if st.sidebar.button("Cancel Edit"):
        st.session_state.editing_id = None
        st.session_state.selected_card = None
        st.session_state.should_rerun = True
else:
    st.sidebar.header("Add New Card")

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
    
    # Interpret "color/color" as multiselected
    if isinstance(current_color_str, str) and "/" in current_color_str:
        default_colors = [c.strip() for c in current_color_str.split("/")]
    elif current_color_str in colors_list:
        default_colors = [current_color_str]
    else:
        default_colors = ["White"]
        
    color = st.multiselect("Color", colors_list, default=default_colors)
    
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
            # Join selected colors with '/'
            color_to_save = "/".join(color) if color else "Colorless"
            card_data = {
                "name": name, "color": color_to_save, "quantity": quantity,
                "card_category": category, "mana_cost": mana_cost, "power_toughness": pt,
                "subtypes": subtypes, "keywords": keywords, "ability": ability,
                "loyalty": int(loyalty) if (loyalty and str(loyalty).isdigit()) else None,
                "set_code": s_code if s_code else None,
                "collector_number": c_num if c_num else None,
                "collection_id": collection_id if collection_id else None
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
    # Improved color filtering for multiselect
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
    essential = ['name', 'set_code', 'collector_number', 'color', 'quantity', 'card_category']
    active_cols = [col for col in cols_to_show if col in essential or 
                   filtered_df[col].apply(lambda x: str(x).strip() not in ['', 'None', 'nan'] if x is not None else False).any()]
    
    styled_df = filtered_df.style.apply(highlight_rows, axis=1)
    
    # Enable row selection
    selection = st.dataframe(
        styled_df, 
        use_container_width=True, 
        hide_index=True, 
        column_order=active_cols,
        on_select="rerun",
        selection_mode="single-row"
    )

    # Check for selection
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

st.markdown("---")
st.caption("Tip: To use this 'from anywhere', host this code on GitHub and connect it to [Streamlit Cloud](https://streamlit.io/cloud).")

if st.session_state.should_rerun:
    st.session_state.should_rerun = False
    st.rerun()
