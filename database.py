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
-- KONSINYASI — pola header/detail (1 surat jalan = banyak produk)
-- consignment_batches = 1 baris per pengiriman/surat jalan ke 1 toko
-- consignment_items    = 1 baris per produk di dalam batch tsb
-- ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS consignment_batches (
    id              TEXT    PRIMARY KEY,            -- e.g. KS-1720000000000
    tempat          TEXT    NOT NULL,               -- nama toko / konsinyee
    tanggal_mulai   TEXT    NOT NULL,               -- ISO date
    tanggal_str     TEXT    NOT NULL DEFAULT '',    -- format Bahasa Indonesia
    durasi_bulan    INTEGER NOT NULL DEFAULT 3,     -- 1, 2, atau 3 bulan
    komisi_persen   REAL    NOT NULL DEFAULT 0,     -- % komisi toko (0-100), berlaku utk semua produk di batch ini
    status          TEXT    NOT NULL DEFAULT 'aktif'
                        CHECK(status IN ('aktif','selesai')),
    catatan         TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS consignment_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id        TEXT    NOT NULL,
    produk_id       INTEGER NOT NULL,
    nama_produk     TEXT    NOT NULL,
    qty_titip       INTEGER NOT NULL DEFAULT 0,     -- unit dititipkan
    qty_terjual     INTEGER NOT NULL DEFAULT 0,     -- unit sudah terjual
    qty_kembali     INTEGER NOT NULL DEFAULT 0,     -- unit dikembalikan
    harga_jual      REAL    NOT NULL DEFAULT 0,     -- harga jual ke konsinyee
    harga_modal     REAL    NOT NULL DEFAULT 0,     -- HPP / modal per unit
    FOREIGN KEY (batch_id)  REFERENCES consignment_batches(id) ON DELETE CASCADE,
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

-- ─────────────────────────────────────────────────────────
-- RESEP PRODUK (Bill of Materials)
-- jumlah_per_unit = satuan bahan per 1 unit produk
-- Contoh: Dompet → Karton 0.2 lbr (artinya 1 lembar = 5 dompet)
-- ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS product_recipes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    produk_id       INTEGER NOT NULL,
    material_id     INTEGER NOT NULL,
    jumlah_per_unit REAL    NOT NULL DEFAULT 0,
    FOREIGN KEY (produk_id)   REFERENCES products(id)  ON DELETE CASCADE,
    FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE CASCADE,
    UNIQUE (produk_id, material_id)
);

-- ─────────────────────────────────────────────────────────
-- LOG PRODUKSI — 1 baris per batch produksi
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS productions (
    id           TEXT    PRIMARY KEY,
    produk_id    INTEGER NOT NULL,
    nama_produk  TEXT    NOT NULL,
    jumlah       INTEGER NOT NULL DEFAULT 0,
    tanggal      TEXT    NOT NULL,
    tanggal_str  TEXT    NOT NULL DEFAULT '',
    catatan      TEXT    DEFAULT '',
    FOREIGN KEY (produk_id) REFERENCES products(id)
);
 
-- ─────────────────────────────────────────────────────────
-- DETAIL BAHAN TERPAKAI PER BATCH PRODUKSI
-- Disimpan agar riwayat akurat walaupun resep diubah
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS production_materials (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    production_id   TEXT    NOT NULL,
    material_id     INTEGER NOT NULL,
    nama_material   TEXT    NOT NULL,
    jumlah_terpakai REAL    NOT NULL DEFAULT 0,
    satuan          TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY (production_id) REFERENCES productions(id) ON DELETE CASCADE
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
# MIGRASI — pindahkan data konsinyasi lama (1 baris = 1 produk)
# ke skema baru header/detail (1 batch = banyak produk).
# Aman dijalankan berkali-kali: hanya jalan jika tabel lama
# 'consignments' masih ada (belum pernah dimigrasi sebelumnya).
# ─────────────────────────────────────────────────────
def _migrate_legacy_consignments(conn: sqlite3.Connection) -> None:
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='consignments'"
    ).fetchone()
    if not exists:
        return

    old_rows = conn.execute("SELECT * FROM consignments").fetchall()

    # Matikan sementara FK check — data lama bisa saja mengacu ke produk
    # yang sudah dihapus dari master produk, itu tidak boleh menggagalkan migrasi.
    conn.execute("PRAGMA foreign_keys=OFF")
    for r in old_rows:
        conn.execute(
            """INSERT OR IGNORE INTO consignment_batches
               (id, tempat, tanggal_mulai, tanggal_str, durasi_bulan,
                komisi_persen, status, catatan)
               VALUES (?,?,?,?,?,?,?,?)""",
            (r["id"], r["tempat"], r["tanggal_mulai"], r["tanggal_str"],
             r["durasi_bulan"], r["komisi_persen"], r["status"], r["catatan"]),
        )
        conn.execute(
            """INSERT INTO consignment_items
               (batch_id, produk_id, nama_produk, qty_titip,
                qty_terjual, qty_kembali, harga_jual, harga_modal)
               VALUES (?,?,?,?,?,?,?,?)""",
            (r["id"], r["produk_id"], r["nama_produk"], r["qty_titip"],
             r["qty_terjual"], r["qty_kembali"], r["harga_jual"], r["harga_modal"]),
        )
    conn.execute("PRAGMA foreign_keys=ON")

    conn.execute("ALTER TABLE consignments RENAME TO consignments_legacy_backup")
    conn.commit()
    if old_rows:
        print(f"✅ Migrasi {len(old_rows)} konsinyasi lama ke skema multi-produk selesai.")


# ─────────────────────────────────────────────────────
# INIT — dipanggil sekali saat aplikasi start
# ─────────────────────────────────────────────────────
def init_db() -> None:
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    _migrate_legacy_consignments(conn)
    conn.close()
    print("✅ Database siap.")
