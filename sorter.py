#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import pandas as pd
import os
from tkinterdnd2 import DND_FILES, TkinterDnD

# Database file location
DB_FILE = "mtg_collection.db"

class SearchableMultiSelectDropdown(tk.Frame):
    def __init__(self, parent, options, label_text="Select Options"):
        super().__init__(parent)
        self.options = sorted(options)
        self.selected_items = set() 
        self.label_text = label_text
        
        self.menubutton = tk.Button(self, text=label_text, command=self.toggle_popup, relief="raised", width=15, anchor="w")
        self.menubutton.pack(fill="x")
        self.popup = None

    def toggle_popup(self):
        if self.popup and self.popup.winfo_exists():
            self.popup.destroy()
            return
        self.popup = tk.Toplevel(self)
        self.popup.wm_overrideredirect(True)
        self.popup.attributes('-topmost', True)
        x = self.menubutton.winfo_rootx()
        y = self.menubutton.winfo_rooty() + self.menubutton.winfo_height()
        self.popup.geometry(f"250x300+{x}+{y}")

        search_frame = tk.Frame(self.popup, bg="#eeeeee", padx=5, pady=5)
        search_frame.pack(fill="x")
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.update_list)
        tk.Entry(search_frame, textvariable=self.search_var).pack(fill="x")

        list_frame = tk.Frame(self.popup)
        list_frame.pack(fill="both", expand=True)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical")
        self.listbox = tk.Listbox(list_frame, selectmode="multiple", exportselection=False, yscrollcommand=scrollbar.set, height=10)
        scrollbar.config(command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)
        
        tk.Button(self.popup, text="Done / Close", command=self.close_popup, bg="#dddddd").pack(fill="x")
        self.update_list()

    def update_list(self, *args):
        search_term = self.search_var.get().lower()
        self.listbox.delete(0, "end")
        filtered = [opt for opt in self.options if search_term in str(opt).lower()]
        for i, opt in enumerate(filtered):
            self.listbox.insert("end", opt)
            if opt in self.selected_items: self.listbox.selection_set(i)

    def on_select(self, event):
        all_visible = self.listbox.get(0, "end")
        current_indices = self.listbox.curselection()
        for i, item in enumerate(all_visible):
            if i in current_indices: self.selected_items.add(item)
            else: self.selected_items.discard(item)
        self.update_label()

    def close_popup(self):
        if self.popup: self.popup.destroy()

    def update_label(self):
        if not self.selected_items: self.menubutton.config(text=self.label_text)
        elif len(self.selected_items) == 1: self.menubutton.config(text=list(self.selected_items)[0])
        else: self.menubutton.config(text=f"{len(self.selected_items)} Selected")
            
    def get_selected(self): return list(self.selected_items)
    def update_options(self, new_options):
        self.options = sorted(list(set(new_options)))
        self.selected_items = {x for x in self.selected_items if x in self.options}
        self.update_label()
    def clear_selection(self):
        self.selected_items.clear()
        self.update_label()

class MTGCardManager:
    def __init__(self, root):
        self.root = root
        self.root.title("MTG Card Sorter & Inventory")
        self.root.geometry("1400x900")

        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.on_file_drop)

        # Style Settings
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Treeview", rowheight=30, font=('Arial', 10)) 
        style.configure("Treeview.Heading", font=('Arial', 10, 'bold'))
        
        # Connect DB
        self.conn = sqlite3.connect(DB_FILE)
        self.create_table()

        # Session
        self.session_active = False
        self.session_card_ids = set() 

        # Variables
        self.var_name = tk.StringVar()
        self.var_color = tk.StringVar()
        self.var_quantity = tk.IntVar(value=1)
        self.var_type = tk.StringVar()
        self.var_mana_cost = tk.StringVar()
        self.var_pt = tk.StringVar()
        self.var_subtypes = tk.StringVar()
        self.var_keywords = tk.StringVar()
        self.var_ability = tk.StringVar()
        self.var_loyalty = tk.StringVar()
        self.var_set_code = tk.StringVar()
        self.var_collector_num = tk.StringVar()
        self.editing_card_id = None 

        self.card_types = [
            "Land", "Legendary Creature", "Creature", "Instant", "Sorcery",
            "Legendary Enchantment", "Enchantment", "Planeswalker",
            "Legendary Artifact", "Artifact", "Artifact Equipment",
            "Artifact Vehicle", "Artifact Creature", "Artifact Treasure"
        ]
        self.colors = ["White", "Blue", "Black", "Red", "Green", "Colorless", "Multicolor"]
        self.tree_dict = {} 
        
        self.setup_ui()
        self.refresh_dropdowns()

    def create_table(self):
        cursor = self.conn.cursor()
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
        self.conn.commit()

    def get_distinct_values(self, column):
        cursor = self.conn.cursor()
        try:
            cursor.execute(f"SELECT DISTINCT {column} FROM cards WHERE {column} IS NOT NULL AND {column} != ''")
            return [row[0] for row in cursor.fetchall()]
        except: return []

    def get_split_subtypes(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT subtypes FROM cards WHERE subtypes IS NOT NULL AND subtypes != ''")
        unique_subs = set()
        for (s_str,) in cursor.fetchall():
            parts = [p.strip() for p in str(s_str).split(',')]
            unique_subs.update(parts)
        return sorted(list(unique_subs))

    def refresh_dropdowns(self):
        self.db_costs = self.get_distinct_values("mana_cost")
        self.db_subtypes = self.get_split_subtypes()
        if hasattr(self, 'filter_cost'):
            self.filter_cost.update_options(self.db_costs)
            self.filter_sub.update_options(self.db_subtypes)

    def setup_ui(self):
        self.create_session_frame()
        self.create_input_frame()
        
        self.main_notebook = ttk.Notebook(self.root)
        self.main_notebook.pack(fill="both", expand=True, padx=5, pady=5)

        master_frame = tk.Frame(self.main_notebook)
        self.main_notebook.add(master_frame, text="  MASTER LIST  ")
        self.create_master_tab_content(master_frame)

        for color in self.colors:
            color_frame = tk.Frame(self.main_notebook)
            self.main_notebook.add(color_frame, text=f"  {color}  ")
            self.create_color_tab_content(color_frame, color)

        self.load_all_cards()

    def create_session_frame(self):
        session_frame = tk.LabelFrame(self.root, text="Session Manager", padx=10, pady=5, bg="#f0f8ff")
        session_frame.pack(fill="x", padx=10, pady=5)
        
        self.lbl_session_status = tk.Label(session_frame, text="Status: Inactive", fg="red", bg="#f0f8ff", font=("Arial", 10, "bold"))
        self.lbl_session_status.pack(side="left", padx=10)
        
        tk.Button(session_frame, text="Start Session", command=self.start_session, bg="#b3e6b3").pack(side="left", padx=5)
        tk.Button(session_frame, text="End Session", command=self.end_session, bg="#ffcccb").pack(side="left", padx=5)
        tk.Button(session_frame, text="Highlight Added Cards", command=self.highlight_session, bg="#ffff99").pack(side="left", padx=20)
        tk.Button(session_frame, text="Unhighlight Cards", command=self.unhighlight_session, bg="#ffffff").pack(side="left", padx=5)
        
        # Add Export Button
        tk.Button(session_frame, text="Export to Excel", command=self.export_to_excel, bg="#add8e6").pack(side="right", padx=10)

    def export_to_excel(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile="mtg_collection.xlsx"
        )
        if not file_path:
            return
        
        try:
            # Read all data
            df = pd.read_sql_query("SELECT * FROM cards ORDER BY name ASC", self.conn)
            
            # If the database is empty
            if df.empty:
                messagebox.showwarning("Export Warning", "The collection is empty. Nothing to export.")
                return

            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # 1. Master Sheet
                df.to_excel(writer, sheet_name='Master List', index=False)
                
                # 2. Sheets by Color
                # Use the predefined colors to ensure consistent order and presence
                for color in self.colors:
                    color_df = df[df['color'] == color]
                    if not color_df.empty:
                        color_df.to_excel(writer, sheet_name=color, index=False)
                
                # 3. Handle any other colors not in self.colors (just in case)
                other_colors = df[~df['color'].isin(self.colors)]['color'].unique()
                for color in other_colors:
                    if color and color not in self.colors:
                        color_df = df[df['color'] == color]
                        # Excel sheet names must be <= 31 chars
                        sheet_name = str(color)[:31]
                        color_df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            messagebox.showinfo("Export Successful", f"Collection exported to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"An error occurred while exporting:\n{e}")

    def create_input_frame(self):
        input_frame = tk.LabelFrame(self.root, text="Card Details (Drag & Drop Excel Files Here)", padx=10, pady=5)
        input_frame.pack(fill="x", padx=10, pady=5)

        # Row 0: Name, Color, Qty, Category
        tk.Label(input_frame, text="Name:").grid(row=0, column=0, sticky="e")
        tk.Entry(input_frame, textvariable=self.var_name, width=25).grid(row=0, column=1, sticky="w")
        tk.Label(input_frame, text="Color:").grid(row=0, column=2, sticky="e")
        tk.Entry(input_frame, textvariable=self.var_color, width=15).grid(row=0, column=3, sticky="w")
        tk.Label(input_frame, text="Qty:").grid(row=0, column=4, sticky="e")
        tk.Entry(input_frame, textvariable=self.var_quantity, width=5).grid(row=0, column=5, sticky="w")
        tk.Label(input_frame, text="Category:").grid(row=0, column=6, sticky="e")
        self.type_combo = ttk.Combobox(input_frame, textvariable=self.var_type, values=self.card_types, state="readonly", width=20)
        self.type_combo.grid(row=0, column=7, sticky="w")
        self.type_combo.bind("<<ComboboxSelected>>", self.update_fields_visibility)

        # Row 1: Set Code, Collector Number
        tk.Label(input_frame, text="Set Code:").grid(row=1, column=0, sticky="e")
        tk.Entry(input_frame, textvariable=self.var_set_code, width=10).grid(row=1, column=1, sticky="w")
        tk.Label(input_frame, text="Card # (ID):").grid(row=1, column=2, sticky="e")
        tk.Entry(input_frame, textvariable=self.var_collector_num, width=10).grid(row=1, column=3, sticky="w")

        self.dynamic_frame = tk.Frame(input_frame)
        self.dynamic_frame.grid(row=2, column=0, columnspan=8, pady=5, sticky="w")
        self.lbl_mana = tk.Label(self.dynamic_frame, text="Mana Cost:")
        self.ent_mana = tk.Entry(self.dynamic_frame, textvariable=self.var_mana_cost, width=10)
        self.lbl_pt = tk.Label(self.dynamic_frame, text="P/T:")
        self.ent_pt = tk.Entry(self.dynamic_frame, textvariable=self.var_pt, width=8)
        self.lbl_sub = tk.Label(self.dynamic_frame, text="Subtypes:")
        self.ent_sub = tk.Entry(self.dynamic_frame, textvariable=self.var_subtypes, width=15)
        self.lbl_key = tk.Label(self.dynamic_frame, text="Keywords:")
        self.ent_key = tk.Entry(self.dynamic_frame, textvariable=self.var_keywords, width=15)
        self.lbl_ab = tk.Label(self.dynamic_frame, text="Ability:")
        self.ent_ab = tk.Entry(self.dynamic_frame, textvariable=self.var_ability, width=30)
        self.lbl_loy = tk.Label(self.dynamic_frame, text="Loyalty:")
        self.ent_loy = tk.Entry(self.dynamic_frame, textvariable=self.var_loyalty, width=5)

        btn_frame = tk.Frame(input_frame)
        btn_frame.grid(row=3, column=0, columnspan=8, pady=5)
        self.btn_submit = tk.Button(btn_frame, text="Add Card", command=self.add_card, bg="#dddddd", width=15)
        self.btn_submit.pack(side="left", padx=5)
        self.btn_delete = tk.Button(btn_frame, text="Delete Card", command=self.delete_card, bg="#ff9999", width=15, state="disabled")
        self.btn_delete.pack(side="left", padx=5)
        tk.Button(btn_frame, text="Clear Form", command=self.clear_form, bg="#dddddd", width=15).pack(side="left", padx=5)

    def create_master_tab_content(self, parent):
        search_frame = tk.LabelFrame(parent, text="Filter Master List", padx=5, pady=5)
        search_frame.pack(fill="x", padx=5, pady=5)

        tk.Label(search_frame, text="Colors:").pack(side="left", padx=2)
        self.filter_color = SearchableMultiSelectDropdown(search_frame, self.colors, "Select Colors")
        self.filter_color.pack(side="left", padx=5)
        tk.Label(search_frame, text="Categories:").pack(side="left", padx=2)
        self.filter_cat = SearchableMultiSelectDropdown(search_frame, self.card_types, "Select Types")
        self.filter_cat.pack(side="left", padx=5)
        tk.Label(search_frame, text="Costs:").pack(side="left", padx=2)
        self.filter_cost = SearchableMultiSelectDropdown(search_frame, [], "Select Cost")
        self.filter_cost.pack(side="left", padx=5)
        tk.Label(search_frame, text="Subtypes:").pack(side="left", padx=2)
        self.filter_sub = SearchableMultiSelectDropdown(search_frame, [], "Select Subtype")
        self.filter_sub.pack(side="left", padx=5)

        tk.Button(search_frame, text="Search", command=self.search_master, bg="#b3d9ff", width=10).pack(side="left", padx=15)
        tk.Button(search_frame, text="Reset", command=self.clear_search, bg="#dddddd").pack(side="left")

        tree_frame = tk.Frame(parent)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        if "Master" not in self.tree_dict: self.tree_dict["Master"] = {}
        self.tree_dict["Master"]["All"] = self.create_treeview(tree_frame)

    def start_session(self):
        self.session_active = True
        self.session_card_ids.clear()
        self.lbl_session_status.config(text="Status: Active", fg="green")
        messagebox.showinfo("Session Started", "Session tracking started.\nNew cards added will be recorded.")

    def end_session(self):
        count = len(self.session_card_ids)
        self.session_active = False
        self.lbl_session_status.config(text="Status: Inactive", fg="red")
        messagebox.showinfo("Session Ended", f"Session ended.\n{count} cards were added or modified.")

    def highlight_session(self):
        if not self.session_card_ids:
            messagebox.showinfo("Info", "No cards in current/last session to highlight.")
            return
        
        for main_cat in self.tree_dict:
            for sub_cat in self.tree_dict[main_cat]:
                tree = self.tree_dict[main_cat][sub_cat]
                
                # Apply highlighing while maintaining striping for non-highlighted
                for item_id in tree.get_children():
                    tags = []
                    # 1. Determine Striping
                    idx = tree.index(item_id)
                    if idx % 2 == 1: tags.append('odd')
                    else: tags.append('even')
                    
                    # 2. Determine Highlight
                    try:
                        if int(item_id) in self.session_card_ids:
                            tags = ['session_highlight'] # Highlight overrides striping
                    except: pass
                    
                    tree.item(item_id, tags=tuple(tags))

    def unhighlight_session(self):
        for main_cat in self.tree_dict:
            for sub_cat in self.tree_dict[main_cat]:
                tree = self.tree_dict[main_cat][sub_cat]
                for item_id in tree.get_children():
                    idx = tree.index(item_id)
                    tags = ('odd',) if idx % 2 == 1 else ('even',)
                    tree.item(item_id, tags=tags)

    def upsert_card(self, data):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, quantity FROM cards WHERE name=? AND card_category=? AND set_code IS ? AND collector_number IS ?", 
                      (data['name'], data['card_category'], data.get('set_code'), data.get('collector_number')))
        result = cursor.fetchone()
        row_id = None
        if result:
            row_id = result[0]
            cursor.execute("UPDATE cards SET quantity=? WHERE id=?", (result[1] + data['quantity'], row_id))
        else:
            cursor.execute("""INSERT INTO cards (name, color, quantity, card_category, mana_cost, power_toughness, subtypes, keywords, ability, loyalty, set_code, collector_number) 
                           VALUES (:name, :color, :quantity, :card_category, :mana_cost, :power_toughness, :subtypes, :keywords, :ability, :loyalty, :set_code, :collector_number)""", data)
            row_id = cursor.lastrowid
        
        if self.session_active and row_id:
            self.session_card_ids.add(row_id)
        return row_id

    def add_card(self):
        name = self.var_name.get().strip()
        cat = self.var_type.get()
        if not name or not cat:
            messagebox.showerror("Error", "Name/Category required.")
            return

        data = {
            "name": name, "color": self.var_color.get(), "quantity": self.var_quantity.get(),
            "card_category": cat, "mana_cost": self.var_mana_cost.get(), "power_toughness": self.var_pt.get(),
            "subtypes": self.var_subtypes.get(), "keywords": self.var_keywords.get(),
            "ability": self.var_ability.get(), "loyalty": self.var_loyalty.get() if self.var_loyalty.get() else None,
            "set_code": self.var_set_code.get().strip().upper(), "collector_number": self.var_collector_num.get().strip()
        }
        
        self.upsert_card(data)
        self.conn.commit()
        self.refresh_dropdowns()
        self.load_all_cards()
        self.clear_form()

    def load_all_cards(self):
        for main_cat in self.tree_dict:
            for sub_cat in self.tree_dict[main_cat]:
                self.tree_dict[main_cat][sub_cat].delete(*self.tree_dict[main_cat][sub_cat].get_children())
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, color, quantity, card_category, mana_cost, power_toughness, subtypes, keywords, ability, loyalty, set_code, collector_number FROM cards ORDER BY name ASC")
        for row in cursor.fetchall():
            self.insert_row_to_ui(row)

    def insert_row_to_ui(self, row):
        row_id, name, color_str, cat = row[0], row[1], str(row[2]) if row[2] else "Colorless", row[4]
        display = self.clean_row(row) 
        
        # Helper to insert with striping logic
        def insert_striped(tree_widget):
            # Calculate striping based on current count
            count = len(tree_widget.get_children())
            row_tags = ('odd',) if count % 2 == 1 else ('even',)
            tree_widget.insert("", "end", iid=row_id, values=display, tags=row_tags)

        # 1. Master List
        insert_striped(self.tree_dict["Master"]["All"])
        
        # 2. Colors
        dest_colors = []
        standard = ["White", "Blue", "Black", "Red", "Green"]
        detected = [c for c in standard if c in color_str]
        
        if len(detected) > 1: dest_colors.extend(["Multicolor"] + detected)
        elif len(detected) == 1: dest_colors.append(detected[0])
        else: dest_colors.append("Colorless")

        for c_tab in dest_colors:
            if c_tab in self.tree_dict:
                try: insert_striped(self.tree_dict[c_tab]["All"])
                except tk.TclError: pass
                if cat in self.tree_dict[c_tab]:
                    try: insert_striped(self.tree_dict[c_tab][cat])
                    except tk.TclError: pass

    def clean_row(self, row):
        l = list(row)
        l.pop(0) # remove ID
        # row: (name, color, qty, cat, cost, pt, sub, key, ab, loy, set, num)
        # Treeview expects: (Qty, Name, Set, ID#, Color, Category, Cost, P/T, Subtypes, Keywords, Ability, Loyalty)
        # l: [name, color, qty, cat, cost, pt, sub, key, ab, loy, set, num]
        name = l[0]
        color = l[1]
        qty = l[2]
        cat = l[3]
        cost = l[4]
        pt = l[5]
        sub = l[6]
        key = l[7]
        ab = l[8]
        loy = l[9]
        set_code = l[10]
        num = l[11]
        
        ordered = [qty, name, set_code, num, color, cat, cost, pt, sub, key, ab, loy]
        cleaned = []
        for x in ordered:
            if x is None or str(x).lower() == 'nan': cleaned.append("")
            else: cleaned.append(str(x).replace('\n', ' '))
        return cleaned

    def search_master(self):
        self.tree_dict["Master"]["All"].delete(*self.tree_dict["Master"]["All"].get_children())
        sel_colors = self.filter_color.get_selected()
        sel_cats = self.filter_cat.get_selected()
        sel_costs = self.filter_cost.get_selected()
        sel_subs = self.filter_sub.get_selected()

        query = "SELECT id, name, color, quantity, card_category, mana_cost, power_toughness, subtypes, keywords, ability, loyalty, set_code, collector_number FROM cards WHERE 1=1"
        params = []

        if sel_colors:
            clauses = [f"color LIKE ?" for _ in sel_colors]
            query += " AND (" + " OR ".join(clauses) + ")"
            params.extend([f"%{c}%" for c in sel_colors])
        if sel_cats:
            placeholders = ",".join("?" * len(sel_cats))
            query += f" AND card_category IN ({placeholders})"
            params.extend(sel_cats)
        if sel_costs:
            clauses = ["mana_cost = ?" for _ in sel_costs]
            query += " AND (" + " OR ".join(clauses) + ")"
            params.extend(sel_costs)
        if sel_subs:
            clauses = ["subtypes LIKE ?" for _ in sel_subs]
            query += " AND (" + " OR ".join(clauses) + ")"
            params.extend([f"%{s}%" for s in sel_subs])

        query += " ORDER BY name ASC"
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        for row in cursor.fetchall():
            self.insert_row_to_ui(row)

    def clear_search(self):
        self.filter_color.clear_selection()
        self.filter_cat.clear_selection()
        self.filter_cost.clear_selection()
        self.filter_sub.clear_selection()
        self.load_all_cards()

    def update_fields_visibility(self, event=None):
        for w in self.dynamic_frame.winfo_children(): w.grid_forget()
        ctype = self.var_type.get()
        r, c = 0, 0
        show = {"mana":True, "pt":False, "sub":False, "key":False, "ab":False, "loy":False}
        if ctype == "Land": show["mana"]=False; show["ab"]=True
        elif "Creature" in ctype or "Vehicle" in ctype: show["pt"]=True; show["sub"]=True; show["key"]=True
        elif ctype == "Planeswalker": show["loy"]=True
        if ctype in ["Legendary Creature", "Creature", "Artifact Creature"]: show["sub"]=True; show["key"]=True

        widgets = [("mana", self.lbl_mana, self.ent_mana), ("pt", self.lbl_pt, self.ent_pt), ("sub", self.lbl_sub, self.ent_sub),
                   ("key", self.lbl_key, self.ent_key), ("ab", self.lbl_ab, self.ent_ab), ("loy", self.lbl_loy, self.ent_loy)]
        for key, lbl, ent in widgets:
            if show[key]:
                lbl.grid(row=r, column=c, sticky="e"); ent.grid(row=r, column=c+1, sticky="w", padx=5)
                c += 2
                if c > 6: r+=1; c=0

    def clear_form(self):
        self.editing_card_id = None
        self.btn_submit.config(text="Add Card", bg="#dddddd", command=self.add_card)
        self.btn_delete.config(state="disabled")
        for v in [self.var_name, self.var_color, self.var_type, self.var_mana_cost, self.var_pt, self.var_subtypes, self.var_keywords, self.var_ability, self.var_loyalty, self.var_set_code, self.var_collector_num]: v.set("")
        self.var_quantity.set(1)
        self.update_fields_visibility()

    def on_tree_double_click(self, event):
        tree = event.widget
        selection = tree.selection()
        if not selection: return
        item_id = selection[0] 
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM cards WHERE id=?", (item_id,))
        row = cursor.fetchone()
        if row:
            self.editing_card_id = row[0]
            self.var_name.set(row[1])
            self.var_color.set(row[2] if row[2] else "")
            self.var_quantity.set(row[3])
            self.var_type.set(row[4])
            self.var_mana_cost.set(row[5] if row[5] else "")
            self.var_pt.set(row[6] if row[6] else "")
            self.var_subtypes.set(row[7] if row[7] else "")
            self.var_keywords.set(row[8] if row[8] else "")
            self.var_ability.set(row[9] if row[9] else "")
            self.var_loyalty.set(row[10] if row[10] else "")
            self.var_set_code.set(row[11] if row[11] else "")
            self.var_collector_num.set(row[12] if row[12] else "")
            
            self.update_fields_visibility()
            self.btn_submit.config(text="Save Changes", bg="#b3d9ff", command=self.save_edits)
            self.btn_delete.config(state="normal")

    def save_edits(self):
        if self.editing_card_id is None: return
        try:
            name = self.var_name.get().strip()
            cat = self.var_type.get()
            cursor = self.conn.cursor()
            query = """UPDATE cards SET name=?, color=?, quantity=?, card_category=?, mana_cost=?, power_toughness=?, subtypes=?, keywords=?, ability=?, loyalty=?, set_code=?, collector_number=? WHERE id=?"""
            data = (name, self.var_color.get(), self.var_quantity.get(), cat, self.var_mana_cost.get(), self.var_pt.get(), self.var_subtypes.get(), self.var_keywords.get(), self.var_ability.get(), self.var_loyalty.get() if self.var_loyalty.get() else None, self.var_set_code.get().strip().upper(), self.var_collector_num.get().strip(), self.editing_card_id)
            cursor.execute(query, data)
            self.conn.commit()
            
            if self.session_active: self.session_card_ids.add(self.editing_card_id)

            self.refresh_dropdowns()
            self.load_all_cards()
            self.clear_form()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def delete_card(self):
        if self.editing_card_id is None: return
        if messagebox.askyesno("Confirm", f"Delete '{self.var_name.get()}'?"):
            self.conn.execute("DELETE FROM cards WHERE id=?", (self.editing_card_id,))
            self.conn.commit()
            self.refresh_dropdowns()
            self.load_all_cards()
            self.clear_form()

    def on_file_drop(self, event):
        file_path = event.data
        if file_path.startswith('{') and file_path.endswith('}'): file_path = file_path[1:-1]
        if file_path.endswith('.xlsx') or file_path.endswith('.xls'):
            self.process_excel_file(file_path)
            self.conn.commit()
            self.refresh_dropdowns()
            self.load_all_cards()
            messagebox.showinfo("Import Successful", f"Imported: {os.path.basename(file_path)}")
        else: messagebox.showerror("Error", "Please drop a valid Excel file (.xlsx, .xls)")

    def process_excel_file(self, file_path):
        xls = pd.read_excel(file_path, sheet_name=None, header=None)
        cat_map = {"Not Basic Lands": "Land", "Legendary Creatures": "Legendary Creature", "Ledgendary Creatures": "Legendary Creature", "Creatures": "Creature", "Planeswalkers": "Planeswalker", "Instants": "Instant", "Sorceries": "Sorcery", "Legendary Enchantments - Backgrounds": "Legendary Enchantment", "Ledgendary Enchantments - Backgrounds": "Legendary Enchantment", "Legendary Enchantment Creature - Backgrounds": "Legendary Creature", "Ledgendary Enchantment Creature - Backgrounds": "Legendary Creature", "Enchantments": "Enchantment", "Legendary Artifact": "Legendary Artifact", "Ledgendary Artifact": "Legendary Artifact", "Ledgendary Artifacts": "Legendary Artifact", "Artifacts": "Artifact", "Artifact Equiment": "Artifact Equipment", "Artifact Vehicle": "Artifact Vehicle", "Artifact Treasure": "Artifact Treasure", "Atrifact Creatures": "Artifact Creature", "Articaft Cretures": "Artifact Creature"}
        for sheet_name, df in xls.items():
            if sheet_name in ["All", "Statistics"] or df.empty: continue
            j = 0
            while j < df.shape[1]:
                cat_raw = df.iloc[0, j]
                if pd.notna(cat_raw) and isinstance(cat_raw, str) and cat_raw != "Total Cards":
                    mapped_cat = cat_map.get(cat_raw.strip(), cat_raw.strip())
                    k = j
                    block_cols = []
                    while k < df.shape[1]:
                        header = df.iloc[1, k]
                        if pd.isna(header): break
                        block_cols.append(str(header).strip())
                        k += 1
                    if not block_cols: j += 1; continue
                    block_data = df.iloc[2:, j:k].copy()
                    block_data.columns = block_cols
                    if "Name" in block_data.columns:
                        block_data = block_data.dropna(subset=["Name"])
                        for _, row in block_data.iterrows():
                            c_val = row["Color"] if "Color" in row and pd.notna(row["Color"]) else sheet_name
                            data = {"name": row["Name"], "card_category": mapped_cat, "quantity": int(row["Quantity"]) if "Quantity" in row and pd.notna(row["Quantity"]) else 1, "color": c_val, "mana_cost": str(row["Cost"]) if "Cost" in row and pd.notna(row["Cost"]) else None, "power_toughness": str(row["Power/Toughness"]) if "Power/Toughness" in row and pd.notna(row["Power/Toughness"]) else None, "subtypes": str(row["Types"]) if "Types" in row and pd.notna(row["Types"]) else None, "keywords": str(row["Keywords"]) if "Keywords" in row and pd.notna(row["Keywords"]) else None, "ability": str(row["Ability"]) if "Ability" in row and pd.notna(row["Ability"]) else None, "loyalty": int(row["Base Loyalty"]) if "Base Loyalty" in row and pd.notna(row["Base Loyalty"]) else None, "set_code": None, "collector_number": None}
                            for key, val in data.items():
                                if str(val) == 'nan': data[key] = None
                            self.upsert_card(data)
                    j = k
                else: j += 1

    def create_color_tab_content(self, parent, color_name):
        inner_notebook = ttk.Notebook(parent)
        inner_notebook.pack(fill="both", expand=True, padx=5, pady=5)
        if color_name not in self.tree_dict: self.tree_dict[color_name] = {}
        all_frame = tk.Frame(inner_notebook)
        inner_notebook.add(all_frame, text=f" All {color_name} ")
        self.tree_dict[color_name]["All"] = self.create_treeview(all_frame)
        for ctype in self.card_types:
            type_frame = tk.Frame(inner_notebook)
            inner_notebook.add(type_frame, text=f" {ctype} ")
            self.tree_dict[color_name][ctype] = self.create_treeview(type_frame)

    def create_treeview(self, parent_frame):
        columns = ("Qty", "Name", "Set", "ID#", "Color", "Category", "Cost", "P/T", "Subtypes", "Keywords", "Ability", "Loyalty")
        tree = ttk.Treeview(parent_frame, columns=columns, show="headings")
        
        # Configure Row Striping Tags
        tree.tag_configure('odd', background='#F0F0F0') # Light Grey
        tree.tag_configure('even', background='#FFFFFF') # White
        tree.tag_configure('session_highlight', background='#FFFF99') # Yellow Highlight

        col_widths = [40, 250, 60, 60, 80, 120, 60, 50, 180, 120, 300, 50]
        for col, width in zip(columns, col_widths):
            tree.heading(col, text=col)
            tree.column(col, width=width, minwidth=50)
        v_scroll = ttk.Scrollbar(parent_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscroll=v_scroll.set)
        v_scroll.pack(side="right", fill="y")
        h_scroll = ttk.Scrollbar(parent_frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(xscroll=h_scroll.set)
        h_scroll.pack(side="bottom", fill="x")
        tree.pack(side="left", fill="both", expand=True)
        tree.bind("<Double-1>", self.on_tree_double_click)
        return tree

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = MTGCardManager(root)
    root.mainloop()
