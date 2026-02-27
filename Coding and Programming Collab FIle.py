from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional

# Add required standard imports and detect requests availability
import os, sys, json, re, time, random
try:
    import requests
    REQUESTS_AVAILABLE = True
except Exception:
    REQUESTS_AVAILABLE = False

DATA_FILE = os.path.join(os.path.dirname(__file__), "coding_programming_data.json")
YELP_BUSINESS_FILE = "/Users/zayanjami/Downloads/Yelp JSON/yelp_dataset/yelp_academic_dataset_business.json"
AUTO_IMPORT_CITY = "Las Vegas"
AUTO_IMPORT_LIMIT = 200

# Unique program name used in window title and header label
PROGRAM_NAME = "Local Lift"
# Path to app logo (place local_lift_logo.png next to the script or update path)
LOGO_PATH = os.path.join(os.path.dirname(__file__), "local_lift_logo.png")

BIG_CHAINS = [
    "mcdonald's", "starbucks", "walmart", "subway", "burger king", "wendy's", "taco bell",
    "kfc", "pizza hut", "domino's", "dunkin'", "chipotle", "panera", "target", "costco",
    "panda express", "chick-fil-a", "popeyes", "arby's", "jack in the box", "little caesars",
    "7-eleven", "krispy kreme", "in-n-out", "five guys", "buffalo wild wings", "red lobster",
    "olive garden", "outback", "applebee's", "ihop", "denny's", "cheesecake factory", "bj's restaurant",
    "chili's", "wingstop", "raising cane's", "shake shack", "blaze pizza", "mod pizza", "safeway",
    "whole foods", "aldi", "sprouts", "winco", "publix", "heb", "kroger", "meijer", "wegmans",
    "trader joe", "aldi sud", "aldi nord", "aldi inc", "aldi group"
]

# Replace existing is_big_chain with a normalization-aware check
def normalize_name(s: str) -> str:
    """Return a normalized string with only lowercase alphanumerics."""
    if not s:
        return ""
    return re.sub(r'[^a-z0-9]', '', s.lower())

def is_big_chain(name: str) -> bool:
    """Return True if the business name matches a known big chain (punctuation/space-insensitive)."""
    if not name:
        return False
    norm = normalize_name(name)
    for chain in BIG_CHAINS:
        if normalize_name(chain) in norm:
            return True
    return False

# Add lightweight logging and OSM tag normalization utilities
LOG_PATH = os.path.expanduser("~/.business_app.log")

def log(msg: str):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def normalize_osm_tags(user: str) -> str:
    s = (user or "").strip().lower()
    if not s:
        return "restaurant|cafe|bar|pub|fast_food|coffee|bakery|ice_cream|deli"
    aliases = {
        "bars": "bar|pub",
        "bar": "bar|pub",
        "pubs": "pub|bar",
        "restaurants": "restaurant|fast_food",
        "restaurant": "restaurant|fast_food",
        "cafes": "cafe|coffee",
        "cafe": "cafe|coffee",
        "coffee": "cafe|coffee",
        "coffee shops": "cafe|coffee",
    }
    return aliases.get(s, s)

@dataclass
class Review:
    rating: int
    text: str
    timestamp: float = field(default_factory=time.time)

@dataclass
class Business:
    id: int
    name: str
    category: str
    address: str
    deal: str = ""
    reviews: List[Review] = field(default_factory=list)
    def avg_rating(self):
        return sum(r.rating for r in self.reviews) / len(self.reviews) if self.reviews else 0.0
    def review_count(self):
        return len(self.reviews)

def default_data():
    return {"businesses": [
        {"id": 1, "name": "Chuckeys Cheesesteak", "category": "food", "address": "123 Jolly Ave", "deal": "10 dollars off: JOLLY100", "reviews": []},
        {"id": 2, "name": "Corner Book Nook", "category": "retail", "address": "55 Maple Ave", "deal": "Buy 2 get 1 (weekends)", "reviews": []},
        {"id": 3, "name": "QuickFix Phone Repair", "category": "services", "address": "200 Oak Blvd", "deal": "Free screen protector", "reviews": []},
    ], "favorites": []}

def save_data(data):
    """Save data to DATA_FILE. Create a backup of the previous file as *_backup.json before overwriting."""
    try:
        if os.path.exists(DATA_FILE):
            backup_file = DATA_FILE.replace('.json', '_backup.json')
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as src, open(backup_file, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
                try:
                    log(f"Created backup: {backup_file}")
                except Exception:
                    pass
            except Exception:
                # continue even if backup fails
                pass
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        # Best-effort fallback: try writing without pretty formatting
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception:
            pass

def load_data():
    if not os.path.exists(DATA_FILE):
        d = default_data(); save_data(d); return d
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = default_data(); save_data(data); return data
    if not isinstance(data, dict):
        data = default_data(); save_data(data)
    data.setdefault("businesses", []); data.setdefault("favorites", [])
    if not data["businesses"]:
        data = default_data(); save_data(data)
    return data

def build_businesses(raw):
    out = []
    for b in raw.get("businesses", []):
        if isinstance(b, Business): out.append(b); continue
        if not isinstance(b, dict): continue
        reviews = [Review(r.get("rating",0), r.get("text",""), r.get("timestamp",time.time())) for r in b.get("reviews", []) if isinstance(r, dict)]
        out.append(Business(b.get("id",0), b.get("name",""), b.get("category",""), b.get("address",""), b.get("deal",""), reviews))
    return out

def persist_businesses(raw, businesses):
    raw["businesses"] = [asdict(b) for b in businesses]

def import_yelp_academic_businesses(path, city_filter="", limit=500, category_filter=None):
    res = []
    city_filter = city_filter.lower().strip()
    log_path = os.path.expanduser("~/yelp_debug.log")
    with open(path, "r", encoding="utf-8") as f, open(log_path, "a", encoding="utf-8") as logf:
        for line in f:
            try:
                obj = json.loads(line)
            except:
                continue
            name = obj.get("name", "").lower().strip()
            if is_big_chain(name):
                continue 
            city_val = obj.get("city", "").lower().strip()
            logf.write(f"Loaded: {obj.get('name','')} | City: {city_val} | Categories: {obj.get('categories','')}\n")
            if city_filter and city_filter not in city_val:
                continue
            # Improved category filtering
            if category_filter:
                cats = obj.get("categories", "")
                cat_list = [c.strip().lower() for c in cats.split(",") if c.strip()]
                filter_val = category_filter.lower().strip()
                if not any(filter_val in c for c in cat_list):
                    continue
            # Add Yelp review as a Review dict
            stars = obj.get("stars", None)
            yelp_review = []
            if stars is not None:
                try:
                    stars_int = int(round(float(stars)))
                except Exception:
                    stars_int = 0
                yelp_review = [{
                    "rating": stars_int,
                    "text": "Imported from Yelp (Yelp average rating)",
                    "timestamp": time.time()
                }]
            res.append({
                "external_id": obj.get("business_id"),
                "name": obj.get("name", ""),
                "category": obj.get("categories", ""),
                "address": f"{obj.get('address','')}, {obj.get('city','')}",
                "deal": "",
                "reviews": yelp_review
            })
            if len(res) >= limit:
                break
    return res
YELP_SEARCH_URL = "https://api.yelp.com/v3/businesses/search"
CONFIG_PATH = os.path.expanduser("~/.business_app_config.json")
def get_saved_api_key():
    env = os.environ.get("YELP_API_KEY")
    if env: return env
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            return cfg.get("yelp_api_key")
    except: pass
    return None
def save_api_key_to_config(key):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"yelp_api_key": key}, f, indent=2)
        try: os.chmod(CONFIG_PATH, 0o600)
        except: pass
        return True
    except: return False
def integrate_yelp_results(raw, yelp_items):
    raw.setdefault("businesses", [])
    ids = [b.get("id") for b in raw["businesses"] if isinstance(b, dict)]
    next_id = max([int(i) for i in ids if isinstance(i,int) or (isinstance(i,str) and i.isdigit())]+[0]) + 1
    for item in yelp_items:
        entry = {"id": next_id, "name": item.get("name",""), "category": item.get("category",""), "address": item.get("address",""), "deal": item.get("deal",""), "reviews": item.get("reviews",[])}
        if item.get("external_id"): entry["external_id"] = item["external_id"]
        raw["businesses"].append(entry)
        next_id += 1
    return len(yelp_items)

def fetch_from_overpass(location: str, tags: str = "restaurant|cafe|bar", limit: int = 50) -> List[Dict]:
    """Fetch POIs from OpenStreetMap using Nominatim + Overpass.
    Uses a center-point radius search instead of a giant city bbox so that
    large places like Chicago/Manhattan do not time out.
    """
    tags = (tags or "").strip().lower()

    if not isinstance(location, str) or not location.strip():
        return []

    if not REQUESTS_AVAILABLE:
        return []

    if tags in {"restaurant|cafe|bar", "restaurant"}:
        tags = "restaurant|cafe|bar|fast_food|pub|coffee|bakery|ice_cream|deli"
    elif not tags:
        tags = "restaurant|cafe|bar|fast_food|pub|coffee|bakery|ice_cream|deli"

    LOG_PATH = os.path.expanduser("~/.business_app_osm_import.log")

    def _log(msg: str) -> None:
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as lf:
                lf.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
        except Exception:
            pass

    def run_overpass_query(q: str) -> List[Dict]:
        url = "https://overpass-api.de/api/interpreter"
        try:
            q_snippet = q[:250].replace("\n", " ")
        except Exception:
            q_snippet = q[:250]
        _log(f"Overpass QL start: {q_snippet}...")
        try:
            resp = requests.post(url, data={"data": q}, timeout=45)
            resp.raise_for_status()
            data = resp.json()
            elems = data.get("elements", []) if isinstance(data, dict) else []
            _log(f"Overpass returned {len(elems)} elements")
            return elems
        except Exception as e:
            _log(f"Overpass error: {e}")
            try:
                _log(f"Overpass raw response: {resp.text[:500]}")
            except Exception:
                pass
            return []

    def _convert_elements(elems: List[Dict], limit: int) -> List[Dict]:
        out: List[Dict] = []
        seen = set()

        for elem in elems:
            tags_dict = elem.get("tags", {}) or {}
            name = tags_dict.get("name", "")

            if is_big_chain(name):
                continue

            addr_parts = []
            for k in ("addr:housenumber", "addr:street", "addr:city", "addr:postcode"):
                v = tags_dict.get(k)
                if v:
                    addr_parts.append(v)

            address = ", ".join(addr_parts) if addr_parts else tags_dict.get("addr:full", "")
            category = tags_dict.get("amenity") or tags_dict.get("shop") or tags_dict.get("craft") or ""

            key = (name.strip().lower(), address.strip().lower(), category.strip().lower())
            if key in seen:
                continue
            seen.add(key)

            out.append({
                "external_id": f"{elem.get('type')}/{elem.get('id')}",
                "name": name or category or "(no name)",
                "category": category,
                "address": address,
                "deal": "",
                "reviews": [],
            })

            if len(out) >= limit:
                break

        return out

    # Step 1: geocode location to a center point
    try:
        nom_url = "https://nominatim.openstreetmap.org/search"
        headers = {
            "User-Agent": "LocalLift/1.0 (student desktop app)",
            "Accept": "application/json"
        }

        _log(f"Nominatim query: {location}")
        resp = requests.get(
            nom_url,
            params={"q": location, "format": "json", "limit": 1},
            headers=headers,
            timeout=15
        )
        resp.raise_for_status()
        results = resp.json()

        if results:
            lat = float(results[0]["lat"])
            lon = float(results[0]["lon"])

            # radius in meters; use a manageable search size for big cities
            radius = 8000
            if any(x in location.lower() for x in ["manhattan", "new york", "chicago"]):
                radius = 6000

            q_center = f'''[out:json][timeout:25];
(
  node["amenity"~"{tags}", i](around:{radius},{lat},{lon});
  way["amenity"~"{tags}", i](around:{radius},{lat},{lon});
  relation["amenity"~"{tags}", i](around:{radius},{lat},{lon});

  node["shop"~"{tags}", i](around:{radius},{lat},{lon});
  way["shop"~"{tags}", i](around:{radius},{lat},{lon});
  relation["shop"~"{tags}", i](around:{radius},{lat},{lon});

  node["craft"~"{tags}", i](around:{radius},{lat},{lon});
  way["craft"~"{tags}", i](around:{radius},{lat},{lon});
  relation["craft"~"{tags}", i](around:{radius},{lat},{lon});
);
out center;'''

            elems = run_overpass_query(q_center)
            if elems:
                return _convert_elements(elems, limit)

    except Exception as e:
        _log(f"Nominatim/geocode error: {e}")

    # Step 2: fallback area search
    try:
        safe_loc = re.escape(location.strip())
        q_name = f'''[out:json][timeout:25];
area["name"~"^{safe_loc}$", i]->.searchArea;
(
  node["amenity"~"{tags}", i](area.searchArea);
  way["amenity"~"{tags}", i](area.searchArea);
  relation["amenity"~"{tags}", i](area.searchArea);

  node["shop"~"{tags}", i](area.searchArea);
  way["shop"~"{tags}", i](area.searchArea);
  relation["shop"~"{tags}", i](area.searchArea);

  node["craft"~"{tags}", i](area.searchArea);
  way["craft"~"{tags}", i](area.searchArea);
  relation["craft"~"{tags}", i](area.searchArea);
);
out center;'''

        elems = run_overpass_query(q_name)
        if elems:
            return _convert_elements(elems, limit)

    except Exception as e:
        _log(f"Area fallback error: {e}")

    _log("No POIs found for provided location/tags")
    return []
    def _log(msg: str) -> None:
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as lf:
                lf.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
        except Exception:
            pass

    def run_overpass_query(q: str) -> List[Dict]:
        url = "https://overpass-api.de/api/interpreter"
        # avoid backslash inside f-string expression by preparing a snippet first
        try:
            q_snippet = q[:200].replace("\n", " ")
        except Exception:
            q_snippet = q[:200]
        _log(f"Overpass QL start: {q_snippet}...")
        try:
            resp = requests.post(url, data={"data": q}, timeout=40)
            resp.raise_for_status()
            data = resp.json()
            elems = data.get("elements", []) if isinstance(data, dict) else []
            _log(f"Overpass returned {len(elems)} elements")
            return elems
        except Exception as e:
            _log(f"Overpass error: {e}")
            return []

 

# Add helpers to support automatic import on startup (Option A)

def get_saved_default_location() -> Optional[str]:
    """Return a default location for Yelp searches from the environment or local config file, if present."""
    # prefer explicit environment variable first
    env = os.environ.get("YELP_DEFAULT_LOCATION")
    if env:
        return env
    # next try config file
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            loc = cfg.get("yelp_default_location")
            if loc:
                return loc
    except Exception:
        pass
    return None

def extract_yelp_categories(path):
    categories = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    cats = obj.get("categories", "")
                    if cats:
                        for cat in cats.split(","):
                            categories.add(cat.strip())
                except Exception:
                    continue
    except Exception:
        pass
    return sorted(categories)

def extract_yelp_category_strings(path):
    category_strings = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    cats = obj.get("categories", "")
                    if cats:
                        category_strings.add(cats.strip())
                except Exception:
                    continue
    except Exception:
        pass
    return sorted(category_strings)

# ----------------- PYSIDE6 / QT UI (preferred) ---------------------------

# restore PySide6 import detection used by the UI
try:
    from PySide6 import QtWidgets, QtGui, QtCore
    PYSIDE_AVAILABLE = True
except Exception:
    PYSIDE_AVAILABLE = False

if PYSIDE_AVAILABLE:
    class QtMainWindow(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle(f"{PROGRAM_NAME} - Qt")
            self.resize(1150, 720)
            self.setStyleSheet("""
                QMainWindow { background: #0B1220; }
                QWidget#centralwidget, QWidget { background: #0B1220; }
                QFrame#Card {
                    background: #0B1220;
                    border-radius: 16px;
                }
                QLabel#Title {
                    font-size: 22px;
                    font-weight: 800;
                    color: #F8FAFC;
                }
                QLabel#Subtitle {
                    font-size: 13px;
                    color: #94A3B8;
                }
                QPushButton {
                    background-color: #2563eb;
                    color: #fff;
                    border-radius: 10px;
                    padding: 10px 22px;
                    font-size: 16px;
                    font-weight: 600;
                    border: none;
                    margin: 0 2px;
                }
                QPushButton:hover {
                    background-color: #174ea6;
                }
                QTableView {
                    background: #23272e;
                    color: #f5f6fa;
                    border-radius: 8px;
                    border: 1px solid #353b48;
                    font-size: 16px;
                    font-weight: 500;
                    padding: 10px;
                    gridline-color: #353b48;
                    selection-background-color: #dbeafe;
                    selection-color: #181818;
                    outline: none;
                }
                QTableView::item {
                    border-bottom: 1px solid #353b48;
                    padding: 10px 0;
                }
                QTableView::item:hover {
                    background: #2d3240;
                }
                QHeaderView::section {
                    background: #2563eb;
                    color: #fff;
                    font-size: 17px;
                    font-weight: bold;
                    padding: 6px 10px;
                    border: none;
                    border-radius: 4px 4px 0 0;
                    margin: 0;
                }
                QInputDialog, QMessageBox {
                    background: #181f2f;
                    color: #fff;
                    border-radius: 12px;
                }
                QInputDialog QLabel, QMessageBox QLabel {
                    color: #fff;
                    font-size: 16px;
                }
                QInputDialog QLineEdit, QMessageBox QLineEdit {
                    background: #23272e;
                    color: #fff;
                    border: 1px solid #353b48;
                    border-radius: 6px;
                    padding: 6px 8px;
                    font-size: 16px;
                }
                QInputDialog QPushButton, QMessageBox QPushButton {
                    background: #2563eb;
                    color: #fff;
                    border-radius: 8px;
                    font-size: 16px;
                    font-weight: 600;
                    padding: 8px 24px;
                }
                QInputDialog QPushButton:hover, QMessageBox QPushButton:hover {
                    background: #174ea6;
                }
            """)

            container = QtWidgets.QWidget()
            self.setCentralWidget(container)
            root = QtWidgets.QVBoxLayout(container)
            root.setContentsMargins(24, 24, 24, 24)
            root.setSpacing(18)

            # Header card
            header_card = QtWidgets.QFrame()
            header_card.setObjectName("Card")
            header_layout = QtWidgets.QHBoxLayout(header_card)
            header_layout.setContentsMargins(18, 14, 18, 14)
            header_layout.setSpacing(12)

            # Left: title + subtitle
            title_col = QtWidgets.QVBoxLayout()
            title_col.setSpacing(2)
            # small logo label (falls back to blank if file missing)
            logo_label = QtWidgets.QLabel()
            logo_label.setFixedSize(48, 48)
            try:
                pix = None
                # Prefer a local cached logo
                if os.path.exists(LOGO_PATH):
                    pix = QtGui.QPixmap(LOGO_PATH)
                else:
                    logo_url = "https://chatgpt.com/backend-api/estuary/content?id=file_00000000038471fd8937cbdde8e6a188&ts=492265&p=fs&cid=1&sig=d4720d3e15fa5d4e58b5e566d3ea2e79112ed58bdb2a09c69e2b2086f0bc408e&v=0"
                    try:
                        # try requests first if available
                        if REQUESTS_AVAILABLE:
                            resp = requests.get(logo_url, timeout=10)
                            if resp.status_code == 200:
                                data = resp.content
                                pix = QtGui.QPixmap()
                                pix.loadFromData(data)
                                # cache locally
                                try:
                                    with open(LOGO_PATH, "wb") as wf:
                                        wf.write(data)
                                except Exception:
                                    pass
                        else:
                            # fallback to urllib which is in stdlib
                            try:
                                import urllib.request as _ur
                                with _ur.urlopen(logo_url, timeout=10) as u:
                                    data = u.read()
                                    pix = QtGui.QPixmap()
                                    pix.loadFromData(data)
                                    try:
                                        with open(LOGO_PATH, "wb") as wf:
                                            wf.write(data)
                                    except Exception:
                                        pass
                            except Exception:
                                pix = None
                    except Exception:
                        pix = None
                if pix is not None and not pix.isNull():
                    pix = pix.scaled(48, 48, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                    logo_label.setPixmap(pix)
                    try:
                        # prefer using the cached file for window icon when available
                        if os.path.exists(LOGO_PATH):
                            self.setWindowIcon(QtGui.QIcon(LOGO_PATH))
                        else:
                            self.setWindowIcon(QtGui.QIcon(pix))
                    except Exception:
                        pass
            except Exception:
                pass

            title_h = QtWidgets.QHBoxLayout()
            title_h.setSpacing(8)
            title_h.addWidget(logo_label, 0, QtCore.Qt.AlignVCenter)
            title = QtWidgets.QLabel(PROGRAM_NAME)
            title.setObjectName("Title")
            title.setStyleSheet("color: #ffffff;")
            title_h.addWidget(title)
            title_col.addLayout(title_h)
            subtitle = QtWidgets.QLabel("Browse, favorite, review, and import local businesses")
            subtitle.setObjectName("Subtitle")
            subtitle.setStyleSheet("color: #ffffff;")
            title_col.addWidget(subtitle)
            header_layout.addLayout(title_col)

            # Center: search + filters
            center_widget = QtWidgets.QWidget()
            center_layout = QtWidgets.QHBoxLayout(center_widget)
            center_layout.setContentsMargins(0, 0, 0, 0)
            center_layout.setSpacing(8)
            # Location input (repurpose the large field)
            self.search_input = QtWidgets.QLineEdit()
            self.search_input.setPlaceholderText("Location (city or area)")
            self.search_input.setMinimumWidth(360)
            self.search_input.setStyleSheet("background:#23272e;color:#ffffff;border:1px solid #353b48;border-radius:10px;padding:6px 8px;")
            # Category filter (editable)
            self.filter_category = QtWidgets.QComboBox()
            self.filter_category.setEditable(True)
            self.filter_category.setPlaceholderText("Category (optional)")
            self.filter_category.setStyleSheet("background:#23272e;color:#ffffff;border:1px solid #353b48;border-radius:8px;padding:4px 6px;")
            # Remove the small location combo -- we will prefill the large input with default
            try:
                default_loc = get_saved_default_location() or AUTO_IMPORT_CITY
            except Exception:
                default_loc = AUTO_IMPORT_CITY
            self.search_input.setText(default_loc)
            # Rating filter
            self.filter_rating = QtWidgets.QComboBox()
            self.filter_rating.addItem("Any rating")
            for i in range(1, 6):
                self.filter_rating.addItem(str(i))
            self.filter_rating.setStyleSheet("background:#23272e;color:#ffffff;border:1px solid #353b48;border-radius:8px;padding:4px 6px;")
            # Search/Go button (runs combined import similar to Combined Search)
            self.go_btn = QtWidgets.QPushButton("Search")
            self.go_btn.setMinimumWidth(90)
            self.go_btn.setStyleSheet("background-color:#06b6d4;color:#081225;border-radius:10px;padding:8px 14px;font-weight:700;")

            # Add to center layout
            center_layout.addWidget(self.search_input)
            center_layout.addWidget(self.filter_category)
            center_layout.addWidget(self.filter_rating)
            center_layout.addWidget(self.go_btn)
            header_layout.addWidget(center_widget, 1)  # give center area stretch

            # Right: status pill + last-updated + sync button
            right_col = QtWidgets.QVBoxLayout()
            right_col.setSpacing(4)
            status_row = QtWidgets.QHBoxLayout()
            status_row.setSpacing(8)
            # little green dot
            dot = QtWidgets.QLabel()
            dot.setFixedSize(12, 12)
            dot.setStyleSheet("background-color: #10B981; border-radius: 6px;")
            # status label text
            self.status_label = QtWidgets.QLabel("Ready")
            self.status_label.setStyleSheet("color: #93C5FD; font-weight: 700;")
            status_row.addWidget(dot)
            status_row.addWidget(self.status_label)
            status_row.addStretch()
            right_col.addLayout(status_row)
            # last updated line
            try:
                if os.path.exists(DATA_FILE):
                    last = time.strftime('%I:%M %p', time.localtime(os.path.getmtime(DATA_FILE)))
                    last_txt = f"Last updated: {last.lstrip('0')}"
                else:
                    last_txt = "Last updated: N/A"
            except Exception:
                last_txt = "Last updated: N/A"
            last_label = QtWidgets.QLabel(last_txt)
            last_label.setStyleSheet("color: #94A3B8; font-size: 11px;")
            right_col.addWidget(last_label)

            # Help button on the right
            try:
                help_btn = QtWidgets.QPushButton("Help")
                help_btn.setMaximumWidth(90)
                help_btn.setStyleSheet("background-color:#0ea5a4;color:#081225;border-radius:8px;padding:6px 10px;font-weight:700;")
                try:
                    help_btn.clicked.connect(self.show_help)
                except Exception:
                    pass
                right_col.addWidget(help_btn, 0, QtCore.Qt.AlignRight)

                # Header save button placed under Help (same size/style)
                try:
                    self.header_save_btn = QtWidgets.QPushButton("Save")
                    self.header_save_btn.setMaximumWidth(90)
                    self.header_save_btn.setStyleSheet("background-color:#0ea5a4;color:#081225;border-radius:8px;padding:6px 10px;font-weight:700;")
                    try:
                        self.header_save_btn.clicked.connect(self.save_now_qt)
                    except Exception:
                        pass
                    right_col.addWidget(self.header_save_btn, 0, QtCore.Qt.AlignRight)
                except Exception:
                    pass
            except Exception:
                pass
            # small Sync/Import button
            # sync_btn = QtWidgets.QPushButton("Sync")
            # sync_btn.setMaximumWidth(90)
            # try:
            #     sync_btn.clicked.connect(self.auto_import_yelp_if_needed)
            # except Exception:
            #     pass
            # right_col.addWidget(sync_btn, 0, QtCore.Qt.AlignRight)

            header_layout.addLayout(right_col)

            root.addWidget(header_card)

            # Table card
            table_card = QtWidgets.QFrame()
            table_card.setObjectName("Card")
            table_layout = QtWidgets.QVBoxLayout(table_card)
            table_layout.setContentsMargins(16, 16, 16, 12)
            table_layout.setSpacing(12)
            self.table = QtWidgets.QTableView()
            self.table.setAlternatingRowColors(False)
            self.table.setShowGrid(False)
            self.table.verticalHeader().setVisible(False)
            self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            table_layout.addWidget(self.table, 1)

            # Toolbar (2 rows)
            toolbar = QtWidgets.QWidget()
            tool_layout = QtWidgets.QGridLayout(toolbar)
            tool_layout.setContentsMargins(0, 0, 0, 0)
            tool_layout.setHorizontalSpacing(10)
            tool_layout.setVerticalSpacing(10)

            def make_btn(text):
                b = QtWidgets.QPushButton(text)
                b.setMinimumHeight(40)
                b.setMinimumWidth(180)
                return b

            # removed 'List All' – it duplicated Refresh behavior
            self.btn_sort = make_btn("Sort by Rating")
            self.btn_review = make_btn("Add Review")
            self.btn_show_deals = make_btn("Show Deals")
            self.btn_show_reviews = make_btn("Show Reviews")
            self.btn_show_stats = make_btn("Report Summary")
            self.btn_smart_filter = make_btn("Smart Filter")
            # toolbar Save removed — header save used instead

            # Row 1 (reflowed after removing List All)
            tool_layout.addWidget(self.btn_sort, 0, 0)
            tool_layout.addWidget(self.btn_smart_filter, 0, 1)
            tool_layout.addWidget(self.btn_review, 0, 2)
            # Row 2
            tool_layout.addWidget(self.btn_show_deals, 1, 0)
            tool_layout.addWidget(self.btn_show_stats, 1, 1)
            # place Show Reviews under Add Review (column 2)
            tool_layout.addWidget(self.btn_show_reviews, 1, 2)
            # leave column 2 empty for spacing
            for col in range(5):
                tool_layout.setColumnStretch(col, 1)

            # Wrap toolbar in a horizontal container so it's centered
            wrapper = QtWidgets.QWidget()
            wrap_layout = QtWidgets.QHBoxLayout(wrapper)
            wrap_layout.setContentsMargins(0, 0, 0, 0)
            wrap_layout.addStretch()
            wrap_layout.addWidget(toolbar, 0, QtCore.Qt.AlignHCenter)
            wrap_layout.addStretch()

            table_layout.addWidget(wrapper)

            # Create a tab widget and add Search + Favorites tabs
            self.tab_widget = QtWidgets.QTabWidget()
            self.tab_widget.setObjectName("CardTabs")
            self.tab_widget.setStyleSheet("QTabBar::tab { background:#23272e; color:#f5f6fa; padding:8px 12px; border-radius:8px; } QTabBar::tab:selected { background:#2563eb; }")

            # Search tab (reuse the existing table_card)
            search_tab = QtWidgets.QWidget()
            search_layout = QtWidgets.QVBoxLayout(search_tab)
            search_layout.setContentsMargins(0, 0, 0, 0)
            search_layout.addWidget(table_card)

            # Favorites tab: separate card with its own table and same toolbar below
            fav_card = QtWidgets.QFrame()
            fav_card.setObjectName("Card")
            fav_layout = QtWidgets.QVBoxLayout(fav_card)
            fav_layout.setContentsMargins(16, 16, 16, 12)
            fav_layout.setSpacing(12)
            self.fav_table = QtWidgets.QTableView()
            self.fav_table.setAlternatingRowColors(False)
            self.fav_table.setShowGrid(False)
            self.fav_table.verticalHeader().setVisible(False)
            self.fav_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.fav_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            fav_layout.addWidget(self.fav_table, 1)
            # (toolbar kept on the Search tab only)

            self.tab_widget.addTab(search_tab, "Search")
            self.tab_widget.addTab(fav_card, "Favorites")

            root.addWidget(self.tab_widget, 1)

            # Model
            self.model = QtGui.QStandardItemModel()
            # add a narrow star column at index 0, then Business Name, Category, Address, Rating
            headers = ["", "Business Name", "Category", "Address", "Rating"]
            self.model.setHorizontalHeaderLabels(headers)
            self.table.setModel(self.model)

            # favorites model
            self.fav_model = QtGui.QStandardItemModel()
            self.fav_model.setHorizontalHeaderLabels(headers)
            self.fav_table.setModel(self.fav_model)

            # mapping for star buttons and row -> business id
            self._star_buttons = {}
            self._row_to_bid = {}
            # mapping for favorites table
            self._fav_star_buttons = {}
            self._fav_row_to_bid = {}

            try:
                self.table.selectionModel().selectionChanged.connect(lambda s,d,which='main': self._on_selection_changed(s,d,which))
            except Exception:
                pass
            try:
                self.table.clicked.connect(lambda idx, which='main': self._on_table_clicked(idx, which))
            except Exception:
                pass
            try:
                self.fav_table.selectionModel().selectionChanged.connect(lambda s,d,which='fav': self._on_selection_changed(s,d,which))
            except Exception:
                pass
            try:
                self.fav_table.clicked.connect(lambda idx, which='fav': self._on_table_clicked(idx, which))
            except Exception:
                pass

            self.table.horizontalHeader().setStretchLastSection(False)
            for i, header in enumerate(headers):
                if header == "":
                    # star column fixed small width
                    self.table.horizontalHeader().setSectionResizeMode(i, QtWidgets.QHeaderView.Fixed)
                    self.table.setColumnWidth(i, 36)
                elif header == "Rating":
                    self.table.horizontalHeader().setSectionResizeMode(i, QtWidgets.QHeaderView.ResizeToContents)
                    self.table.setColumnWidth(i, 100)
                    self.table.horizontalHeader().setMaximumSectionSize(120)
                else:
                    self.table.horizontalHeader().setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)
            self.table.verticalHeader().setDefaultSectionSize(38)

            # ensure favorites table uses similar column sizing
            for i, header in enumerate(headers):
                if header == "":
                    self.fav_table.horizontalHeader().setSectionResizeMode(i, QtWidgets.QHeaderView.Fixed)
                    self.fav_table.setColumnWidth(i, 36)
                elif header == "Rating":
                    self.fav_table.horizontalHeader().setSectionResizeMode(i, QtWidgets.QHeaderView.ResizeToContents)
                    self.fav_table.setColumnWidth(i, 100)
                    self.fav_table.horizontalHeader().setMaximumSectionSize(120)
                else:
                    self.fav_table.horizontalHeader().setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)
            self.fav_table.verticalHeader().setDefaultSectionSize(38)

            # Connects
            self.btn_sort.clicked.connect(self.sort_by_rating)
            self.btn_review.clicked.connect(self.add_review_qt)
            self.btn_show_deals.clicked.connect(self.show_deals)
            self.btn_show_reviews.clicked.connect(self.show_reviews)
            # Summary button now shows an exportable report dialog
            self.btn_show_stats.clicked.connect(self.export_report_dialog)
            self.btn_smart_filter.clicked.connect(self.smart_filter)

            # Load
            self.raw = load_data()
            self.businesses = build_businesses(self.raw)
            self.yelp_categories = extract_yelp_categories(YELP_BUSINESS_FILE)
            self.yelp_category_strings = extract_yelp_category_strings(YELP_BUSINESS_FILE)

            # populate category dropdown (non-destructive)
            try:
                if self.yelp_categories:
                    self.filter_category.blockSignals(True)
                    self.filter_category.clear()
                    self.filter_category.addItem("")
                    self.filter_category.addItems(sorted(self.yelp_categories))
                    self.filter_category.blockSignals(False)
            except Exception:
                pass

            # wire header controls: Enter or Go triggers combined import; category/rating still filter local list
            try:
                self.search_input.returnPressed.connect(self.header_combined_search)
                self.go_btn.clicked.connect(self.header_combined_search)
                self.filter_category.currentTextChanged.connect(self.apply_header_filters)
                self.filter_rating.currentTextChanged.connect(self.apply_header_filters)
            except Exception:
                pass

            self.list_all()

        def clear_model(self):
            if self.model.rowCount() > 0:
                self.model.removeRows(0, self.model.rowCount())
            # clear widget mappings
            try:
                self._star_buttons = {}
                self._row_to_bid = {}
            except Exception:
                pass

        def _business_key(self, b: Business) -> str:
            """Return a stable key for a business based on normalized name and address."""
            try:
                name = getattr(b, 'name', '') or ''
                addr = getattr(b, 'address', '') or ''
            except Exception:
                name = ''
                addr = ''
            return normalize_name(name) + '|' + normalize_name(addr)

        def _get_fav_keys(self) -> set:
            """Return a set of favorite keys, converting legacy numeric ids if present.
            Also normalizes and persists converted favorites back to raw if conversion occurred.
            """
            raw_favs = self.raw.setdefault('favorites', [])
            fav_keys = set()
            converted = False
            for item in list(raw_favs):
                # legacy numeric id -> convert to stable key if possible
                try:
                    if isinstance(item, int) or (isinstance(item, str) and str(item).isdigit()):
                        bid = int(item)
                        b = find_business(self.businesses, bid)
                        if b:
                            fav_keys.add(self._business_key(b))
                            converted = True
                            continue
                except Exception:
                    pass
                # assume it's already a key string
                try:
                    fav_keys.add(str(item))
                except Exception:
                    continue
            if converted:
                try:
                    self.raw['favorites'] = list(fav_keys)
                    save_data(self.raw)
                except Exception:
                    pass
            return fav_keys

        def _toggle_fav(self, bid: int, btn: QtWidgets.QPushButton):
            """Toggle favorite state for business id and update button appearance.
            Use stable name|address keys and refresh the Favorites tab."""
            b = find_business(self.businesses, bid)
            if not b:
                return
            key = self._business_key(b)
            fav_keys = set(self._get_fav_keys())
            if key in fav_keys:
                try:
                    fav_keys.remove(key)
                except Exception:
                    pass
                try:
                    btn.setText("☆")
                    btn.setStyleSheet("color: #ffffff; font-size: 18px; border: none; background: transparent;")
                except Exception:
                    pass
            else:
                fav_keys.add(key)
                try:
                    btn.setText("★")
                    btn.setStyleSheet("color: #ffd700; font-size: 18px; border: none; background: transparent;")
                except Exception:
                    pass
            # persist normalized favorite keys
            try:
                self.raw['favorites'] = list(fav_keys)
                persist_businesses(self.raw, self.businesses)
                save_data(self.raw)
            except Exception:
                pass
            try:
                self._star_buttons[bid] = btn
            except Exception:
                pass
            # refresh favorites view
            try:
                self.list_favorites()
            except Exception:
                pass

        def toggle_favorite(self):
            """Toggle favorite for selected business (toolbar button) using stable keys."""
            b = self.selected_business()
            if b is None:
                QtWidgets.QMessageBox.warning(self, "Error", "Select a business first.")
                return
            key = self._business_key(b)
            fav_keys = set(self._get_fav_keys())
            if key in fav_keys:
                try:
                    fav_keys.remove(key)
                except Exception:
                    pass
            else:
                fav_keys.add(key)
            try:
                self.raw['favorites'] = list(fav_keys)
                persist_businesses(self.raw, self.businesses)
                save_data(self.raw)
            except Exception:
                pass
            # refresh views
            self.businesses = build_businesses(self.raw)
            self.list_all()
            try:
                self.list_favorites()
            except Exception:
                pass

        def _make_star_button(self, b: Business) -> QtWidgets.QPushButton:
            """Create and return a star QPushButton for the given business."""
            fav_keys = self._get_fav_keys()
            star_btn = QtWidgets.QPushButton("★" if self._business_key(b) in fav_keys else "☆")
            star_btn.setFlat(True)
            star_btn.setCursor(QtCore.Qt.PointingHandCursor)
            star_btn.setFixedSize(28, 28)
            star_btn.setFocusPolicy(QtCore.Qt.NoFocus)
            try:
                if self._business_key(b) in fav_keys:
                    star_btn.setStyleSheet("color: #ffd700; font-size: 18px; border: none; background: transparent;")
                else:
                    star_btn.setStyleSheet("color: #ffffff; font-size: 18px; border: none; background: transparent;")
            except Exception:
                pass
            try:
                star_btn.clicked.connect(lambda _, bid=b.id, btn=star_btn: self._toggle_fav(bid, btn))
            except Exception:
                pass
            return star_btn

        def list_all(self):
            self.clear_model()
            fav_keys = self._get_fav_keys()
            for idx, b in enumerate(self.businesses):
                avg = round(b.avg_rating(), 1)
                rating_text = f"{avg} ({b.review_count()} reviews)"
                # create items for columns: star col, name, category, address, rating
                star_item = QtGui.QStandardItem("★" if self._business_key(b) in fav_keys else "☆")
                star_item.setEditable(False)
                try:
                    color = "#ffd700" if self._business_key(b) in fav_keys else "#ffffff"
                    star_item.setForeground(QtGui.QBrush(QtGui.QColor(color)))
                except Exception:
                    pass
                name_item = QtGui.QStandardItem(b.name)
                cat_item = QtGui.QStandardItem(b.category)
                addr_item = QtGui.QStandardItem(b.address)
                rating_item = QtGui.QStandardItem(rating_text)
                # style name/category/address/rating
                for it in (name_item, cat_item, addr_item, rating_item):
                    try:
                        it.setEditable(False)
                        it.setBackground(QtGui.QColor("#23272e"))
                        it.setForeground(QtGui.QBrush(QtGui.QColor("#f5f6fa")))
                    except Exception:
                        pass
                row = [star_item, name_item, cat_item, addr_item, rating_item]
                self.model.appendRow(row)
                try:
                    r = self.model.rowCount() - 1
                    try:
                        self._row_to_bid[r] = b.id
                    except Exception:
                        pass
                except Exception:
                    pass

        def list_favorites(self):
            """List businesses in the favorites table."""
            # clear the favorites model and mappings
            try:
                if self.fav_model.rowCount() > 0:
                    self.fav_model.removeRows(0, self.fav_model.rowCount())
            except Exception:
                pass
            try:
                self._fav_star_buttons = {}
                self._fav_row_to_bid = {}
            except Exception:
                pass

            fav_keys = self._get_fav_keys()
            # populate favorites model with businesses that are favorited
            for b in self.businesses:
                try:
                    if self._business_key(b) not in fav_keys:
                        continue
                    avg = round(b.avg_rating(), 1)
                    rating_text = f"{avg} ({b.review_count()} reviews)"
                    # create items for columns: star col, name, category, address, rating
                    star_item = QtGui.QStandardItem("★" if self._business_key(b) in fav_keys else "☆")
                    star_item.setEditable(False)
                    try:
                        color = "#ffd700" if self._business_key(b) in fav_keys else "#ffffff"
                        star_item.setForeground(QtGui.QBrush(QtGui.QColor(color)))
                    except Exception:
                        pass
                    name_item = QtGui.QStandardItem(b.name)
                    cat_item = QtGui.QStandardItem(b.category)
                    addr_item = QtGui.QStandardItem(b.address)
                    rating_item = QtGui.QStandardItem(rating_text)
                    # style name/category/address/rating
                    for it in (name_item, cat_item, addr_item, rating_item):
                        try:
                            it.setEditable(False)
                            it.setBackground(QtGui.QColor("#23272e"))
                            it.setForeground(QtGui.QBrush(QtGui.QColor("#f5f6fa")))
                        except Exception:
                            pass
                    row = [star_item, name_item, cat_item, addr_item, rating_item]
                    self.fav_model.appendRow(row)
                    # record mapping for click handling
                    try:
                        r = self.fav_model.rowCount() - 1
                        self._fav_row_to_bid[r] = b.id
                    except Exception:
                        pass
                except Exception:
                    continue

        def apply_header_filters(self):
            cat_q = self.filter_category.currentText().strip().lower() if self.filter_category.currentText() else ""
            rating_q = self.filter_rating.currentText().strip()

            try:
                min_rating = int(rating_q) if rating_q and rating_q.isdigit() else None
            except Exception:
                min_rating = None

            cat_variants = set()
            if cat_q:
                cat_variants.add(cat_q)
            if cat_q.endswith("s"):
                cat_variants.add(cat_q[:-1])
            else:
                cat_variants.add(cat_q + "s")

            filtered = []
            for b in self.businesses:
                if cat_q and not any(v in b.category.lower() for v in cat_variants):
                    continue
                if min_rating is not None and round(b.avg_rating()) < min_rating:
                    continue
                filtered.append(b)

            self.clear_model()
            fav_keys = self._get_fav_keys()
            for b in filtered:
                avg = round(b.avg_rating(), 1)
                rating_text = f"{avg} ({b.review_count()} reviews)"
                star_item = QtGui.QStandardItem("★" if self._business_key(b) in fav_keys else "☆")
                star_item.setEditable(False)
                try:
                    color = "#ffd700" if self._business_key(b) in fav_keys else "#ffffff"
                    star_item.setForeground(QtGui.QBrush(QtGui.QColor(color)))
                except Exception:
                    pass
                name_item = QtGui.QStandardItem(b.name)
                cat_item = QtGui.QStandardItem(b.category)
                addr_item = QtGui.QStandardItem(b.address)
                rating_item = QtGui.QStandardItem(rating_text)

                for it in (name_item, cat_item, addr_item, rating_item):
                    try:
                        it.setEditable(False)
                        it.setBackground(QtGui.QColor("#23272e"))
                        it.setForeground(QtGui.QBrush(QtGui.QColor("#f5f6fa")))
                    except Exception:
                        pass

                row = [star_item, name_item, cat_item, addr_item, rating_item]
                self.model.appendRow(row)
                try:
                    r = self.model.rowCount() - 1
                    self._row_to_bid[r] = b.id
                except Exception:
                    pass

        def header_combined_search(self):
            """Run combined search/import using the top Location and Category inputs (like Combined Search button).
            This will fetch from Yelp and OSM, merge, filter big chains, and overwrite current data file with results.
            """
            location = self.search_input.text().strip()
            category = self.filter_category.currentText().strip()
            if not location:
                QtWidgets.QMessageBox.warning(self, "Input Needed", "Please enter a location (city or area) in the top field.")
                return
            limit = 50
            broad_osm_tags = "restaurant|cafe|bar|fast_food|pub|coffee|food|bakery|ice_cream|deli|restaurant;food"
            tags_for_osm = normalize_osm_tags(category) if category else broad_osm_tags
            # Yelp search: pass category filter for partial match
            yelp_items = import_yelp_academic_businesses(YELP_BUSINESS_FILE, location, limit, category_filter=category if category else None)
            # OSM search
            osm_items = []
            try:
                osm_items = fetch_from_overpass(location, tags_for_osm, limit)
            except Exception as e:
                log(f"header_combined_search OSM failure: {e}")
                QtWidgets.QMessageBox.warning(self, "OSM Error", str(e))
            # Merge results, avoiding duplicates
            seen = set()
            combined = []
            for item in yelp_items + osm_items:
                key = (item.get("name", "").strip().lower(), item.get("address", "").strip().lower())
                if key in seen:
                    continue
                seen.add(key)
                combined.append(item)
            # filter out big chains
            combined = [item for item in combined if not is_big_chain(item.get("name", ""))]
            if not combined:
                QtWidgets.QMessageBox.information(
                    self,
                    "No Results",
                    "No businesses found from Yelp or OSM for your search. Try removing the category filter or using a broader category (e.g. 'restaurant')."
                )
                return
            # Overwrite with only the combined results
            # Preserve existing favorites (normalized keys) when saving combined results
            try:
                prev_fav_keys = self._get_fav_keys()
            except Exception:
                prev_fav_keys = set()
            raw = {"businesses": combined, "favorites": list(prev_fav_keys)}
            ensure_numeric_ids_for_raw(raw)
            save_data(raw)
            self.raw = raw
            self.businesses = build_businesses(self.raw)
            self.list_all()
            try:
                self.list_favorites()
            except Exception:
                pass
            QtWidgets.QMessageBox.information(self, "Search Complete", f"Imported {len(combined)} businesses from Yelp and OSM.")

        def selected_business(self) -> Optional[Business]:
            """Return the currently selected Business from the main table or None."""
            try:
                sel = self.table.selectionModel().selectedRows()
            except Exception:
                return None
            if not sel:
                return None
            row = sel[0].row()
            if 0 <= row < len(self.businesses):
                return self.businesses[row]
            return None

        def auto_import_yelp_if_needed(self):
            # only import once: if your app already has more than the 3 default businesses, skip
            if len(self.raw.get("businesses", [])) > 3:
                return

            if not os.path.exists(YELP_BUSINESS_FILE):
                return

            items = import_yelp_academic_businesses(YELP_BUSINESS_FILE, AUTO_IMPORT_CITY, AUTO_IMPORT_LIMIT)

            if not items:
                return

            added = integrate_yelp_results(self.raw, items)
            save_data(self.raw)

            self.businesses = build_businesses(self.raw)
            self.list_all()

        def sort_by_rating(self):
            self.businesses.sort(key=lambda b: b.avg_rating(), reverse=True)  # sort businesses by desc average rating
            self.list_all()  # refresh table

        def show_deals(self):
            b = self.selected_business()
            if b is None:
                QtWidgets.QMessageBox.warning(self, "Error", "Select a business first.")
                return
            if not b.deal.strip():
                QtWidgets.QMessageBox.information(self, "No Deal", f"No deal available for '{b.name}'.")
                return
            QtWidgets.QMessageBox.information(self, "Deal", f"Deal for '{b.name}':\n\n{b.deal}")
        def toggle_favorite(self):
            b = self.selected_business()
            if b is None:
                QtWidgets.QMessageBox.warning(self, "Error", "Select a business first.")  # show warning when no selection
                return
            favs = self.raw.setdefault("favorites", [])  # get or create favorites list
            if b.id in favs:
                favs.remove(b.id)  # remove id if already a favorite
            else:
                favs.append(b.id)  # add id to favorites
            try:
                self.raw['favorites'] = favs
                persist_businesses(self.raw, self.businesses)
                save_data(self.raw)
            except Exception:
                pass
            # refresh views
            self.businesses = build_businesses(self.raw)
            self.list_all()
            try:
                self.list_favorites()
            except Exception:
                pass

        def add_review_qt(self):
            b = self.selected_business()
            if b is None:
                QtWidgets.QMessageBox.warning(self, "Error", "Select a business first.")  # require selection
                return

            # Stronger anti-bot: present a short CAPTCHA-style challenge (6 chars), 3 attempts
            chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
            attempts = 0
            challenge = None
            start_time = time.time()
            while attempts < 3:
                attempts += 1
                challenge = ''.join(random.choice(chars) for _ in range(6))
                dlg = QtWidgets.QDialog(self)
                dlg.setWindowTitle("Human Verification")
                vlayout = QtWidgets.QVBoxLayout(dlg)
                prompt = QtWidgets.QLabel("Type the characters shown below to verify you are human:")
                prompt.setWordWrap(True)
                prompt.setAlignment(QtCore.Qt.AlignCenter)
                vlayout.addWidget(prompt)
                cap_label = QtWidgets.QLabel(challenge)
                cap_font = QtGui.QFont("Monospace")
                cap_font.setStyleHint(QtGui.QFont.TypeWriter)
                cap_font.setPointSize(20)
                cap_label.setFont(cap_font)
                cap_label.setAlignment(QtCore.Qt.AlignCenter)
                cap_label.setContentsMargins(6, 6, 6, 6)
                vlayout.addWidget(cap_label)
                inp = QtWidgets.QLineEdit()
                inp.setPlaceholderText("Enter characters shown above")
                inp.setMaxLength(10)
                inp.setAlignment(QtCore.Qt.AlignCenter)
                # ensure input text is visible on dark background
                inp.setStyleSheet("background:#23272e;color:#ffffff;border:1px solid #353b48;border-radius:6px;padding:6px 8px;")
                vlayout.addWidget(inp)
                btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
                vlayout.addWidget(btn_box)
                btn_box.accepted.connect(dlg.accept)
                btn_box.rejected.connect(dlg.reject)

                # bring to front to improve focus on macOS
                try:
                    self.raise_(); self.activateWindow(); QtWidgets.QApplication.processEvents()
                except Exception:
                    pass

                if dlg.exec() != QtWidgets.QDialog.Accepted:
                    return
                entered = (inp.text() or "").strip().upper()
                if entered == challenge:
                    break
                else:
                    QtWidgets.QMessageBox.warning(self, "Verification", f"Incorrect characters (attempt {attempts}/3).")
                    # small delay to slow automated retries
                    try:
                        time.sleep(0.35)
                    except Exception:
                        pass
            else:
                QtWidgets.QMessageBox.critical(self, "Verification Failed", "Too many incorrect attempts. Review not added.")
                return

            # Optional time-based check: require challenge completed within 2 minutes
            if time.time() - start_time > 120:
                QtWidgets.QMessageBox.critical(self, "Verification Failed", "Verification timed out. Try again.")
                return

            # Proceed to rating and review dialogs (same flow as before)
            rating, ok = QtWidgets.QInputDialog.getInt(self, "Rating", "Rating (1-5):", 1, 1, 5, 1)
            if not ok:
                return
            review_text, ok = QtWidgets.QInputDialog.getText(self, "Review", "Write a short review:")
            if not ok or not review_text.strip():
                return

            b.reviews.append(Review(rating=rating, text=review_text.strip()))
            persist_businesses(self.raw, self.businesses)
            self.list_all()

        def save_now_qt(self):
            persist_businesses(self.raw, self.businesses)
            save_data(self.raw)
            QtWidgets.QMessageBox.information(self, "Saved", "Saved to JSON!")

        def import_from_osm(self):
            """Prompt for a location and optional tags, then import from OpenStreetMap via Overpass."""
            if not REQUESTS_AVAILABLE:
                QtWidgets.QMessageBox.critical(self, "Missing Dependency", "The 'requests' library is required for OSM import. Run: pip install requests")
                return
            location, ok = QtWidgets.QInputDialog.getText(self, "Location", "Enter location (city or area name) for OSM import:")
            if not ok or not location.strip():
                return
            tags, ok = QtWidgets.QInputDialog.getText(self, "Tags", "Optional tag regex (e.g. 'restaurant|cafe|bar'):", text="restaurant|cafe|bar")
            if not ok:
                return
            limit, ok = QtWidgets.QInputDialog.getInt(self, "Limit", "Max number of POIs to import:", 25, 1, 500, 1)
            if not ok:
                return
            try:
                items = fetch_from_overpass(location.strip(), tags.strip() or "restaurant|cafe|bar", limit)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "OSM Error", f"Failed to fetch from Overpass: {e}")
                return
            if not items:
                QtWidgets.QMessageBox.information(self, "No Results", "No POIs returned from Overpass for that location/tags.")
                return
            # Overwrite with only OSM businesses, no favorites
            # Preserve existing favorites (normalized keys) when importing new data
            try:
                prev_fav_keys = self._get_fav_keys()
            except Exception:
                prev_fav_keys = set()
            raw = {"businesses": items, "favorites": list(prev_fav_keys)}
            ensure_numeric_ids_for_raw(raw)
            save_data(raw)
            self.raw = raw
            self.businesses = build_businesses(self.raw)
            self.list_all()
            try:
                self.list_favorites()
            except Exception:
                pass
            QtWidgets.QMessageBox.information(self, "Import Complete", f"Imported {len(items)} POIs from OpenStreetMap.")

        def combined_search(self):
            # Prompt for city/location
            location, ok = QtWidgets.QInputDialog.getText(self, "Combined Search", "Enter location (city or area name):")
            if not ok or not location.strip():
                return
            # Prompt for category (text input for Yelp)
            category, ok = QtWidgets.QInputDialog.getText(self, "Category", "Enter category (e.g. 'drive-in theater', 'restaurant', etc.):")
            if not ok or not category.strip():
                return
            # Prompt for tags (text input for OSM, default to category)
            tags, ok = QtWidgets.QInputDialog.getText(self, "Tags", "Optional tag regex for OSM (e.g. 'restaurant|cafe|bar'):", text=category)
            if not ok:
                return
            limit, ok = QtWidgets.QInputDialog.getInt(self, "Limit", "Max number of businesses to import:", 50, 1, 500, 1)
            if not ok:
                return
            broad_osm_tags = "restaurant|cafe|bar|fast_food|pub|coffee|food|bakery|ice_cream|deli|restaurant;food"
            tags_for_osm = tags.strip()
            if tags_for_osm.lower() in ["restaurant|cafe|bar", "restaurant"]:
                tags_for_osm = broad_osm_tags
            # Yelp search: pass category filter for partial match
            yelp_items = import_yelp_academic_businesses(YELP_BUSINESS_FILE, location.strip(), limit, category_filter=category.strip())
            # OSM search
            osm_items = fetch_from_overpass(location.strip(), tags_for_osm, limit)
            # Show debug counts
            QtWidgets.QMessageBox.information(self, "Debug", f"Yelp: {len(yelp_items)} results\nOSM: {len(osm_items)} results")
            # Merge results, avoiding duplicates between Yelp and OSM (not with existing list)
            seen = set()
            combined = []
            for item in yelp_items + osm_items:
                key = (item.get("name", "").strip().lower(), item.get("address", "").strip().lower())
                if key in seen:
                    continue
                seen.add(key)
                combined.append(item)
            # filter out big chains from combined results
            combined = [item for item in combined if not is_big_chain(item.get("name", ""))]
            if not combined:
                QtWidgets.QMessageBox.information(
                    self,
                    "No Results",
                    "No businesses found from Yelp or OSM for your search. Try removing the category filter or using a broader category (e.g. 'restaurant')."
                )
                return
            # Overwrite with only the combined results
            # Preserve existing favorites (normalized keys) when saving combined results
            try:
                prev_fav_keys = self._get_fav_keys()
            except Exception:
                prev_fav_keys = set()
            raw = {"businesses": combined, "favorites": list(prev_fav_keys)}
            ensure_numeric_ids_for_raw(raw)
            save_data(raw)
            self.raw = raw
            self.businesses = build_businesses(self.raw)
            self.list_all()
            try:
                self.list_favorites()
            except Exception:
                pass
            QtWidgets.QMessageBox.information(self, "Combined Search Complete", f"Imported {len(combined)} businesses from Yelp and OSM.")

        def show_reviews(self):
            b = self.selected_business()
            if b is None:
                QtWidgets.QMessageBox.warning(self, "Error", "Select a business first.")
                return
            if not b.reviews:
                QtWidgets.QMessageBox.information(self, "No Reviews", f"No reviews for '{b.name}'.")
                return
            msg = f"Reviews for '{b.name}':\n\n"
            for r in b.reviews:
                msg += f"Rating: {r.rating}\n{r.text}\n---\n"
            QtWidgets.QMessageBox.information(self, "Reviews", msg)

        def show_stats(self):
            # Show summary statistics for the current business list
            total = len(self.businesses)
            if total == 0:
                QtWidgets.QMessageBox.information(self, "Stats", "No businesses loaded.")
                return
            avg_rating = round(sum(b.avg_rating() for b in self.businesses) / total, 2)
            # Top categories
            from collections import Counter
            cat_counter = Counter()
            for b in self.businesses:
                for cat in b.category.split(","):
                    cat_counter[cat.strip()] += 1
            top_cats = ", ".join([f"{cat} ({count})" for cat, count in cat_counter.most_common(3)])
            # Most reviewed business
            most_reviewed = max(self.businesses, key=lambda b: b.review_count(), default=None)
            most_reviewed_str = f"{most_reviewed.name} ({most_reviewed.review_count()} reviews)" if most_reviewed else "N/A"
            # Rating distribution
            rating_dist = Counter()
            for b in self.businesses:
                for r in b.reviews:
                    rating_dist[r.rating] += 1
            dist_str = ", ".join([f"{k}: {v}" for k, v in sorted(rating_dist.items())])
            msg = f"Total businesses: {total}\nAverage rating: {avg_rating}\nTop categories: {top_cats}\nMost reviewed: {most_reviewed_str}\nRating distribution: {dist_str}"
            QtWidgets.QMessageBox.information(self, "Stats", msg)

        def smart_filter(self):
            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle("Smart Filter")
            layout = QtWidgets.QFormLayout(dlg)

            min_rating = QtWidgets.QSpinBox()
            min_rating.setRange(0, 5)
            min_rating.setValue(0)
            min_rating.setSpecialValueText("Any")

            cat_input = QtWidgets.QLineEdit()
            cat_input.setPlaceholderText("Category contains (optional)")

            name_input = QtWidgets.QLineEdit()
            name_input.setPlaceholderText("Name contains (optional)")

            layout.addRow("Minimum Rating:", min_rating)
            layout.addRow("Category contains:", cat_input)
            layout.addRow("Name contains:", name_input)

            btn_box = QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
            )
            layout.addRow(btn_box)
            btn_box.accepted.connect(dlg.accept)
            btn_box.rejected.connect(dlg.reject)

            if dlg.exec() != QtWidgets.QDialog.Accepted:
                return

            min_rating_val = min_rating.value()
            category_val = cat_input.text().strip().lower()
            name_val = name_input.text().strip().lower()

            filtered = []

            for b in self.businesses:
                business_name = str(b.name).lower().strip()
                business_category = str(b.category).lower().strip()
                business_rating = b.avg_rating()

                if min_rating_val > 0 and business_rating < min_rating_val:
                    continue

                if category_val and category_val not in business_category:
                    continue

                if name_val and name_val not in business_name:
                    continue

                filtered.append(b)

            QtWidgets.QMessageBox.information(
                self,
                "Debug Filter",
                f"Found {len(filtered)} matching businesses."
            )

            if not filtered:
                QtWidgets.QMessageBox.information(self, "Smart Filter", "No businesses match your criteria.")
                return

            self.clear_model()
            fav_keys = self._get_fav_keys()

            for b in filtered:
                avg = round(b.avg_rating(), 1)
                rating_text = f"{avg} ({b.review_count()} reviews)"

                star_item = QtGui.QStandardItem("★" if self._business_key(b) in fav_keys else "☆")
                name_item = QtGui.QStandardItem(b.name)
                cat_item = QtGui.QStandardItem(b.category)
                addr_item = QtGui.QStandardItem(b.address)
                rating_item = QtGui.QStandardItem(rating_text)

                for it in (star_item, name_item, cat_item, addr_item, rating_item):
                    it.setEditable(False)
                    it.setBackground(QtGui.QColor("#23272e"))
                    it.setForeground(QtGui.QBrush(QtGui.QColor("#f5f6fa")))

                self.model.appendRow([star_item, name_item, cat_item, addr_item, rating_item])
            def _normalize(s: str) -> str:
                try:
                    return re.sub(r"\s+", " ", (s or "").strip().lower())
                except Exception:
                    return (s or "").strip().lower()

                    category_val = _normalize(category_val)
                    name_val = _normalize(name_val)

            def matches_category(b: Business, q: str) -> bool:
                if not q:
                    return True
                try:
                    cat_text = _normalize(getattr(b, 'category', '') or '')
                    # direct substring match
                    if q in cat_text:
                        return True
                    # split common separators and match tokens
                    for token in re.split(r"[,/|;]+", cat_text):
                        if q in token.strip():
                            return True
                except Exception:
                    pass
                return False

            def matches_name(b: Business, q: str) -> bool:
                if not q:
                    return True
                try:
                    name_text = _normalize(getattr(b, 'name', '') or '')
                    if q in name_text:
                        return True
                except Exception:
                    pass
                return False

            filtered = []
            for b in self.businesses:
                try:
                    if b.avg_rating() < min_rating_val:
                        continue
                    if not matches_category(b, category_val):
                        continue
                    if not matches_name(b, name_val):
                        continue
                    filtered.append(b)
                except Exception:
                    continue

            if not filtered:
                QtWidgets.QMessageBox.information(self, "Smart Filter", "No businesses match your criteria.")
                return

            self.clear_model()
            fav_keys = self._get_fav_keys()
            for b in filtered:
                avg = round(b.avg_rating(), 1)
                rating_text = f"{avg} ({b.review_count()} reviews)"
                # star, name, category, address, rating
                star_item = QtGui.QStandardItem("★" if self._business_key(b) in fav_keys else "☆")
                name_item = QtGui.QStandardItem(b.name)
                cat_item = QtGui.QStandardItem(b.category)
                addr_item = QtGui.QStandardItem(b.address)
                rating_item = QtGui.QStandardItem(rating_text)
                for it in (name_item, cat_item, addr_item, rating_item):
                    try:
                        it.setEditable(False)
                        it.setBackground(QtGui.QColor("#23272e"))
                        it.setForeground(QtGui.QBrush(QtGui.QColor("#f5f6fa")))
                    except Exception:
                        pass
                row = [star_item, name_item, cat_item, addr_item, rating_item]
                self.model.appendRow(row)
                try:
                    r = self.model.rowCount() - 1
                    try:
                        self._row_to_bid[r] = b.id
                    except Exception:
                        pass
                except Exception:
                    pass
        def _on_selection_changed(self, selected, deselected, which='main'):
            """Update star button colors for selected rows so they stay visible against selection highlight."""
            try:
                sels = set(idx.row() for idx in self.table.selectionModel().selectedRows())
            except Exception:
                sels = set()
            fav_keys = self._get_fav_keys()
            for r, bid in list(self._row_to_bid.items()):
                try:
                    btn = self._star_buttons.get(bid)
                    if not btn:
                        continue
                    # determine business for this bid
                    b = find_business(self.businesses, bid)
                    is_fav = False
                    if b:
                        is_fav = (self._business_key(b) in fav_keys)
                    if is_fav:
                        btn.setText("★")
                        btn.setStyleSheet("color: #ffd700; font-size: 18px; border: none; background: transparent;")
                    else:
                        if r in sels:
                            # when row selected use dark star for contrast
                            btn.setText("☆")
                            btn.setStyleSheet("color: #081225; font-size: 18px; border: none; background: transparent;")
                        else:
                            btn.setText("☆")
                            btn.setStyleSheet("color: #ffffff; font-size: 18px; border: none; background: transparent;")
                except Exception:
                    continue
            # Favorites table selection handling
            if which == 'fav':
                try:
                    sels = set(idx.row() for idx in self.fav_table.selectionModel().selectedRows())
                except Exception:
                    sels = set()
                for r, bid in list(self._fav_row_to_bid.items()):
                    try:
                        btn = self._fav_star_buttons.get(bid)
                        if not btn:
                            continue
                        # determine business for this bid
                        b = find_business(self.businesses, bid)
                        is_fav = False
                        if b:
                            is_fav = (self._business_key(b) in fav_keys)
                        if is_fav:
                            btn.setText("★")
                            btn.setStyleSheet("color: #ffd700; font-size: 18px; border: none; background: transparent;")
                        else:
                            if r in sels:
                                # when row selected use dark star for contrast
                                btn.setText("☆")
                                btn.setStyleSheet("color: #081225; font-size: 18px; border: none; background: transparent;")
                            else:
                                btn.setText("☆")
                                btn.setStyleSheet("color: #ffffff; font-size: 18px; border: none; background: transparent;")
                    except Exception:
                        continue

        def _on_table_clicked(self, index, which='main'):
            """Handle clicks in the table. Toggle favorite when left star column clicked."""
            try:
                # Only handle clicks on the star column (index 0)
                if index.column() != 0:
                    return
                row = index.row()
                # Derive business and its stable key from the currently displayed businesses list
                if row is None or not (0 <= row < len(self.businesses)):
                    return
                b = self.businesses[row]
                key = self._business_key(b)
                fav_keys = set(self._get_fav_keys())
                if key in fav_keys:
                    try:
                        fav_keys.remove(key)
                    except Exception:
                        pass
                else:
                    fav_keys.add(key)
                # write normalized back to raw
                self.raw["favorites"] = list(fav_keys)
                persist_businesses(self.raw, self.businesses)
                save_data(self.raw)
                # refresh view
                self.businesses = build_businesses(self.raw)
                self.list_all()
                try:
                    self.list_favorites()
                except Exception:
                    pass
            except Exception:
                pass

            # Favorites table click handling (when called with which='fav')

            if which == 'fav':
                try:
                    if index.column() != 0:
                        return
                    row = index.row()
                    if row is None or not (0 <= row < len(self.businesses)):
                        return
                    b = self.businesses[row]
                    key = self._business_key(b)
                    fav_keys = set(self._get_fav_keys())
                    if key in fav_keys:
                        try:
                            fav_keys.remove(key)
                        except Exception:
                            pass
                    else:
                        fav_keys.add(key)
                    # write normalized back to raw
                    self.raw["favorites"] = list(fav_keys)
                    persist_businesses(self.raw, self.businesses)
                    save_data(self.raw)
                    # refresh view
                    self.businesses = build_businesses(self.raw)
                    self.list_favorites()
                except Exception:
                    pass

        def show_help(self):
            """Show the help dialog with information about the app."""
            help_text = f"""
            {PROGRAM_NAME} - Help

            This app allows you to browse, favorite, and review local businesses.
            You can also import business data from Yelp and OpenStreetMap.

            Features:
            - Browse businesses by category, location, and rating.
            - View and add reviews for businesses.
            - Save your favorite businesses for quick access.
            - Import business data from Yelp and OpenStreetMap.

            Usage:
            1. Enter a location (city or area) in the search box.
            2. Optionally, select a category and minimum rating.
            3. Click "Search" to find businesses.

            4. View business details, reviews, and available deals.
            5. Add businesses to your favorites for easy access later.
            6. Use the "Import" feature to add businesses from Yelp or OpenStreetMap.

            Note: Some features may require an internet connection and API keys.

            For more information, visit the project repository:
            [Link to repository]

            Report issues or suggest features on the project page.
            """
            QtWidgets.QMessageBox.information(self, "Help", help_text.strip())

        def _export_report_txt(self, report_text: str) -> None:
            """Save report_text to a user-selected .txt file."""
            try:
                path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Report as .txt", "", "Text Files (*.txt);;All Files (*)")
                if not path:
                    return
                with open(path, "w", encoding="utf-8") as f:
                    f.write(report_text)
                QtWidgets.QMessageBox.information(self, "Exported", f"Report saved to:\n{path}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Export Failed", str(e))

        def _export_report_csv(self) -> None:
            """Export current businesses to CSV (name, category, address, avg_rating, review_count)."""
            try:
                path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Report as .csv", "", "CSV Files (*.csv);;All Files (*)")
                if not path:
                    return
                import csv
                with open(path, "w", encoding="utf-8", newline='') as csvf:
                    writer = csv.writer(csvf)
                    writer.writerow(["Business Name", "Category", "Address", "Average Rating", "Review Count"])
                    for b in self.businesses:
                        try:
                            writer.writerow([b.name, b.category, b.address, f"{b.avg_rating():.2f}", str(b.review_count())])
                        except Exception:
                            continue
                QtWidgets.QMessageBox.information(self, "Exported", f"CSV saved to:\n{path}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Export Failed", str(e))

        def export_report_dialog(self):
            """Show a summary report in a dialog with options to export as TXT or CSV."""
            from collections import Counter
            total = len(self.businesses)
            if total == 0:
                QtWidgets.QMessageBox.information(self, "Report", "No businesses loaded.")
                return
            avg_rating = round(sum(b.avg_rating() for b in self.businesses) / total, 2)
            cat_counter = Counter()
            for b in self.businesses:
                for cat in str(b.category).split(","):
                    cat_counter[cat.strip().lower()] += 1
            top_cats = ", ".join([f"{cat} ({count})" for cat, count in cat_counter.most_common(5)])
            most_reviewed = max(self.businesses, key=lambda b: b.review_count(), default=None)
            most_reviewed_str = f"{most_reviewed.name} ({most_reviewed.review_count()} reviews)" if most_reviewed else "N/A"
            rating_dist = Counter()
            for b in self.businesses:
                for r in b.reviews:
                    try:
                        rating_dist[int(r.rating)] += 1
                    except Exception:
                        pass
            dist_str = ", ".join([f"{k}: {v}" for k, v in sorted(rating_dist.items())])
            sorted_by_rating = sorted(self.businesses, key=lambda b: b.avg_rating(), reverse=True)[:10]

            lines = [
                f"{PROGRAM_NAME} - SUMMARY REPORT",
                f"Generated: {time.strftime('%Y-%m-%d %I:%M %p')}",
                "",
                f"Total businesses: {total}",
                f"Average rating: {avg_rating} / 5.0",
                f"Top categories: {top_cats}",
                f"Most reviewed: {most_reviewed_str}",
                f"Rating distribution: {dist_str}",
                "",
                "TOP BUSINESSES BY RATING:",
            ]
            for i, b in enumerate(sorted_by_rating, 1):
                lines.append(f"{i}. {b.name} | {b.category} | {b.address} | {b.avg_rating():.2f} | {b.review_count()} reviews")
            report_text = "\n".join(lines)

            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle("Summary Report")
            dlg.resize(700, 520)
            v = QtWidgets.QVBoxLayout(dlg)
            text = QtWidgets.QPlainTextEdit()
            text.setPlainText(report_text)
            text.setReadOnly(True)
            v.addWidget(text)
            h = QtWidgets.QHBoxLayout()
            h.addStretch()
            btn_txt = QtWidgets.QPushButton("Export as .txt")
            btn_txt.clicked.connect(lambda: self._export_report_txt(report_text))
            h.addWidget(btn_txt)
            btn_csv = QtWidgets.QPushButton("Export as .csv")
            btn_csv.clicked.connect(self._export_report_csv)
            h.addWidget(btn_csv)
            close_btn = QtWidgets.QPushButton("Close")
            close_btn.clicked.connect(dlg.accept)
            h.addWidget(close_btn)
            v.addLayout(h)
            dlg.exec()
# When available, prefer implementations from the new business_boost package.
# This preserves original DATA_FILE path while letting you refactor implementations
# into business_boost modules without changing runtime behavior.
try:
    import business_boost.storage as _storage_mod
    from business_boost.models import Business, Review, default_data, build_businesses
    from business_boost.utils import normalize_name, is_big_chain
    from business_boost.sources import import_yelp_academic_businesses
       # ensure storage uses the monolith DATA_FILE path
    try:
        _storage_mod.DATA_FILE = DATA_FILE
    except Exception:
        pass
    # rebind names to module implementations
    try:
        load_data = _storage_mod.load_data
        save_data = _storage_mod.save_data
        persist_businesses = _storage_mod.persist_businesses
        ensure_numeric_ids_for_raw = _storage_mod.ensure_numeric_ids_for_raw
    except Exception:
        pass
except Exception:
    # fall back to local definitions if import fails
    pass

def find_business(businesses: List[Business], bid: int) -> Optional[Business]:
    """Return the Business with matching id or None if not found."""
    for b in businesses:
        try:
            if b.id == bid:
                return b
        except Exception:
                       continue
    return None

def integrate_osm_results(raw: Dict, osm_items: List[Dict]) -> int:
    """Append OSM/Overpass-derived items into raw['businesses'].
    Each item is expected to be a dict with keys: external_id, name, category, address, deal, reviews.
    Returns number of items added.
    """
    raw.setdefault("businesses", [])
    # collect existing external ids to avoid duplicates
    existing_ext = {b.get("external_id") for b in raw.get("businesses", []) if isinstance(b, dict) and b.get("external_id")}

    # determine next numeric id
    existing_ids = {b.get("id") for b in raw.get("businesses", []) if isinstance(b, dict)}
    max_id = 0
    for eid in existing_ids:
        try:
            if isinstance(eid, int):
                max_id = max(max_id, eid)
            else:
                max_id = max(max_id, int(eid))
        except Exception:
            continue
    next_id = max_id + 1

    added = 0
    for item in osm_items:
        # skip big chains coming from OSM
        if is_big_chain(item.get("name", "")):
            continue
        ext = item.get("external_id")
        if ext and ext in existing_ext:
            continue
        entry = {
            "id": next_id,
            "name": item.get("name", ""),
            "category": item.get("category", ""),
            "address": item.get("address", ""),
            "deal": item.get("deal", ""),
            "reviews": item.get("reviews", []) or [],
        }
        if ext:
            entry["external_id"] = ext
        raw["businesses"].append(entry)
        next_id += 1
        added += 1
    return added

# Ensure unique numeric ids when overwriting/creating raw business lists
def ensure_numeric_ids_for_raw(raw: Dict) -> None:
    """Ensure every business dict in raw['businesses'] has a unique integer 'id'.
    This is used when imported/combined lists are saved without ids so that
    favorites and other id-based operations don't treat them all as the same id (e.g. 0).
    The function mutates the provided raw dict in place.
    """
    raw.setdefault("businesses", [])
    next_id = 1
    for b in raw["businesses"]:
        try:
            # Always assign a fresh sequential integer id to guarantee uniqueness
            b["id"] = next_id
        except Exception:
            # if something odd happens, still ensure an int id
            try:
                b["id"] = int(next_id)
            except Exception:
                b["id"] = next_id
        next_id += 1

# bootstrap: require Qt
if __name__ == "__main__":
    if PYSIDE_AVAILABLE:  # if PySide6 import succeeded
        # Only import Yelp/default data if the data file is missing or empty
        if not os.path.exists(DATA_FILE):
            if os.path.exists(YELP_BUSINESS_FILE):
                items = import_yelp_academic_businesses(YELP_BUSINESS_FILE, AUTO_IMPORT_CITY, AUTO_IMPORT_LIMIT)
                if items:
                    raw = {"businesses": items, "favorites": []}
                    ensure_numeric_ids_for_raw(raw)
                    save_data(raw)
                else:
                    save_data(default_data())
            else:
                save_data(default_data())
        # Do NOT overwrite existing data file
        app = QtWidgets.QApplication(sys.argv)  # create Qt application instance
        app.setStyle("Fusion") 
        # Ensure dialog inputs and popups are readable on the dark theme
        app.setStyleSheet("""
QDialog, QInputDialog, QMessageBox { background: #181f2f; color: #ffffff; }
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox { background: #23272e; color: #ffffff; border: 1px solid #353b48; }
QInputDialog QLabel, QMessageBox QLabel, QDialog QLabel { color: #ffffff; }
QInputDialog QLineEdit, QMessageBox QLineEdit, QDialog QLineEdit { background: #23272e; color: #ffffff; }
QPushButton { color: #ffffff; }
""")
        win = QtMainWindow()  # create main Qt window
        win.show()  # show the Qt main window
        sys.exit(app.exec())  # start Qt event loop and exit with its return code
    else:
        print("PySide6 is not available. Install it with: pip install PySide6")  # instruct user to install PySide6
        sys.exit(1)