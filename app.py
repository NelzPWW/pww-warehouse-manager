# PWW_DB_V1_FAST_IMPORT_FIX

# PWW_WAREHOUSE_DB_V1
import os
import csv
import json
import re
import socket
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from flask import Flask, request, redirect, session, send_file, abort
from werkzeug.security import generate_password_hash, check_password_hash

try:
    import psycopg2
    import psycopg2.extras
except Exception:
    psycopg2 = None

APP_NAME = "PWW Warehouse Manager DB v1"
CREATED_BY = "Created by: Arnel Custodio"

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
QUOTE_DIR = BASE / "quotes"
QUOTE_HISTORY = QUOTE_DIR / "quote_history.csv"
USERS_FILE = BASE / "users.json"
SUPPLIER_CONFIG = BASE / "supplier_setup_config.json"
SERVICE_PRICING_FILE = BASE / "service_pricing.json"
LOGO_FILE = BASE / "pww_logo.png"

GST_RATE = 0.05
PST_RATE = 0.07
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "CHANGE-ME-PWW-WAREHOUSE")

PRODUCT_CACHE = []
PRODUCT_LOADED_AT = None

DEFAULT_SERVICE_PRICING = {
    "install_balance_each": 20.00,
    "tpms_each": 50.00,
    "lug_nut_kit_each": 50.00,
    "shop_labor_hour": 100.00,
    "tire_rotation": 50.00,
    "oil_change": 100.00,
    "flat_repair_each": 30.00,
}

DEFAULT_SUPPLIERS = {
    "FASTCO": {"protocol": "Downloader-managed CSV", "host": "", "dns_host": "", "port": "22", "username": "", "password": "", "remote_folder": "/", "local_folder": "vendor_files/fastco", "notes": "Downloader runs on the shop/approved workstation."},
    "AUTOCOUNTRY": {"protocol": "Downloader-managed CSV", "host": "", "dns_host": "", "port": "22", "username": "", "password": "", "remote_folder": "/", "local_folder": "vendor_files/autocountry", "notes": "Files expected: wheels.csv and tires.csv."},
    "WHEEL PROS": {"protocol": "SFTP", "host": "sftp.wheelpros.com", "dns_host": "sftp.wheelpros.com", "port": "22", "username": "", "password": "", "remote_folder": "/", "local_folder": "vendor_files/wheelpros", "notes": "Static IPs supplied by Wheel Pros: 44.234.227.42, 44.234.227.43, 44.234.227.45"},
}

CSS = """
<style>
:root{--red:#d71920;--dark:#111827;--green:#198754;--blue:#0d6efd;--light:#f5f6f8;--muted:#6b7280}
*{box-sizing:border-box}
body{font-family:Arial,Helvetica,sans-serif;margin:0;background:var(--light);color:#111}
.header{background:white;border-bottom:4px solid var(--red);padding:14px 18px;display:flex;gap:16px;align-items:center;position:sticky;top:0;z-index:5}
.logo{max-width:125px;max-height:62px}
.title{font-size:22px;font-weight:900}
.sub{font-size:13px;color:#555;font-style:italic}
.created{font-size:13px;font-weight:bold;margin-top:4px}
.footer{padding:18px;text-align:center;color:#555;font-size:13px}
.nav{display:flex;gap:8px;overflow-x:auto;background:#fff;padding:10px 14px;border-bottom:1px solid #ddd;position:sticky;top:106px;z-index:4}
.nav a{white-space:nowrap;padding:10px 14px;background:#eee;border-radius:999px;text-decoration:none;color:#111;font-weight:bold}
.nav a.active{background:var(--dark);color:white}
.wrap{padding:14px;max-width:1480px;margin:auto}
.card{background:#fff;border:1px solid #ddd;border-radius:12px;padding:14px;margin:10px 0;box-shadow:0 1px 3px #ddd}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.metric{background:white;border:1px solid #ddd;border-radius:12px;padding:16px}
.metric b{font-size:28px;display:block;margin-top:8px}
.row{display:grid;grid-template-columns:1fr;gap:10px}
.product{border-left:5px solid var(--dark)}
input,select,textarea{width:100%;padding:12px;border:1px solid #bbb;border-radius:8px;font-size:16px;margin:4px 0 10px;background:white}
button,.btn{display:inline-block;border:0;border-radius:8px;background:var(--dark);color:white;padding:12px 14px;font-weight:bold;text-decoration:none;margin:4px 4px 4px 0;font-size:15px;cursor:pointer}
.btn.green,button.green{background:var(--green)}
.btn.blue,button.blue{background:var(--blue)}
.btn.red,button.red{background:var(--red)}
.btn.gray,button.gray{background:#6b7280}
table{width:100%;border-collapse:collapse;background:white}
td,th{border-bottom:1px solid #eee;padding:10px;text-align:left;font-size:14px;vertical-align:top}
th{background:#f9fafb}
.pill{display:inline-block;padding:4px 8px;border-radius:999px;background:#eee;font-weight:bold;font-size:12px}
.pill.no{background:#ffe0e0}
.pill.yes{background:#dff3e3}
.right{text-align:right}
.small{font-size:13px;color:#555}
.desktop-only{display:none}
.mobile-only{display:block}
.two-col{display:grid;grid-template-columns:1fr;gap:12px}
.quote-summary{position:static}
.quote-side{position:static}
.profit-box{background:#ecfdf5;border-left:5px solid var(--green);margin-bottom:12px}
.mini-input{max-width:120px;padding:8px;font-size:14px}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:end}
.toolbar>div{min-width:150px;flex:1}
.warn{border-left:5px solid #d99000}
.success{border-left:5px solid var(--green)}
.danger{border-left:5px solid var(--red)}
.preview-box{display:grid;grid-template-columns:1fr;gap:12px}
.product-img{max-height:260px;object-fit:contain;width:100%;background:#f3f4f6;border-radius:10px}
.click-row:hover{background:#fff7e6}
.printbar{position:sticky;top:0;background:white;padding:10px;border-bottom:1px solid #ddd}
.muted{color:var(--muted)}
.service-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}
@media(min-width:760px){
.quote-side{position:sticky;top:150px;align-self:start}
.preview-box{grid-template-columns:320px 1fr}
.row{grid-template-columns:1fr 1fr}
.title{font-size:30px}
.logo{max-width:175px;max-height:88px}
.mobile-only{display:none}
.desktop-only{display:block}
.two-col{grid-template-columns:minmax(0,1.5fr) 420px}
.nav{top:124px}
.wrap{padding:18px}
.card{padding:18px}
}
@media print{.printbar,.nav,.header,.footer{display:none}body{background:white}.wrap{max-width:none}.card{box-shadow:none}}
</style>
"""

def money(v):
    try: return f"${float(v):,.2f}"
    except Exception: return "$0.00"

def num(v):
    try:
        if v is None or v == "": return 0.0
        return float(str(v).replace("$", "").replace(",", "").strip())
    except Exception: return 0.0

def clean(v):
    return "" if v is None else str(v).strip()

def esc(v):
    s = clean(v)
    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def norm_text(v):
    s = str(v or "").lower()
    for ch in [" ", "-", "_", "/", "\\", "+", ".", "x", "r"]:
        s = s.replace(ch, "")
    return s

def tire_parts(size):
    m = re.search(r"(\d{3})\D*(\d{2})\D*R?(\d{2})", str(size or "").upper().replace(" ", ""))
    return m.groups() if m else ("", "", "")

def wheel_parts(size):
    m = re.search(r"(\d{2})(?:\.0)?x([0-9]+(?:\.[0-9]+)?)", str(size or "").lower().replace(" ", ""))
    return m.groups() if m else ("", "")

def find_col(df, names):
    cols = {c.lower().strip().replace(" ", "_").replace("-", "_"): c for c in df.columns}
    for name in names:
        key = name.lower().strip().replace(" ", "_").replace("-", "_")
        if key in cols: return cols[key]
    for c in df.columns:
        cl = c.lower().strip()
        if any(n.lower() in cl for n in names): return c
    return None

def ensure_dirs():
    DATA_DIR.mkdir(exist_ok=True)
    QUOTE_DIR.mkdir(exist_ok=True)

def db_enabled():
    return bool(DATABASE_URL and psycopg2)

def db_conn():
    if not db_enabled():
        return None
    return psycopg2.connect(DATABASE_URL)

def init_db():
    if not db_enabled():
        return False
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                sku TEXT PRIMARY KEY,
                source TEXT,
                status TEXT,
                publish TEXT,
                type TEXT,
                vendor TEXT,
                brand TEXT,
                model TEXT,
                size TEXT,
                stock TEXT,
                cost NUMERIC DEFAULT 0,
                map NUMERIC DEFAULT 0,
                msrp NUMERIC DEFAULT 0,
                image TEXT,
                profit NUMERIC DEFAULT 0,
                title TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS import_runs (
                id SERIAL PRIMARY KEY,
                source TEXT,
                file_name TEXT,
                row_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
    return True

def db_product_count():
    if not db_enabled(): return 0
    init_db()
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM products")
            return cur.fetchone()[0]

def db_last_import():
    if not db_enabled(): return ""
    init_db()
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT source, file_name, row_count, created_at FROM import_runs ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if not row: return "No imports yet"
            return f"{row[0]} • {row[2]:,} rows • {row[3]}"

def file_existing_path(path):
    for p in [DATA_DIR / path, BASE / path]:
        if p.exists() and p.is_file():
            return p
    return None

def row_from_csv_row(r, cols, vendor, ptype, publish, source):
    sku = clean(r.get(cols["sku"], "")) if cols["sku"] else ""
    if not sku: return None
    size = clean(r.get(cols["size"], "")) if cols["size"] else ""
    if not size and ptype == "Wheel":
        dia = clean(r.get(cols["diameter"], "")) if cols["diameter"] else ""
        width = clean(r.get(cols["width"], "")) if cols["width"] else ""
        size = f"{dia}x{width}" if dia or width else ""
    cost = num(r.get(cols["cost"], 0)) if cols["cost"] else 0
    mp = num(r.get(cols["map"], 0)) if cols["map"] else 0
    msrp = num(r.get(cols["msrp"], 0)) if cols["msrp"] else 0
    return {
        "sku": sku, "source": source, "status": "Database Only" if publish == "Yes" else "Internal Only",
        "publish": publish, "type": ptype, "vendor": vendor,
        "brand": clean(r.get(cols["brand"], "")) if cols["brand"] else "",
        "model": clean(r.get(cols["model"], "")) if cols["model"] else "",
        "size": size,
        "stock": clean(r.get(cols["stock"], "")) if cols["stock"] else "",
        "cost": cost, "map": mp, "msrp": msrp,
        "image": clean(r.get(cols["image"], "")) if cols["image"] else "",
        "profit": (mp - cost) if mp and cost else 0,
        "title": clean(r.get(cols["title"], "")) if cols["title"] else "",
    }

def parse_csv_products(file_path, vendor, ptype, publish, source):
    df = pd.read_csv(file_path, dtype=str, low_memory=False).fillna("")
    cols = {
        "sku": find_col(df, ["sku", "part_number", "partnumber", "item", "item_number", "variant sku"]),
        "brand": find_col(df, ["brand", "manufacturer", "make", "vendor"]),
        "model": find_col(df, ["model", "style", "product_model", "pattern"]),
        "size": find_col(df, ["size", "wheel_size", "tire_size"]),
        "stock": find_col(df, ["stock", "qty", "quantity", "available", "inventory"]),
        "cost": find_col(df, ["cost", "dealer_cost", "wholesale", "cost per item"]),
        "map": find_col(df, ["map", "map_price", "price", "variant price"]),
        "msrp": find_col(df, ["msrp", "retail", "list_price", "compare at price"]),
        "image": find_col(df, ["image", "image_url", "image_src", "picture", "image src"]),
        "diameter": find_col(df, ["diameter", "wheel_diameter", "rim_diameter"]),
        "width": find_col(df, ["width", "wheel_width"]),
        "title": find_col(df, ["title", "name", "description"]),
    }
    rows = []
    for _, rr in df.iterrows():
        out = row_from_csv_row(rr, cols, vendor, ptype, publish, source)
        if out: rows.append(out)
    return rows

def import_products_to_db(file_path, source, vendor, ptype, publish):
    if not db_enabled():
        raise RuntimeError("DATABASE_URL/psycopg2 not available")
    init_db()
    rows = parse_csv_products(file_path, vendor, ptype, publish, source)

    if not rows:
        return 0

    cols = ["sku","source","status","publish","type","vendor","brand","model","size","stock","cost","map","msrp","image","profit","title"]
    values = [[r.get(c, "") for c in cols] for r in rows]

    sql = """
    INSERT INTO products (sku, source, status, publish, type, vendor, brand, model, size, stock, cost, map, msrp, image, profit, title, updated_at)
    VALUES %s
    ON CONFLICT (sku) DO UPDATE SET
        source=EXCLUDED.source,
        status=EXCLUDED.status,
        publish=EXCLUDED.publish,
        type=EXCLUDED.type,
        vendor=EXCLUDED.vendor,
        brand=EXCLUDED.brand,
        model=EXCLUDED.model,
        size=EXCLUDED.size,
        stock=EXCLUDED.stock,
        cost=EXCLUDED.cost,
        map=EXCLUDED.map,
        msrp=EXCLUDED.msrp,
        image=EXCLUDED.image,
        profit=EXCLUDED.profit,
        title=EXCLUDED.title,
        updated_at=CURRENT_TIMESTAMP
    """

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM products WHERE source=%s", (source,))
            psycopg2.extras.execute_values(
                cur,
                sql,
                values,
                template="(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)",
                page_size=1000
            )
            cur.execute(
                "INSERT INTO import_runs (source, file_name, row_count) VALUES (%s,%s,%s)",
                (source, Path(file_path).name, len(rows))
            )

    load_products(force=True)
    return len(rows)

def db_rows_to_products(rows):
    out = []
    for r in rows:
        d = dict(r) if not isinstance(r, dict) else r
        out.append({
            "status": clean(d.get("status")), "publish": clean(d.get("publish")), "type": clean(d.get("type")),
            "vendor": clean(d.get("vendor")), "sku": clean(d.get("sku")), "brand": clean(d.get("brand")),
            "model": clean(d.get("model")), "size": clean(d.get("size")), "stock": clean(d.get("stock")),
            "cost": num(d.get("cost")), "map": num(d.get("map")), "msrp": num(d.get("msrp")),
            "image": clean(d.get("image")), "profit": num(d.get("profit")), "title": clean(d.get("title")),
        })
    return out

def load_products(force=False):
    global PRODUCT_CACHE, PRODUCT_LOADED_AT
    if PRODUCT_CACHE and not force:
        return PRODUCT_CACHE
    rows = []
    if db_enabled():
        init_db()
        with db_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM products ORDER BY brand, model, sku")
                rows = db_rows_to_products(cur.fetchall())
    else:
        for rel, vendor, ptype, publish, source in [
            ("normalized_wheels.csv", "FASTCO", "Wheel", "Yes", "normalized_wheels"),
            ("vendor_files/autocountry/wheels.csv", "AUTOCOUNTRY", "Wheel", "Yes", "autocountry_wheels"),
            ("vendor_files/autocountry/tires.csv", "AUTOCOUNTRY", "Tire", "No", "autocountry_tires"),
            ("normalized_tires.csv", "MIXED", "Tire", "No", "normalized_tires"),
        ]:
            p = file_existing_path(rel)
            if p:
                try: rows += parse_csv_products(p, vendor, ptype, publish, source)
                except Exception: pass
    PRODUCT_CACHE = rows
    PRODUCT_LOADED_AT = datetime.now()
    return rows

def load_service_pricing():
    data = dict(DEFAULT_SERVICE_PRICING)
    if SERVICE_PRICING_FILE.exists():
        try: data.update({k: num(v) for k, v in json.loads(SERVICE_PRICING_FILE.read_text()).items()})
        except Exception: pass
    return data

def save_service_pricing(data):
    SERVICE_PRICING_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def load_quote_history():
    if not QUOTE_HISTORY.exists(): return []
    try:
        with open(QUOTE_HISTORY, "r", encoding="utf-8", newline="") as f: return list(csv.DictReader(f))
    except Exception:
        return []

def write_quote_history(rows):
    ensure_dirs()
    fields = ["quote_number","created","valid_until","customer","email","phone","vehicle","item_count","subtotal","gst","pst","grand_total","deposit","balance_due","invoice_file"]
    with open(QUOTE_HISTORY, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)

def load_suppliers():
    data = json.loads(json.dumps(DEFAULT_SUPPLIERS))
    if SUPPLIER_CONFIG.exists():
        try:
            saved = json.loads(SUPPLIER_CONFIG.read_text())
            for name, cfg in saved.items(): data.setdefault(name, {}).update(cfg)
        except Exception: pass
    return data

def save_suppliers(data):
    SUPPLIER_CONFIG.write_text(json.dumps(data, indent=2), encoding="utf-8")

def save_users(users): USERS_FILE.write_text(json.dumps(users, indent=2), encoding="utf-8")

def bootstrap_users():
    users = {}
    if USERS_FILE.exists():
        try: users = json.loads(USERS_FILE.read_text())
        except Exception: users = {}
    def ensure_user(name, password, role):
        if name not in users:
            users[name] = {"password_hash": generate_password_hash(password), "role": role, "active": True}
    ensure_user("Arnel", os.environ.get("PWW_ARNEL_PASS", "pww2026"), "Admin")
    ensure_user("Ryan", os.environ.get("PWW_RYAN_PASS", os.environ.get("PWW_ADMIN_PASS", "pww2026")), "Admin")
    ensure_user("Staff", os.environ.get("PWW_STAFF_PASS", "staff2026"), "Staff")
    save_users(users)

def load_users():
    bootstrap_users()
    try: return json.loads(USERS_FILE.read_text())
    except Exception: return {}

def current_user(): return session.get("user", "")
def current_role(): return session.get("role", "")
def is_admin(): return current_role() == "Admin"
def require_login(): return bool(session.get("logged_in"))

def nav(active=""):
    links = [("dashboard","/","Dashboard"),("products","/products","Products"),("quote","/quote","Quote"),("quotes","/quotes","Saved Quotes")]
    if is_admin():
        links += [("inventory","/inventory","Admin Tools"),("services","/admin/services","Service Pricing"),("suppliers","/suppliers","Suppliers"),("admin","/admin/users","Admin")]
    html = "".join(f"<a class='{'active' if active==k else ''}' href='{u}'>{t}</a>" for k,u,t in links)
    html += f"<a href='/logout'>Logout ({esc(current_user())})</a>"
    return html

def layout(title, body, active=""):
    logo = "<img class='logo' src='/logo'>" if LOGO_FILE.exists() else ""
    nav_html = "" if title == "Login" else f"<div class='nav'>{nav(active)}</div>"
    return f"""<!doctype html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'>{CSS}<title>{esc(APP_NAME)}</title></head>
<body><div class='header'>{logo}<div><div class='title'>{esc(APP_NAME)}</div><div class='sub'>Project Wheel Works cloud warehouse beta</div><div class='created'>{esc(CREATED_BY)}</div></div></div>{nav_html}<div class='wrap'>{body}</div><div class='footer'>Created by: Arnel Custodio • Internal use only</div></body></html>"""

@app.before_request
def gate():
    ensure_dirs()
    if request.path in ["/login", "/logo"] or request.path.startswith("/static"): return None
    if not require_login(): return redirect("/login")

@app.route("/logo")
def logo():
    if LOGO_FILE.exists(): return send_file(LOGO_FILE)
    abort(404)

@app.route("/login", methods=["GET","POST"])
def login():
    bootstrap_users()
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        users = load_users(); rec = users.get(username)
        if rec and rec.get("active", True) and check_password_hash(rec.get("password_hash",""), password):
            session.clear(); session["logged_in"] = True; session["user"] = username; session["role"] = rec.get("role","Staff"); session["cart"] = []; session["quote_info"] = {}; session["services"] = {}
            return redirect("/")
        return layout("Login", "<div class='card danger'><b>Login failed.</b><br><a class='btn' href='/login'>Try again</a></div>")
    return layout("Login", "<div class='card'><h2>Login</h2><form method='post'><label>Username</label><input name='username' value='Arnel'><label>Password</label><input type='password' name='password'><button class='green'>Login</button></form></div>")

@app.route("/logout")
def logout():
    session.clear(); return redirect("/login")

@app.route("/")
def dashboard():
    rows = load_products()
    wheels = sum(r["type"]=="Wheel" for r in rows); tires = sum(r["type"]=="Tire" for r in rows); internal = sum(r["publish"]=="No" for r in rows)
    value = sum(num(r["stock"])*num(r["cost"]) for r in rows)
    db_status = "Connected" if db_enabled() else "File mode"
    last_import = db_last_import() if db_enabled() else "N/A"
    body = f"""
    <div class='card success'><b>Database Status:</b> {esc(db_status)}<br><b>Last Import:</b> {esc(last_import)}</div>
    <div class='grid'>
      <div class='metric'>Products<b>{len(rows):,}</b></div><div class='metric'>Wheels<b>{wheels:,}</b></div><div class='metric'>Tires<b>{tires:,}</b></div>
      <div class='metric'>Internal Only<b>{internal:,}</b></div><div class='metric'>Saved Quotes<b>{len(load_quote_history()):,}</b></div><div class='metric'>Inventory Value<b>{money(value)}</b></div>
    </div>
    <div class='card'><h3>Working v1 Online Warehouse</h3><p>Product lookup, quoting, saved quotes, user management, service pricing, and supplier setup. Products are read from PostgreSQL when DATABASE_URL is configured.</p></div>"""
    return layout("Dashboard", body, "dashboard")

def option_list(values, selected, include_all=False, all_label="All"):
    vals=[]; seen=set()
    if include_all: vals.append(all_label); seen.add(all_label)
    for v in values:
        v=str(v or "").strip()
        if v and v not in seen: vals.append(v); seen.add(v)
    return "".join(f"<option value='{esc(v)}' {'selected' if str(selected)==str(v) else ''}>{esc(v)}</option>" for v in vals)

def contains_all_terms(row, query):
    query=(query or "").strip().lower()
    if not query: return True
    hay=" ".join(str(row.get(k,"")) for k in ["sku","brand","model","size","title","vendor","type","publish"]).lower()
    hn=norm_text(hay)
    return all(term in hay or norm_text(term) in hn for term in query.split())

@app.route("/products")
def products():
    params=request.args; rows=load_products(); all_rows=rows
    q=params.get("q","").strip(); ptype=params.get("type","All"); vendor=params.get("vendor","All"); brand=params.get("brand","All"); publish=params.get("publish","All"); min_stock=params.get("min_stock",""); sort=params.get("sort","relevance")
    rows=[r for r in rows if contains_all_terms(r,q)]
    if ptype!="All": rows=[r for r in rows if r["type"]==ptype]
    if vendor!="All": rows=[r for r in rows if r["vendor"]==vendor]
    if brand!="All": rows=[r for r in rows if r["brand"]==brand]
    if publish!="All": rows=[r for r in rows if r["publish"]==publish]
    if min_stock: rows=[r for r in rows if num(r.get("stock"))>=num(min_stock)]
    tw,ta,tr=params.get("tire_width",""),params.get("tire_aspect",""),params.get("tire_rim","")
    wd,ww,bolt=params.get("wheel_dia",""),params.get("wheel_width",""),params.get("bolt","")
    if tw or ta or tr:
        rows=[r for r in rows if r["type"]=="Tire"]
        if tw: rows=[r for r in rows if tire_parts(r["size"])[0]==tw]
        if ta: rows=[r for r in rows if tire_parts(r["size"])[1]==ta]
        if tr: rows=[r for r in rows if tire_parts(r["size"])[2]==tr]
    if wd or ww or bolt:
        rows=[r for r in rows if r["type"]=="Wheel"]
        if wd: rows=[r for r in rows if wheel_parts(r["size"])[0]==wd]
        if ww: rows=[r for r in rows if wheel_parts(r["size"])[1]==ww]
        if bolt: rows=[r for r in rows if norm_text(bolt) in norm_text(" ".join(str(r.get(k,"")) for k in ["sku","title","size","model"]))]
    if sort=="stock_desc": rows.sort(key=lambda r:num(r["stock"]), reverse=True)
    elif sort=="price_asc": rows.sort(key=lambda r:num(r["map"]))
    elif sort=="price_desc": rows.sort(key=lambda r:num(r["map"]), reverse=True)
    elif sort=="profit_desc": rows.sort(key=lambda r:num(r["profit"]), reverse=True)
    elif sort=="brand": rows.sort(key=lambda r:(r["brand"],r["model"],r["size"]))
    vendors=sorted({r["vendor"] for r in all_rows if r.get("vendor")}); brands=sorted({r["brand"] for r in all_rows if r.get("brand")})[:1000]
    tire_widths=sorted({tire_parts(r["size"])[0] for r in all_rows if r["type"]=="Tire" and tire_parts(r["size"])[0]}, key=lambda x:int(x))
    tire_aspects=sorted({tire_parts(r["size"])[1] for r in all_rows if r["type"]=="Tire" and tire_parts(r["size"])[1]}, key=lambda x:int(x))
    tire_rims=sorted({tire_parts(r["size"])[2] for r in all_rows if r["type"]=="Tire" and tire_parts(r["size"])[2]}, key=lambda x:int(x))
    wheel_dias=sorted({wheel_parts(r["size"])[0] for r in all_rows if r["type"]=="Wheel" and wheel_parts(r["size"])[0]}, key=lambda x:int(float(x)))
    wheel_widths=sorted({wheel_parts(r["size"])[1] for r in all_rows if r["type"]=="Wheel" and wheel_parts(r["size"])[1]}, key=lambda x:float(x))
    sort_opts="".join(f"<option value='{v}' {'selected' if sort==v else ''}>{label}</option>" for v,label in [("relevance","Best match"),("stock_desc","Stock high to low"),("price_asc","MAP low to high"),("price_desc","MAP high to low"),("profit_desc","Profit high to low"),("brand","Brand / model")])
    shown=rows[:500]; show_cost=is_admin(); cost_headers="<th>Cost</th><th>Profit</th>" if show_cost else ""
    table_rows=[]; cards=[]
    for r in shown:
        sku_q=urllib.parse.quote(r["sku"]); pill_cls="yes" if r["publish"]=="Yes" else "no"; cost_cells=f"<td>{money(r['cost'])}</td><td>{money(r['profit'])}</td>" if show_cost else ""
        table_rows.append(f"""<tr class='click-row' onclick="window.location='/product/{sku_q}'"><td><b>{esc(r['brand'])}</b><br><span class='small'>{esc(r['sku'])}</span></td><td>{esc(r['model'])}</td><td>{esc(r['size'])}</td><td>{esc(r['type'])}</td><td>{esc(r['vendor'])}</td><td>{esc(r['stock'])}</td>{cost_cells}<td>{money(r['map'])}</td><td><span class='pill {pill_cls}'>{esc(r['publish'])}</span></td><td onclick='event.stopPropagation()'><a class='btn blue' href='/product/{sku_q}'>Preview</a><form method='post' action='/add' style='display:inline'><input type='hidden' name='sku' value='{esc(r['sku'])}'><input type='hidden' name='qty' value='4'><button class='green'>Add 4</button></form></td></tr>""")
    body=f"""
    <div class='card'><h2>Product Search</h2><form class='toolbar'><div style='flex:2;min-width:260px'><label>Main Search</label><input name='q' value='{esc(q)}' placeholder='BR08, Braelin 19x8.5, 285 55 20'></div><div><label>Type</label><select name='type'>{option_list(['Wheel','Tire'],ptype,True)}</select></div><div><label>Vendor</label><select name='vendor'>{option_list(vendors,vendor,True)}</select></div><div><label>Brand</label><select name='brand'>{option_list(brands,brand,True)}</select></div><div><label>Publish</label><select name='publish'>{option_list(['Yes','No'],publish,True)}</select></div><div><label>Min Stock</label><input name='min_stock' value='{esc(min_stock)}' placeholder='4'></div><div><label>Sort</label><select name='sort'>{sort_opts}</select></div><div><button>Search / Filter</button><a class='btn gray' href='/products'>Reset</a></div></form></div>
    <div class='card'><h3>Guided Filters</h3><form class='toolbar'><input type='hidden' name='type' value='Tire'><div><label>Tire Width</label><select name='tire_width'>{option_list(tire_widths,tw,True,'')}</select></div><div><label>Aspect</label><select name='tire_aspect'>{option_list(tire_aspects,ta,True,'')}</select></div><div><label>Rim</label><select name='tire_rim'>{option_list(tire_rims,tr,True,'')}</select></div><div><button class='blue'>Find Tires</button></div></form><form class='toolbar'><input type='hidden' name='type' value='Wheel'><div><label>Wheel Diameter</label><select name='wheel_dia'>{option_list(wheel_dias,wd,True,'')}</select></div><div><label>Wheel Width</label><select name='wheel_width'>{option_list(wheel_widths,ww,True,'')}</select></div><div><label>Bolt / SKU Contains</label><input name='bolt' value='{esc(bolt)}'></div><div><button class='blue'>Find Wheels</button></div></form></div>
    <p class='small'>Showing {len(shown):,} of {len(rows):,} results.</p><div class='desktop-only card'><table><tr><th>Brand/SKU</th><th>Model</th><th>Size</th><th>Type</th><th>Vendor</th><th>Stock</th>{cost_headers}<th>MAP</th><th>Publish</th><th>Action</th></tr>{''.join(table_rows) or '<tr><td colspan=11>No products found.</td></tr>'}</table></div>"""
    return layout("Products", body, "products")

@app.route("/product/<path:sku>")
def product(sku):
    r=next((x for x in load_products() if x["sku"]==sku), None)
    if not r: return layout("Product", "<div class='card'>Product not found.</div>", "products")
    img=f"<img class='product-img' src='{esc(r['image'])}' onerror=\"this.outerHTML='<div class=card>No product image available.</div>'\">" if r.get("image") else "<div class='card muted'>No product image URL available.</div>"
    margin=(num(r["profit"])/num(r["map"])*100) if num(r["map"]) else 0
    admin_rows=f"<tr><th>Cost</th><td>{money(r['cost'])}</td></tr><tr><th>Profit</th><td>{money(r['profit'])}</td></tr><tr><th>Margin</th><td>{margin:.1f}%</td></tr>" if is_admin() else ""
    body=f"""<div class='card'><a class='btn gray' href='/products'>Back to Products</a></div><div class='card preview-box'><div>{img}</div><div><h2>{esc(r['brand'])} {esc(r['model'])}</h2><table><tr><th>SKU</th><td>{esc(r['sku'])}</td></tr><tr><th>Vendor</th><td>{esc(r['vendor'])}</td></tr><tr><th>Type</th><td>{esc(r['type'])}</td></tr><tr><th>Size</th><td>{esc(r['size'])}</td></tr><tr><th>Stock</th><td>{esc(r['stock'])}</td></tr>{admin_rows}<tr><th>MAP</th><td>{money(r['map'])}</td></tr><tr><th>MSRP</th><td>{money(r['msrp'])}</td></tr></table><form method='post' action='/add'><input type='hidden' name='sku' value='{esc(r['sku'])}'><label>Qty</label><input name='qty' value='4'><button class='green'>Add to Quote</button></form></div></div>"""
    return layout("Product", body, "products")

@app.post("/add")
def add_to_quote():
    cart=session.get("cart", []); cart.append({"sku":request.form.get("sku",""),"qty":int(num(request.form.get("qty",1)) or 1),"price":0}); session["cart"]=cart; session.modified=True; return redirect("/quote")

@app.post("/remove")
def remove_item():
    cart=session.get("cart", []); idx=int(num(request.form.get("idx",-1)))
    if 0<=idx<len(cart): cart.pop(idx)
    session["cart"]=cart; session.modified=True; return redirect("/quote")

@app.post("/clearquote")
def clear_quote():
    session["cart"]=[]; session["services"]={}; session.modified=True; return redirect("/quote")

@app.post("/addmanual")
def add_manual():
    desc=request.form.get("manual_desc","").strip(); price=num(request.form.get("manual_price",0)); qty=int(num(request.form.get("manual_qty",1)) or 1)
    if desc and price:
        cart=session.get("cart", []); cart.append({"manual":True,"desc":desc,"qty":qty,"price":price}); session["cart"]=cart; session.modified=True
    return redirect("/quote")

def default_quote_info(): return {"customer":"","email":"","phone":"","vehicle":"","notes":"","discount":0,"deposit":0}
def default_services(): return {"install_balance_qty":0,"tpms_qty":0,"lug_nut_kit_qty":0,"shop_labor_hours":0,"tire_rotation_qty":0,"oil_change_qty":0,"flat_repair_qty":0,"misc_label":"Miscellaneous","misc_amount":0}

def quote_totals():
    info=session.get("quote_info") or default_quote_info(); services=session.get("services") or default_services(); pricing=load_service_pricing(); products={r["sku"]:r for r in load_products()}
    items=[]; product_subtotal=0; product_cost_total=0
    for i,item in enumerate(session.get("cart", [])):
        qty=int(num(item.get("qty",1)) or 1)
        if item.get("manual"): r={"sku":"MANUAL","brand":item.get("desc","Manual Item"),"model":"","size":"","map":num(item.get("price",0)),"cost":0}; price=num(item.get("price",0)); cost=0
        else:
            r=products.get(item.get("sku",""))
            if not r: continue
            price=num(item.get("price")) or num(r["map"]) or num(r["msrp"]) or num(r["cost"]); cost=num(r.get("cost",0))
        line=qty*price; product_subtotal+=line; product_cost_total+=qty*cost; items.append((i,r,qty,price,line,qty*cost))
    service_lines=[]
    def add_service(k,label,price_key):
        qty=num(services.get(k,0)); rate=num(pricing.get(price_key,0))
        if qty>0 and rate>0: service_lines.append((label,qty,rate,qty*rate))
    add_service("install_balance_qty","Install & Balance","install_balance_each"); add_service("tpms_qty","TPMS Sensor","tpms_each"); add_service("lug_nut_kit_qty","Lug Nut Kit","lug_nut_kit_each"); add_service("shop_labor_hours","Shop Labour","shop_labor_hour"); add_service("tire_rotation_qty","Tire Rotation","tire_rotation"); add_service("oil_change_qty","Oil Change","oil_change"); add_service("flat_repair_qty","Flat Repair","flat_repair_each")
    misc_amount=num(services.get("misc_amount",0)); misc_label=services.get("misc_label","Miscellaneous") or "Miscellaneous"
    if misc_amount: service_lines.append((misc_label,1,misc_amount,misc_amount))
    service_subtotal=sum(line for _,_,_,line in service_lines); discount=num(info.get("discount",0)); deposit=num(info.get("deposit",0)); taxable=max(0,product_subtotal+service_subtotal-discount); pst=taxable*PST_RATE; gst=taxable*GST_RATE; total=taxable+pst+gst; balance=total-deposit
    product_profit=product_subtotal-product_cost_total; service_profit=service_subtotal; total_profit=product_profit+service_profit-discount; margin=(total_profit/taxable*100) if taxable else 0
    return {"info":info,"services":services,"pricing":pricing,"items":items,"service_lines":service_lines,"product_subtotal":product_subtotal,"product_cost_total":product_cost_total,"service_subtotal":service_subtotal,"discount":discount,"taxable":taxable,"pst":pst,"gst":gst,"total":total,"deposit":deposit,"balance":balance,"product_profit":product_profit,"service_profit":service_profit,"total_profit":total_profit,"margin":margin}

def qty_options(selected, max_n=8, allow_half=False):
    vals=[0,0.5,1,1.5,2,2.5,3,4,5,6,8] if allow_half else list(range(0,max_n+1))
    return "".join(f"<option value='{v}' {'selected' if str(selected)==str(v) else ''}>{v}</option>" for v in vals)

@app.route("/quote")
def quote():
    qd=quote_totals(); info=qd["info"]; services=qd["services"]; pricing=qd["pricing"]
    item_rows=[]
    for i,r,qty,price,line,_cost in qd["items"]:
        item_html=f"<input name='line_desc_{i}' value='{esc(r['brand'])}'><span class='small'>Manual Item</span>" if r.get("sku")=="MANUAL" else f"{esc(r['brand'])} {esc(r['model'])}<br><span class='small'>{esc(r['sku'])} • {esc(r['size'])}</span>"
        item_rows.append(f"<tr><td>{item_html}</td><td><input class='mini-input' name='line_qty_{i}' value='{qty}'></td><td><input class='mini-input' name='line_price_{i}' value='{price:.2f}'></td><td>{money(line)}</td><td><form method='post' action='/remove'><input type='hidden' name='idx' value='{i}'><button class='red'>X</button></form></td></tr>")
    admin_profit=""
    if is_admin():
        admin_profit=f"""<div class='card profit-box'><h2>Admin Profit View</h2><table><tr><td>Product Revenue</td><td class='right'>{money(qd['product_subtotal'])}</td></tr><tr><td>Product Cost</td><td class='right'>-{money(qd['product_cost_total'])}</td></tr><tr><td>Product Profit</td><td class='right'>{money(qd['product_profit'])}</td></tr><tr><td>Service/Add-on Profit</td><td class='right'>{money(qd['service_profit'])}</td></tr><tr><td>Discount Impact</td><td class='right'>-{money(qd['discount'])}</td></tr><tr><th>Total Estimated Profit</th><th class='right'>{money(qd['total_profit'])}</th></tr><tr><th>Estimated Margin</th><th class='right'>{qd['margin']:.1f}%</th></tr></table><p class='small'>Admin-only. Never appears on customer print/PDF.</p></div>"""
    body=f"""<div class='two-col'><div class='card'><h2>Quote Builder</h2><form method='post' action='/updatequote'><div class='row'><div><label>Customer</label><input name='customer' value='{esc(info.get('customer',''))}'></div><div><label>Email</label><input name='email' value='{esc(info.get('email',''))}'></div></div><div class='row'><div><label>Phone</label><input name='phone' value='{esc(info.get('phone',''))}'></div><div><label>Vehicle</label><input name='vehicle' value='{esc(info.get('vehicle',''))}'></div></div><label>Notes</label><textarea name='notes'>{esc(info.get('notes',''))}</textarea><table><tr><th>Item</th><th>Qty</th><th>Price</th><th>Total</th><th></th></tr>{''.join(item_rows) or '<tr><td colspan=5>No items yet.</td></tr>'}</table><h3>Service Presets</h3><div class='service-grid'><div><label>Install & Balance ({money(pricing['install_balance_each'])}/tire)</label><select name='install_balance_qty'>{qty_options(services.get('install_balance_qty',0),12)}</select></div><div><label>TPMS ({money(pricing['tpms_each'])}/each)</label><select name='tpms_qty'>{qty_options(services.get('tpms_qty',0),12)}</select></div><div><label>Lug Nut Kit ({money(pricing['lug_nut_kit_each'])}/kit)</label><select name='lug_nut_kit_qty'>{qty_options(services.get('lug_nut_kit_qty',0),8)}</select></div><div><label>Shop Labour ({money(pricing['shop_labor_hour'])}/hour)</label><select name='shop_labor_hours'>{qty_options(services.get('shop_labor_hours',0),8,True)}</select></div><div><label>Tire Rotation ({money(pricing['tire_rotation'])})</label><select name='tire_rotation_qty'>{qty_options(services.get('tire_rotation_qty',0),4)}</select></div><div><label>Oil Change ({money(pricing['oil_change'])})</label><select name='oil_change_qty'>{qty_options(services.get('oil_change_qty',0),4)}</select></div><div><label>Flat Repair ({money(pricing['flat_repair_each'])}/tire)</label><select name='flat_repair_qty'>{qty_options(services.get('flat_repair_qty',0),8)}</select></div></div><div class='row'><div><label>Misc Label</label><input name='misc_label' value='{esc(services.get('misc_label','Miscellaneous'))}'></div><div><label>Misc Amount</label><input name='misc_amount' value='{num(services.get('misc_amount',0)):.2f}'></div></div><div class='row'><div><label>Discount</label><input name='discount' value='{qd['discount']:.2f}'></div><div><label>Deposit</label><input name='deposit' value='{qd['deposit']:.2f}'></div></div><button class='blue'>Update</button><button class='blue' formaction='/previewquote'>Preview / Print</button><button class='green' formaction='/savequote'>Save Quote</button><a class='btn gray' href='/products'>Add Products</a></form><div class='card warn'><h3>Add Manual Item</h3><form method='post' action='/addmanual'><label>Description</label><input name='manual_desc'><label>Qty</label><input name='manual_qty' value='1'><label>Price</label><input name='manual_price'><button class='green'>Add Manual Item</button></form></div><form method='post' action='/clearquote'><button class='red'>Clear Quote</button></form></div><div class='quote-side'>{admin_profit}<div class='card quote-summary'><h2>Summary</h2><table><tr><td>Product Subtotal</td><td class='right'>{money(qd['product_subtotal'])}</td></tr><tr><td>Service/Add-ons</td><td class='right'>{money(qd['service_subtotal'])}</td></tr><tr><td>Discount</td><td class='right'>-{money(qd['discount'])}</td></tr><tr><td>Taxable Subtotal</td><td class='right'>{money(qd['taxable'])}</td></tr><tr><td>PST 7%</td><td class='right'>{money(qd['pst'])}</td></tr><tr><td>GST 5%</td><td class='right'>{money(qd['gst'])}</td></tr><tr><th>Grand Total</th><th class='right'>{money(qd['total'])}</th></tr><tr><td>Deposit</td><td class='right'>-{money(qd['deposit'])}</td></tr><tr><th>Balance Due</th><th class='right'>{money(qd['balance'])}</th></tr></table></div></div></div>"""
    return layout("Quote", body, "quote")

@app.post("/updatequote")
@app.post("/previewquote")
@app.post("/savequote")
def update_quote():
    cart=session.get("cart", [])
    for i,item in enumerate(cart):
        if f"line_qty_{i}" in request.form: item["qty"]=int(num(request.form.get(f"line_qty_{i}")) or 1)
        if f"line_price_{i}" in request.form: item["price"]=num(request.form.get(f"line_price_{i}"))
        if item.get("manual") and f"line_desc_{i}" in request.form: item["desc"]=request.form.get(f"line_desc_{i}","")
    session["cart"]=cart
    session["quote_info"]={k:request.form.get(k,"") for k in ["customer","email","phone","vehicle","notes"]}; session["quote_info"]["discount"]=num(request.form.get("discount",0)); session["quote_info"]["deposit"]=num(request.form.get("deposit",0))
    session["services"]={k:request.form.get(k,"0") for k in ["install_balance_qty","tpms_qty","lug_nut_kit_qty","shop_labor_hours","tire_rotation_qty","oil_change_qty","flat_repair_qty","misc_amount"]}; session["services"]["misc_label"]=request.form.get("misc_label","Miscellaneous")
    session.modified=True
    if request.path=="/updatequote": return redirect("/quote")
    fp=create_invoice(save_history=(request.path=="/savequote"), preview=(request.path=="/previewquote"))
    return redirect("/invoice?file="+urllib.parse.quote(str(fp.relative_to(BASE))))

def create_invoice(save_history=True, preview=False):
    qd=quote_totals(); info=qd["info"]; ensure_dirs()
    quote_num="PWW-M-"+datetime.now().strftime("%Y%m%d-%H%M%S"); created=datetime.now().strftime("%Y-%m-%d %I:%M %p"); valid=(datetime.now()+timedelta(days=7)).strftime("%Y-%m-%d")
    row_html=""; item_count=0
    for _,r,qty,price,line,_cost in qd["items"]:
        item_count+=qty; row_html+=f"<tr><td>{esc(r['brand'])} {esc(r.get('model',''))}<br><small>{esc(r['sku'])} • {esc(r.get('size',''))}</small></td><td>{qty}</td><td>{money(price)}</td><td>{money(line)}</td></tr>"
    for label,qty,rate,line in qd["service_lines"]: row_html+=f"<tr><td>{esc(label)}</td><td>{qty:g}</td><td>{money(rate)}</td><td>{money(line)}</td></tr>"
    if qd["discount"]: row_html+=f"<tr><td>Discount</td><td>1</td><td>-{money(qd['discount'])}</td><td>-{money(qd['discount'])}</td></tr>"
    logo_html="<img src='/logo' onerror=\"this.style.display='none'\">" if LOGO_FILE.exists() else ""
    html=f"""<!doctype html><html><head><meta charset='utf-8'>{CSS}<style>body{{background:white;margin:25px}}@media print{{.printbar{{display:none}}}}.top{{display:flex;justify-content:space-between;gap:20px;border-bottom:5px solid #d71920;padding-bottom:20px}}.top img{{max-width:220px;max-height:100px;object-fit:contain}}.box{{border:1px solid #ddd;padding:15px;margin-top:20px}}</style></head><body><div class='printbar'><a class='btn gray' href='/quotes'>Back</a><button onclick='window.print()'>Print / Save PDF</button></div><div class='top'><div>{logo_html}<p>1833 Inkster Blvd, Unit F13<br>Winnipeg, MB | 204-558-8473</p></div><div class='right'><h1>Quote / Estimate</h1><p><b>Quote #:</b> {esc(quote_num)}<br><b>Date:</b> {esc(created)}<br><b>Valid Until:</b> {esc(valid)}</p></div></div><div class='box'><h2>Customer</h2><p><b>Name:</b> {esc(info.get('customer',''))}<br><b>Email:</b> {esc(info.get('email',''))}<br><b>Phone:</b> {esc(info.get('phone',''))}<br><b>Vehicle:</b> {esc(info.get('vehicle',''))}</p><p><b>Notes:</b> {esc(info.get('notes',''))}</p></div><table><tr><th>Item</th><th>Qty</th><th>Price</th><th>Total</th></tr>{row_html}</table><div class='right'><p>Taxable Subtotal: {money(qd['taxable'])}<br>PST 7%: {money(qd['pst'])}<br>GST 5%: {money(qd['gst'])}</p><h2>Grand Total: {money(qd['total'])}</h2><p>Deposit Paid: -{money(qd['deposit'])}<br><b>Balance Due: {money(qd['balance'])}</b></p></div><p><small>Quote is subject to stock availability and price changes. Valid until date shown above.</small></p></body></html>"""
    safe="".join(c for c in info.get("customer","customer") if c.isalnum() or c in (" ","_","-")).strip().replace(" ","_") or "customer"; fp=QUOTE_DIR/(f"{'PREVIEW_' if preview else ''}{quote_num}_{safe}.html"); fp.write_text(html, encoding="utf-8")
    if save_history:
        rows=load_quote_history(); rows.append({"quote_number":quote_num,"created":created,"valid_until":valid,"customer":info.get("customer",""),"email":info.get("email",""),"phone":info.get("phone",""),"vehicle":info.get("vehicle",""),"item_count":item_count,"subtotal":money(qd["taxable"]),"gst":money(qd["gst"]),"pst":money(qd["pst"]),"grand_total":money(qd["total"]),"deposit":money(qd["deposit"]),"balance_due":money(qd["balance"]),"invoice_file":str(fp.relative_to(BASE))}); write_quote_history(rows)
    return fp

@app.route("/quotes")
def quotes():
    q=request.args.get("q","").lower(); rows=load_quote_history()
    if q: rows=[r for r in rows if q in " ".join(str(v) for v in r.values()).lower()]
    cards=""
    for r in rows[-150:][::-1]:
        qn=r.get("quote_number",""); inv=r.get("invoice_file","")
        cards+=f"<div class='card'><b>{esc(qn)}</b><br>{esc(r.get('customer',''))}<br><span class='small'>{esc(r.get('email',''))} • {esc(r.get('phone',''))} • {esc(r.get('vehicle',''))}</span><br>Total: <b>{esc(r.get('grand_total',''))}</b><br><a class='btn blue' href='/invoice?file={urllib.parse.quote(inv)}'>Open Invoice</a><form method='post' action='/deletequote' style='display:inline' onsubmit=\"return confirm('Delete this quote record?')\"><input type='hidden' name='quote_number' value='{esc(qn)}'><button class='red'>Delete Record</button></form></div>"
    return layout("Saved Quotes", f"<div class='card'><form><label>Search Saved Quotes</label><input name='q' value='{esc(q)}'><button>Search</button><a class='btn gray' href='/quotes'>Reset</a></form></div>{cards or '<div class=card>No saved quotes found.</div>'}", "quotes")

@app.post("/deletequote")
def delete_quote():
    target=request.form.get("quote_number",""); write_quote_history([r for r in load_quote_history() if r.get("quote_number","")!=target]); return redirect("/quotes")

@app.route("/invoice")
def invoice():
    file=request.args.get("file",""); fp=(BASE/file).resolve()
    if BASE.resolve() not in fp.parents and fp!=BASE.resolve(): abort(403)
    if not fp.exists(): return layout("Invoice","<div class='card'>Invoice file not found.</div>","quotes")
    return fp.read_text(encoding="utf-8", errors="ignore")

@app.route("/inventory", methods=["GET","POST"])
def inventory():
    if not is_admin(): abort(403)
    msg=""
    source_map={
        "normalized_wheels.csv": ("normalized_wheels","FASTCO","Wheel","Yes"),
        "vendor_files/autocountry/tires.csv": ("autocountry_tires","AUTOCOUNTRY","Tire","No"),
        "vendor_files/autocountry/wheels.csv": ("autocountry_wheels","AUTOCOUNTRY","Wheel","Yes"),
        "normalized_tires.csv": ("normalized_tires","MIXED","Tire","No"),
    }
    if request.method=="POST":
        target=request.form.get("target","normalized_wheels.csv"); file=request.files.get("csv_file")
        if target not in source_map: msg="<div class='card danger'>Invalid target file.</div>"
        elif file and file.filename:
            dest=DATA_DIR/target; dest.parent.mkdir(parents=True, exist_ok=True); file.save(dest)
            if db_enabled():
                source,vendor,ptype,publish=source_map[target]
                try:
                    count=import_products_to_db(dest, source, vendor, ptype, publish)
                    msg=f"<div class='card success'>Imported {count:,} rows into PostgreSQL from {esc(file.filename)}.</div>"
                except Exception as e: msg=f"<div class='card danger'>Database import failed: {esc(e)}</div>"
            else:
                load_products(force=True); msg=f"<div class='card success'>Uploaded {esc(file.filename)} to Render disk. Warning: file mode is not persistent.</div>"
        else: msg="<div class='card danger'>No file selected.</div>"
    db_status="Connected" if db_enabled() else "Not connected"
    prod_count=db_product_count() if db_enabled() else len(load_products(force=True))
    checks=f"<tr><td>PostgreSQL</td><td>{esc(db_status)}</td></tr><tr><td>Products in database/app</td><td>{prod_count:,}</td></tr><tr><td>Last Import</td><td>{esc(db_last_import() if db_enabled() else 'N/A')}</td></tr>"
    body=f"""{msg}<div class='card'><h2>Admin Tools / Inventory Import</h2><p>Upload CSV files here to import products into PostgreSQL. Once imported, products survive redeploys.</p><form method='post' enctype='multipart/form-data'><label>File Type</label><select name='target'><option value='normalized_wheels.csv'>Normalized Wheels</option><option value='vendor_files/autocountry/tires.csv'>AutoCountry Tires - Internal Only</option><option value='vendor_files/autocountry/wheels.csv'>AutoCountry Wheels</option><option value='normalized_tires.csv'>Normalized Tires</option></select><label>CSV File</label><input type='file' name='csv_file' accept='.csv'><button class='green'>Import Inventory File</button></form></div><div class='card'><h3>Database Status</h3><table><tr><th>Item</th><th>Status</th></tr>{checks}</table></div>"""
    return layout("Admin Tools", body, "inventory")

@app.route("/admin/services", methods=["GET","POST"])
def admin_services():
    if not is_admin(): abort(403)
    pricing=load_service_pricing(); msg=""
    if request.method=="POST":
        for k in DEFAULT_SERVICE_PRICING: pricing[k]=num(request.form.get(k, pricing.get(k,0)))
        save_service_pricing(pricing); msg="<div class='card success'>Service pricing updated.</div>"
    labels={"install_balance_each":"Install & Balance / Tire","tpms_each":"TPMS Sensor Each","lug_nut_kit_each":"Lug Nut Kit Each","shop_labor_hour":"Shop Labour / Hour","tire_rotation":"Tire Rotation","oil_change":"Oil Change","flat_repair_each":"Flat Repair / Tire"}
    fields="".join(f"<label>{esc(labels[k])}</label><input name='{k}' value='{pricing.get(k,0):.2f}'>" for k in DEFAULT_SERVICE_PRICING)
    return layout("Service Pricing", f"{msg}<div class='card'><h2>Service Pricing</h2><form method='post'>{fields}<button class='green'>Save Service Pricing</button></form></div>", "services")

@app.route("/admin/users")
def admin_users():
    if not is_admin(): abort(403)
    users=load_users(); rows=""
    for username,data in sorted(users.items()):
        rows+=f"<tr><td>{esc(username)}</td><td>{esc(data.get('role',''))}</td><td>{'Active' if data.get('active', True) else 'Disabled'}</td><td><form method='post' action='/admin/reset' style='display:inline'><input type='hidden' name='username' value='{esc(username)}'><input class='mini-input' name='password' placeholder='new password'><button class='blue'>Reset</button></form><form method='post' action='/admin/toggle' style='display:inline'><input type='hidden' name='username' value='{esc(username)}'><button class='gray'>{'Disable' if data.get('active', True) else 'Enable'}</button></form><form method='post' action='/admin/delete' style='display:inline' onsubmit=\"return confirm('Delete user?')\"><input type='hidden' name='username' value='{esc(username)}'><button class='red'>Delete</button></form></td></tr>"
    body=f"<div class='card'><h2>User Management</h2><table><tr><th>User</th><th>Role</th><th>Status</th><th>Actions</th></tr>{rows}</table></div><div class='card'><h3>Add User</h3><form method='post' action='/admin/add'><div class='row'><div><label>Username</label><input name='username'></div><div><label>Password</label><input name='password'></div></div><label>Role</label><select name='role'><option>Admin</option><option>Staff</option></select><button class='green'>Add User</button></form></div>"
    return layout("Admin Users", body, "admin")

@app.post("/admin/add")
def admin_add():
    if not is_admin(): abort(403)
    users=load_users(); username=request.form.get("username","").strip(); password=request.form.get("password",""); role=request.form.get("role","Staff")
    if username and password: users[username]={"password_hash":generate_password_hash(password),"role":role,"active":True}; save_users(users)
    return redirect("/admin/users")

@app.post("/admin/reset")
def admin_reset():
    if not is_admin(): abort(403)
    users=load_users(); username=request.form.get("username",""); password=request.form.get("password","")
    if username in users and password: users[username]["password_hash"]=generate_password_hash(password); save_users(users)
    return redirect("/admin/users")

@app.post("/admin/toggle")
def admin_toggle():
    if not is_admin(): abort(403)
    users=load_users(); username=request.form.get("username","")
    if username in users and username!=current_user(): users[username]["active"]=not users[username].get("active", True); save_users(users)
    return redirect("/admin/users")

@app.post("/admin/delete")
def admin_delete():
    if not is_admin(): abort(403)
    users=load_users(); username=request.form.get("username","")
    if username in users and username!=current_user(): users.pop(username,None); save_users(users)
    return redirect("/admin/users")

@app.route("/suppliers")
def suppliers():
    if not is_admin(): abort(403)
    data=load_suppliers(); body="<form method='post' action='/suppliers'>"
    for name,cfg in data.items():
        safe=name.replace(" ","_")
        body+=f"<div class='card'><h2>{esc(name)}</h2><label>Protocol</label><input name='{safe}_protocol' value='{esc(cfg.get('protocol',''))}'><label>DNS Host</label><input name='{safe}_dns_host' value='{esc(cfg.get('dns_host',''))}'><a class='btn blue' href='/dns/{urllib.parse.quote(name)}'>Test DNS</a><label>Host</label><input name='{safe}_host' value='{esc(cfg.get('host',''))}'><label>Username</label><input name='{safe}_username' value='{esc(cfg.get('username',''))}'><label>Password</label><input type='password' name='{safe}_password' value='{esc(cfg.get('password',''))}'><label>Local Folder</label><input name='{safe}_local_folder' value='{esc(cfg.get('local_folder',''))}'><label>Notes</label><textarea name='{safe}_notes'>{esc(cfg.get('notes',''))}</textarea></div>"
    body+="<button class='green'>Save Suppliers</button></form>"
    return layout("Suppliers", body, "suppliers")

@app.post("/suppliers")
def save_supplier_route():
    if not is_admin(): abort(403)
    data=load_suppliers()
    for name in data:
        safe=name.replace(" ","_")
        for key in ["protocol","dns_host","host","username","password","local_folder","notes"]:
            field=f"{safe}_{key}"
            if field in request.form: data[name][key]=request.form.get(field,"")
    save_suppliers(data); return redirect("/suppliers")

@app.route("/dns/<path:name>")
def dns(name):
    if not is_admin(): abort(403)
    cfg=load_suppliers().get(name, {}); host=(cfg.get("dns_host") or cfg.get("host") or "").strip()
    try: result=socket.gethostbyname_ex(host) if host else "No host entered"; body=f"<h2>DNS OK</h2><pre>{esc(result)}</pre>"
    except Exception as e: body=f"<h2>DNS Failed</h2><p>{esc(host)}</p><pre>{esc(e)}</pre>"
    return layout("DNS", f"<div class='card'>{body}<a class='btn' href='/suppliers'>Back</a></div>", "suppliers")

if __name__ == "__main__":
    ensure_dirs(); bootstrap_users(); init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
