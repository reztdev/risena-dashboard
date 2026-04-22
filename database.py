# database.py — Inisialisasi SQLite untuk BatikCraft
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "risena.db"


def get_conn() -> sqlite3.Connection:
    """Buat koneksi SQLite dengan row_factory agar hasil query seperti dict."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ─────────────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kode        TEXT    NOT NULL DEFAULT '',
    nama        TEXT    NOT NULL,
    kategori    TEXT    NOT NULL DEFAULT 'Lainnya',
    stok        INTEGER NOT NULL DEFAULT 0,
    min_stok    INTEGER NOT NULL DEFAULT 5,
    satuan      TEXT    NOT NULL DEFAULT 'pcs',
    deskripsi   TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS materials (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    kode         TEXT    NOT NULL DEFAULT '',
    nama         TEXT    NOT NULL,
    kategori     TEXT    NOT NULL DEFAULT 'Lainnya',
    stok         REAL    NOT NULL DEFAULT 0,
    min_stok     REAL    NOT NULL DEFAULT 5,
    satuan       TEXT    NOT NULL DEFAULT 'meter',
    harga_satuan REAL    NOT NULL DEFAULT 0,
    supplier     TEXT    DEFAULT '',
    catatan      TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS prices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    produk_id   INTEGER NOT NULL,
    overhead    REAL    NOT NULL DEFAULT 0,
    harga_jual  REAL    NOT NULL DEFAULT 0,
    FOREIGN KEY (produk_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS price_components (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    price_id    INTEGER NOT NULL,
    nama        TEXT    NOT NULL,
    harga       REAL    NOT NULL DEFAULT 0,
    FOREIGN KEY (price_id) REFERENCES prices(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS orders (
    id          TEXT    PRIMARY KEY,
    customer    TEXT    NOT NULL DEFAULT 'Umum',
    date        TEXT    NOT NULL,
    date_str    TEXT    NOT NULL DEFAULT '',
    subtotal    REAL    NOT NULL DEFAULT 0,
    discount    REAL    NOT NULL DEFAULT 0,
    total       REAL    NOT NULL DEFAULT 0,
    note        TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS order_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    TEXT    NOT NULL,
    price_id    INTEGER,
    nama        TEXT    NOT NULL,
    harga       REAL    NOT NULL DEFAULT 0,
    qty         INTEGER NOT NULL DEFAULT 1,
    subtotal    REAL    NOT NULL DEFAULT 0,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cashflows (
    id          TEXT    PRIMARY KEY,
    type        TEXT    NOT NULL CHECK(type IN ('in','out')),
    date        TEXT    NOT NULL,
    date_str    TEXT    NOT NULL DEFAULT '',
    desc_text   TEXT    NOT NULL,
    category    TEXT    NOT NULL DEFAULT 'Lain-lain',
    amount      REAL    NOT NULL DEFAULT 0
);

-- ─────────────────────────────────────────────────────
-- TABEL KONSINYASI
-- Menyimpan barang yang dititipkan ke toko/konsinyee.
-- Setiap baris = 1 batch konsinyasi per produk per tempat.
-- ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS consignments (
    id              TEXT    PRIMARY KEY,            -- e.g. KS-1720000000000
    produk_id       INTEGER NOT NULL,
    nama_produk     TEXT    NOT NULL,
    tempat          TEXT    NOT NULL,               -- nama toko / konsinyee
    tanggal_mulai   TEXT    NOT NULL,               -- ISO date
    tanggal_str     TEXT    NOT NULL DEFAULT '',    -- format Bahasa Indonesia
    durasi_bulan    INTEGER NOT NULL DEFAULT 3,     -- 1, 2, atau 3 bulan
    qty_titip       INTEGER NOT NULL DEFAULT 0,     -- unit dititipkan
    qty_terjual     INTEGER NOT NULL DEFAULT 0,     -- unit sudah terjual
    qty_kembali     INTEGER NOT NULL DEFAULT 0,     -- unit dikembalikan
    harga_jual      REAL    NOT NULL DEFAULT 0,     -- harga jual ke konsinyee
    harga_modal     REAL    NOT NULL DEFAULT 0,     -- HPP / modal per unit
    komisi_persen   REAL    NOT NULL DEFAULT 0,     -- % komisi toko (0-100)
    status          TEXT    NOT NULL DEFAULT 'aktif'
                        CHECK(status IN ('aktif','selesai')),
    catatan         TEXT    DEFAULT '',
    FOREIGN KEY (produk_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS print_logs (
    id           TEXT    PRIMARY KEY,           -- e.g. PL-1720000000000
    type         TEXT    NOT NULL
                     CHECK(type IN ('nota','surat_jalan')),
    ref_id       TEXT    NOT NULL,              -- order_id atau consignment_id
    ref_label    TEXT    NOT NULL DEFAULT '',   -- nama customer / nama toko
    printed_at   TEXT    NOT NULL,              -- ISO datetime
    printed_str  TEXT    NOT NULL DEFAULT ''    -- format Bahasa Indonesia
);
"""


def fmt_date_id(dt: datetime) -> str:
    """Format tanggal dalam Bahasa Indonesia: 01 Jan 2025"""
    bulan = [
        "", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
        "Jul", "Agu", "Sep", "Okt", "Nov", "Des"
    ]
    return f"{dt.day:02d} {bulan[dt.month]} {dt.year}"


# ─────────────────────────────────────────────────────
# INIT — dipanggil sekali saat aplikasi start
# ─────────────────────────────────────────────────────
def init_db() -> None:
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print("✅ Database siap.")
