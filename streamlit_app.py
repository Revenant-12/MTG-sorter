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

def add_card(data):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, quantity FROM cards WHERE name=? AND card_category=?", (data['name'], data['card_category']))
    result = cursor.fetchone()
    if result:
        cursor.execute("UPDATE cards SET quantity=? WHERE id=?", (result[1] + data['quantity'], result[0]))
    else:
        cursor.execute("""
            INSERT INTO cards (name, color, quantity, card_category, mana_cost, power_toughness, subtypes, keywords, ability, loyalty) 
            VALUES (:name, :color, :quantity, :card_category, :mana_cost, :power_toughness, :subtypes, :keywords, :ability, :loyalty)
        """, data)
    conn.commit()
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
            color_df = df[df['color'] == color]
            if not color_df.empty:
                color_df.to_excel(writer, sheet_name=color, index=False)
    return output.getvalue()

# Initialize App
st.set_page_config(page_title="MTG Collection Manager", layout="wide")
create_table()

st.title("🎴 MTG Card Collection Manager")

# Sidebar - Add Card
st.sidebar.header("Add New Card")
with st.sidebar.form("add_card_form", clear_on_submit=True):
    name = st.text_input("Card Name")
    color = st.selectbox("Color", ["White", "Blue", "Black", "Red", "Green", "Colorless", "Multicolor"])
    quantity = st.number_input("Quantity", min_value=1, value=1)
    category = st.selectbox("Category", [
        "Land", "Legendary Creature", "Creature", "Instant", "Sorcery",
        "Legendary Enchantment", "Enchantment", "Planeswalker",
        "Legendary Artifact", "Artifact", "Artifact Equipment",
        "Artifact Vehicle", "Artifact Creature", "Artifact Treasure"
    ])
    mana_cost = st.text_input("Mana Cost")
    pt = st.text_input("P/T")
    subtypes = st.text_input("Subtypes")
    keywords = st.text_input("Keywords")
    ability = st.text_area("Ability")
    loyalty = st.text_input("Loyalty")

    submitted = st.form_submit_button("Add Card")
    if submitted:
        if name:
            new_card = {
                "name": name, "color": color, "quantity": quantity,
                "card_category": category, "mana_cost": mana_cost, "power_toughness": pt,
                "subtypes": subtypes, "keywords": keywords, "ability": ability,
                "loyalty": int(loyalty) if loyalty.isdigit() else None
            }
            add_card(new_card)
            st.success(f"Added {name}!")
        else:
            st.error("Card Name is required.")

# Main Content
df = load_data()

# Filters
st.header("Collection Browser")
col1, col2, col3 = st.columns(3)
with col1:
    f_color = st.multiselect("Filter by Color", df['color'].unique() if not df.empty else [])
with col2:
    f_cat = st.multiselect("Filter by Category", df['card_category'].unique() if not df.empty else [])
with col3:
    search = st.text_input("Search Name")

filtered_df = df.copy()
if f_color:
    filtered_df = filtered_df[filtered_df['color'].isin(f_color)]
if f_cat:
    filtered_df = filtered_df[filtered_df['card_category'].isin(f_cat)]
if search:
    filtered_df = filtered_df[filtered_df['name'].str.contains(search, case=False)]

st.dataframe(filtered_df, use_container_width=True, hide_index=True)

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
