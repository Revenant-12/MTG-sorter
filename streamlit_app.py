import streamlit as st
import pandas as pd
import sqlite3
import os

# Database file location
DB_FILE = "mtg_collection.db"

def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

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
            UNIQUE(name, card_category)
        )
    """)
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
    cursor.execute("SELECT id, quantity FROM cards WHERE name=? AND card_category=?", (data['name'], data['card_category']))
    result = cursor.fetchone()
    row_id = None
    if result:
        row_id = result[0]
        cursor.execute("UPDATE cards SET quantity=? WHERE id=?", (result[1] + data['quantity'], row_id))
    else:
        cursor.execute("""
            INSERT INTO cards (name, color, quantity, card_category, mana_cost, power_toughness, subtypes, keywords, ability, loyalty) 
            VALUES (:name, :color, :quantity, :card_category, :mana_cost, :power_toughness, :subtypes, :keywords, :ability, :loyalty)
        """, data)
        row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id

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
            color_df = df[df['color'] == color]
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
            st.rerun()
    else:
        if st.button("End Session", use_container_width=True):
            count = len(st.session_state.session_card_ids)
            st.session_state.session_active = False
            st.info(f"Session ended. {count} cards were added/modified.")
            st.rerun()

with s_col3:
    if st.button("Highlight Session Cards", use_container_width=True):
        st.session_state.highlight_session = True
        if not st.session_state.session_card_ids:
            st.warning("No cards in current/last session to highlight.")

with s_col4:
    if st.button("Unhighlight Cards", use_container_width=True):
        st.session_state.highlight_session = False

# Sidebar - Add Card
st.sidebar.header("Add New Card")
category = st.sidebar.selectbox("Category", [
    "Land", "Legendary Creature", "Creature", "Instant", "Sorcery",
    "Legendary Enchantment", "Enchantment", "Planeswalker",
    "Legendary Artifact", "Artifact", "Artifact Equipment",
    "Artifact Vehicle", "Artifact Creature", "Artifact Treasure"
])

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

with st.sidebar.form("add_card_form", clear_on_submit=True):
    name = st.text_input("Card Name")
    color = st.selectbox("Color", ["White", "Blue", "Black", "Red", "Green", "Colorless", "Multicolor"])
    quantity = st.number_input("Quantity", min_value=1, value=1)
    
    mana_cost = st.text_input("Mana Cost") if show["mana"] else ""
    pt = st.text_input("P/T") if show["pt"] else ""
    subtypes = st.text_input("Subtypes") if show["sub"] else ""
    keywords = st.text_input("Keywords") if show["key"] else ""
    ability = st.text_area("Ability") if show["ab"] else ""
    loyalty = st.text_input("Loyalty") if show["loy"] else ""

    submitted = st.form_submit_button("Add Card")
    if submitted:
        if name:
            new_card = {
                "name": name, "color": color, "quantity": quantity,
                "card_category": category, "mana_cost": mana_cost, "power_toughness": pt,
                "subtypes": subtypes, "keywords": keywords, "ability": ability,
                "loyalty": int(loyalty) if loyalty.isdigit() else None
            }
            row_id = add_card(new_card)
            if st.session_state.session_active and row_id:
                st.session_state.session_card_ids.add(row_id)
            st.success(f"Added {name}!")
            st.rerun()
        else:
            st.error("Card Name is required.")

# Main Content
df = load_data()

# Filters
st.header("Collection Browser")
f_col1, f_col2, f_col3, f_col4 = st.columns(4)

with f_col1:
    f_color = st.multiselect("Colors", ["White", "Blue", "Black", "Red", "Green", "Colorless", "Multicolor"])
with f_col2:
    f_cat = st.multiselect("Categories", [
        "Land", "Legendary Creature", "Creature", "Instant", "Sorcery",
        "Legendary Enchantment", "Enchantment", "Planeswalker",
        "Legendary Artifact", "Artifact", "Artifact Equipment",
        "Artifact Vehicle", "Artifact Creature", "Artifact Treasure"
    ])
with f_col3:
    all_costs = sorted(df['mana_cost'].dropna().unique()) if not df.empty else []
    f_cost = st.multiselect("Costs", all_costs)
with f_col4:
    all_subs = get_split_subtypes(df)
    f_sub = st.multiselect("Subtypes", all_subs)

search = st.text_input("Search Name")

filtered_df = df.copy()
if f_color:
    # Use OR logic for colors (LIKE %color%)
    color_mask = filtered_df['color'].apply(lambda x: any(c in str(x) for c in f_color))
    filtered_df = filtered_df[color_mask]
if f_cat:
    filtered_df = filtered_df[filtered_df['card_category'].isin(f_cat)]
if f_cost:
    filtered_df = filtered_df[filtered_df['mana_cost'].isin(f_cost)]
if f_sub:
    # Use LIKE logic for subtypes
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
    # Dynamically hide columns that are entirely empty in the current view
    cols_to_show = [col for col in filtered_df.columns if col != 'id']
    
    # Essential columns we always want to see
    essential = ['name', 'color', 'quantity', 'card_category']
    
    # Filter dynamic columns: keep if they have at least one non-empty/non-null value
    active_cols = [col for col in cols_to_show if col in essential or 
                   filtered_df[col].apply(lambda x: str(x).strip() not in ['', 'None', 'nan'] if x is not None else False).any()]
    
    styled_df = filtered_df.style.apply(highlight_rows, axis=1)
    st.dataframe(styled_df, use_container_width=True, hide_index=True, column_order=active_cols)
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
            cat_to_delete = st.selectbox("Select Category for Deletion", df[df['name'] == card_to_delete]['card_category'].unique())
            if st.button("Confirm Delete", type="primary"):
                card_id = df[(df['name'] == card_to_delete) & (df['card_category'] == cat_to_delete)]['id'].values[0]
                delete_card(card_id)
                st.warning(f"Deleted {card_to_delete} ({cat_to_delete})")
                st.rerun()

else:
    st.info("Your collection is currently empty. Add some cards in the sidebar!")

st.markdown("---")
st.caption("Tip: To use this 'from anywhere', host this code on GitHub and connect it to [Streamlit Cloud](https://streamlit.io/cloud).")
