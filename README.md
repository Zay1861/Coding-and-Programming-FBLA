# Local Lift

## Project Description

**Local Lift** is a desktop application built in **Python** using **PySide6**. The program helps users discover and support local businesses by allowing them to search for businesses by location and category, save favorites, add reviews, and view useful business information in one interface.

The application is designed to solve a practical community problem: making it easier for people to find and interact with local businesses instead of relying only on large chain stores. Local Lift combines local data storage with external business data imports to create an organized and user-friendly experience.

---

## Main Features

* Search businesses by **location**
* Filter by **category**
* Filter and sort by **rating**
* View business **name, category, address, and rating**
* Save businesses to a **Favorites** tab
* Add and view **customer reviews**
* View available **deals**
* Display business **statistics**
* Import business data from:

  * **Yelp Academic Dataset**
  * **OpenStreetMap (Overpass API)**

---

## How the Program Works

When the program starts, the user is shown a graphical interface with a search bar, category selector, rating filter, and business results table. The user can enter a location and optional category, then press **Search** to load matching businesses.

The program gathers business information from stored JSON data and can also import additional businesses from external sources. Results are displayed in a table with clear columns for business name, category, address, and rating. Users can then interact with the data by saving favorites, adding reviews, viewing deals, or examining summary statistics.

---

## Software and Tools Used

* **Python**
* **PySide6** for the graphical user interface
* **JSON** for local data storage
* **Requests** for web/API access
* **OpenStreetMap Overpass API**
* **Yelp Academic Dataset**

---

## Program Structure

The program is organized into logical sections so that the code is readable and maintainable.

### Data Classes

* `Review` stores a rating, text, and timestamp
* `Business` stores business details and related reviews

### Core Functions

* `normalize_name()` standardizes business names
* `is_big_chain()` filters out major chain businesses
* `load_data()` and `save_data()` manage local JSON storage
* `build_businesses()` converts raw data into business objects
* `import_yelp_academic_businesses()` imports records from Yelp data
* `fetch_from_overpass()` imports business information from OpenStreetMap
* `ensure_numeric_ids_for_raw()` guarantees unique IDs for saved businesses

### User Interface

The application interface is managed through the `QtMainWindow` class, which handles:

* searching
* filtering
* favorites
* reviews
* statistics
* saving data
* help information

---

## Input and Validation

The program includes validation to improve reliability and prevent errors:

* Empty searches are blocked
* Review ratings are limited to valid values
* Review submission includes a verification step
* Missing files and import failures are handled with messages
* Favorite records are normalized before being saved

---

## Data Storage

Local Lift stores data in a JSON file so that information such as imported businesses, reviews, and favorites can persist between sessions. This allows the user to reopen the application without losing previous work.

---

## Installation Requirements

* Python **3.8 or higher**
* `pip`
* Recommended libraries:

  * `PySide6`
  * `requests`

Install dependencies with:

```bash
python3 -m pip install PySide6 requests
```

---

## How to Run

Run the application with:

```bash
python3 "Coding and Programming Collab FIle.py"
```

If the file is in another folder, replace the path with the correct one.

---

## Files Included

* `Coding and Programming Collab FIle.py` — main program
* `coding_programming_data.json` — local saved data
* `local_lift_logo.png` — application icon/logo
* `requirements.txt` — dependency list

---

## Intended User Experience

The program is designed to be simple and intuitive. Users can quickly search, browse, and manage business data without needing technical knowledge. The interface emphasizes clarity, accessibility, and straightforward navigation so that all main actions are easy to locate and use.

---

## Summary

Local Lift is a complete desktop solution for discovering and interacting with local businesses. It combines clean design, useful features, organized code structure, and multiple data sources to create an application that is both practical and user-friendly.
