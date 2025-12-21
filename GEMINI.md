# Project Overview

This project is a Python-based application for managing a Magic: The Gathering (MTG) card collection. It provides a graphical user interface (GUI) built with Tkinter to easily sort, view, and manage cards. The application uses an SQLite database to store the card information.

## Key Features

*   **Card Management:** Add, edit, and delete cards from your collection.
*   **Card Browser:** View your collection in a filterable and searchable table.
*   **Data Import:** Import card data from Excel files using drag and drop.
*   **GUI:** A user-friendly interface with tabs for each color and a master list.

## Technologies Used

*   **Python:** The core programming language.
*   **Tkinter:** Used for the GUI.
*   **SQLite:** For the database.
*   **Pandas:** For data manipulation and Excel file reading.
*   **Jupyter Notebook:** The development environment.

# Building and Running

To run this project, you will need to have Python 3 and the required dependencies installed.

1.  **Set up the virtual environment:** The project includes a `.venv` directory. You can activate it using:
    ```bash
    source .venv/bin/activate
    ```
2.  **Install dependencies:** The project uses `uv` to manage dependencies. You can install them with:
    ```bash
    uv pip install pandas openpyxl tkinterdnd2
    ```
3.  **Run the application:** The main application logic is in the `sorter.py` script. You can run it using:
    ```bash
    python sorter.py
    ```

# Development Conventions

*   The application is developed in the `sorter.py` script.
*   Card data is stored in a SQLite database named `mtg_collection.db`.
*   The GUI is built using Tkinter.
*   The application supports importing data from Excel files.

