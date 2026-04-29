# production.py — Resep Produk (BOM) & Manajemen Produksi untuk Risena
# ─────────────────────────────────────────────────────────────────────
# Fitur:
#   1. Resep Produk (Bill of Materials)
#      → Definisikan bahan apa + berapa yang dibutuhkan per 1 unit produk
#      → Contoh: 1 dompet = 0.2 lbr karton + 1 resleting + 2 kancing + 10cm busa
#
#   2. Produksi (Manufacturing Order)
#      → Catat batch produksi
#      → Otomatis KURANGI stok bahan sesuai resep × qty produksi
#      → Otomatis TAMBAH stok produk jadi
#      → Validasi: cek apakah stok bahan cukup sebelum produksi
#
#   3. Kapasitas Produksi
#      → Hitung berapa unit maksimal bisa diproduksi dari stok bahan saat ini
#
#   4. HPP Otomatis dari Resep
#      → Hitung HPP per unit berdasarkan harga_satuan bahan × jumlah_per_unit
# ─────────────────────────────────────────────────────────────────────

import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_conn, fmt_date_id

router = APIRouter(prefix="/api", tags=["produksi"])


# ════════════════════════════════════════════════════════════
# SCHEMAS
# ════════════════════════════════════════════════════════════

class RecipeItemIn(BaseModel):
    """Satu baris resep: bahan tertentu, berapa per 1 unit produk."""
    materialId:    int
    jumlahPerUnit: float   # misal 0.2 (karton), 1 (resleting), 10 (busa cm)


class RecipeIn(BaseModel):
    """Resep lengkap untuk 1 produk. Kirim ulang seluruh baris untuk update."""
    produkId: int
    items:    list[RecipeItemIn] = []


class ProductionIn(BaseModel):
    """Input untuk mencatat 1 batch produksi."""
    produkId:  int
    jumlah:    int           # qty unit yang diproduksi
    tanggal:   str           # ISO date string, misal "2026-04-29"
    tanggalStr: str = ""     # format Bahasa Indonesia (opsional, auto-generate)
    catatan:   str = ""


# ════════════════════════════════════════════════════════════
# SCHEMA ADDITIONS — dieksekusi dari init_db() di database.py
# Tambahkan dua CREATE TABLE ini ke variabel SCHEMA di database.py
# ════════════════════════════════════════════════════════════

PRODUCTION_SCHEMA = """
-- ─────────────────────────────────────────────────────────
-- RESEP PRODUK (Bill of Materials)
-- Setiap baris = 1 bahan yang dibutuhkan untuk 1 produk.
-- jumlah_per_unit = berapa satuan bahan per 1 unit produk.
-- Contoh: produk=Dompet, material=Karton, jumlah_per_unit=0.2
--   → 1 lembar karton menghasilkan 5 dompet
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS product_recipes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    produk_id       INTEGER NOT NULL,
    material_id     INTEGER NOT NULL,
    jumlah_per_unit REAL    NOT NULL DEFAULT 0,
    FOREIGN KEY (produk_id)   REFERENCES products(id)  ON DELETE CASCADE,
    FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE CASCADE,
    UNIQUE (produk_id, material_id)   -- 1 bahan hanya 1 baris per produk
);

-- ─────────────────────────────────────────────────────────
-- LOG PRODUKSI
-- Setiap baris = 1 batch produksi yang sudah dijalankan.
-- Stok bahan sudah dikurangi, stok produk sudah ditambah.
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS productions (
    id           TEXT    PRIMARY KEY,       -- e.g. PROD-1720000000000
    produk_id    INTEGER NOT NULL,
    nama_produk  TEXT    NOT NULL,
    jumlah       INTEGER NOT NULL DEFAULT 0,
    tanggal      TEXT    NOT NULL,          -- ISO date
    tanggal_str  TEXT    NOT NULL DEFAULT '',
    catatan      TEXT    DEFAULT '',
    FOREIGN KEY (produk_id) REFERENCES products(id)
);

-- ─────────────────────────────────────────────────────────
-- DETAIL LOG PRODUKSI (bahan yang terpakai per batch)
-- Disimpan agar riwayat tetap akurat meski resep diubah.
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


# ════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════

def _fmt(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return fmt_date_id(dt)
    except Exception:
        return iso


def _get_recipe(conn, produk_id: int) -> list[dict]:
    """Ambil resep lengkap sebuah produk, join ke materials untuk info bahan."""
    rows = conn.execute(
        """
        SELECT
            pr.id,
            pr.produk_id,
            pr.material_id,
            pr.jumlah_per_unit,
            m.nama      AS nama_material,
            m.satuan    AS satuan,
            m.stok      AS stok_tersedia,
            m.harga_satuan
        FROM product_recipes pr
        JOIN materials m ON m.id = pr.material_id
        WHERE pr.produk_id = ?
        """,
        (produk_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def _hitung_hpp_dari_resep(recipe_items: list[dict]) -> float:
    """
    HPP otomatis = Σ (harga_satuan_bahan × jumlah_per_unit)
    Ini menggantikan / melengkapi input manual di price_components.
    """
    return sum(item["harga_satuan"] * item["jumlah_per_unit"] for item in recipe_items)


def _hitung_kapasitas(recipe_items: list[dict]) -> dict:
    """
    Hitung berapa unit maksimal bisa diproduksi dari stok bahan saat ini.
    Bottleneck = bahan yang paling cepat habis.
    """
    if not recipe_items:
        return {"maxUnit": 0, "bottleneck": None, "detail": []}

    detail = []
    for item in recipe_items:
        if item["jumlah_per_unit"] <= 0:
            continue
        maks_dari_bahan = item["stok_tersedia"] / item["jumlah_per_unit"]
        detail.append({
            "materialId":    item["material_id"],
            "namaMaterial":  item["nama_material"],
            "stokTersedia":  item["stok_tersedia"],
            "satuan":        item["satuan"],
            "jumlahPerUnit": item["jumlah_per_unit"],
            "maxUnit":       int(maks_dari_bahan),
        })

    if not detail:
        return {"maxUnit": 0, "bottleneck": None, "detail": detail}

    bottleneck = min(detail, key=lambda x: x["maxUnit"])
    return {
        "maxUnit":    bottleneck["maxUnit"],
        "bottleneck": {
            "materialId":   bottleneck["materialId"],
            "namaMaterial": bottleneck["namaMaterial"],
            "stok":         bottleneck["stokTersedia"],
            "satuan":       bottleneck["satuan"],
        },
        "detail": detail,
    }


# ════════════════════════════════════════════════════════════
# ENDPOINTS — RESEP PRODUK (BOM)
# ════════════════════════════════════════════════════════════

@router.get("/recipes")
def get_all_recipes() -> list[dict]:
    """
    List semua resep yang sudah dibuat.
    Return dikelompokkan per produk.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                pr.id,
                pr.produk_id,
                pr.material_id,
                pr.jumlah_per_unit,
                p.nama      AS nama_produk,
                m.nama      AS nama_material,
                m.satuan    AS satuan,
                m.harga_satuan
            FROM product_recipes pr
            JOIN products   p ON p.id = pr.produk_id
            JOIN materials  m ON m.id = pr.material_id
            ORDER BY p.nama, m.nama
            """
        ).fetchall()

    # Group per produk
    grouped: dict[int, dict] = {}
    for r in rows:
        pid = r["produk_id"]
        if pid not in grouped:
            grouped[pid] = {
                "produkId":   pid,
                "namaProduk": r["nama_produk"],
                "items":      [],
                "hppOtomatis": 0.0,
            }
        item = {
            "id":            r["id"],
            "materialId":    r["material_id"],
            "namaMaterial":  r["nama_material"],
            "jumlahPerUnit": r["jumlah_per_unit"],
            "satuan":        r["satuan"],
            "hargaSatuan":   r["harga_satuan"],
            "biayaPerUnit":  round(r["harga_satuan"] * r["jumlah_per_unit"], 2),
        }
        grouped[pid]["items"].append(item)
        grouped[pid]["hppOtomatis"] += item["biayaPerUnit"]

    result = list(grouped.values())
    for r in result:
        r["hppOtomatis"] = round(r["hppOtomatis"], 2)
    return result


@router.get("/recipes/{produk_id}")
def get_recipe(produk_id: int) -> dict:
    """
    Resep + HPP otomatis + kapasitas produksi saat ini untuk 1 produk.
    Endpoint ini cocok dipanggil saat buka halaman 'Resep Produk'.
    """
    with get_conn() as conn:
        produk = conn.execute(
            "SELECT id, nama FROM products WHERE id=?", (produk_id,)
        ).fetchone()
        if not produk:
            raise HTTPException(404, "Produk tidak ditemukan")

        recipe_items = _get_recipe(conn, produk_id)

    hpp = _hitung_hpp_dari_resep(recipe_items)
    kapasitas = _hitung_kapasitas(recipe_items)

    return {
        "produkId":    produk_id,
        "namaProduk":  produk["nama"],
        "hppOtomatis": round(hpp, 2),
        "kapasitas":   kapasitas,
        "items": [
            {
                "id":            item["id"],
                "materialId":    item["material_id"],
                "namaMaterial":  item["nama_material"],
                "jumlahPerUnit": item["jumlah_per_unit"],
                "satuan":        item["satuan"],
                "hargaSatuan":   item["harga_satuan"],
                "biayaPerUnit":  round(item["harga_satuan"] * item["jumlah_per_unit"], 2),
            }
            for item in recipe_items
        ],
    }


@router.post("/recipes", status_code=201)
def save_recipe(body: RecipeIn) -> dict:
    """
    Simpan/update resep produk (upsert penuh).
    Kirim seluruh items — baris lama akan dihapus dan diganti.
    Cocok untuk form 'Simpan Resep' di frontend.
    """
    with get_conn() as conn:
        produk = conn.execute(
            "SELECT id FROM products WHERE id=?", (body.produkId,)
        ).fetchone()
        if not produk:
            raise HTTPException(404, "Produk tidak ditemukan")

        # Validasi semua material_id ada
        for item in body.items:
            mat = conn.execute(
                "SELECT id FROM materials WHERE id=?", (item.materialId,)
            ).fetchone()
            if not mat:
                raise HTTPException(400, f"Bahan ID {item.materialId} tidak ditemukan")
            if item.jumlahPerUnit <= 0:
                raise HTTPException(400, f"jumlahPerUnit untuk bahan ID {item.materialId} harus > 0")

        # Hapus resep lama, isi dengan yang baru
        conn.execute(
            "DELETE FROM product_recipes WHERE produk_id=?", (body.produkId,)
        )
        for item in body.items:
            conn.execute(
                "INSERT INTO product_recipes (produk_id, material_id, jumlah_per_unit) "
                "VALUES (?, ?, ?)",
                (body.produkId, item.materialId, item.jumlahPerUnit),
            )
        conn.commit()

        recipe_items = _get_recipe(conn, body.produkId)

    hpp = _hitung_hpp_dari_resep(recipe_items)
    kapasitas = _hitung_kapasitas(recipe_items)

    return {
        "ok":          True,
        "produkId":    body.produkId,
        "jumlahBahan": len(body.items),
        "hppOtomatis": round(hpp, 2),
        "kapasitas":   kapasitas,
    }


@router.delete("/recipes/{produk_id}")
def delete_recipe(produk_id: int) -> dict:
    """Hapus seluruh resep sebuah produk."""
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM product_recipes WHERE produk_id=?", (produk_id,)
        )
        conn.commit()
    return {"ok": True}


# ════════════════════════════════════════════════════════════
# ENDPOINTS — KAPASITAS PRODUKSI
# ════════════════════════════════════════════════════════════

@router.get("/capacity/{produk_id}")
def get_capacity(produk_id: int) -> dict:
    """
    Berapa unit produk bisa dibuat dari stok bahan saat ini?
    Jawaban cepat tanpa perlu membuka halaman resep.

    Response:
    - maxUnit    : jumlah unit yang bisa diproduksi sekarang
    - bottleneck : bahan yang jadi pembatas (stok paling sedikit relatif ke kebutuhan)
    - detail     : rincian per bahan
    """
    with get_conn() as conn:
        produk = conn.execute(
            "SELECT id, nama FROM products WHERE id=?", (produk_id,)
        ).fetchone()
        if not produk:
            raise HTTPException(404, "Produk tidak ditemukan")

        recipe_items = _get_recipe(conn, produk_id)
        if not recipe_items:
            raise HTTPException(400, "Produk ini belum punya resep. Buat resep dulu di /api/recipes.")

    kapasitas = _hitung_kapasitas(recipe_items)
    return {
        "produkId":   produk_id,
        "namaProduk": produk["nama"],
        **kapasitas,
    }


# ════════════════════════════════════════════════════════════
# ENDPOINTS — PRODUKSI
# ════════════════════════════════════════════════════════════

@router.get("/productions")
def get_productions() -> list[dict]:
    """Riwayat semua batch produksi."""
    with get_conn() as conn:
        prods = conn.execute(
            "SELECT * FROM productions ORDER BY tanggal DESC"
        ).fetchall()
        result = []
        for p in prods:
            mats = conn.execute(
                "SELECT * FROM production_materials WHERE production_id=?", (p["id"],)
            ).fetchall()
            result.append({
                "id":          p["id"],
                "produkId":    p["produk_id"],
                "namaProduk":  p["nama_produk"],
                "jumlah":      p["jumlah"],
                "tanggal":     p["tanggal"],
                "tanggalStr":  p["tanggal_str"],
                "catatan":     p["catatan"],
                "bahanTerpakai": [
                    {
                        "materialId":    m["material_id"],
                        "namaMaterial":  m["nama_material"],
                        "jumlahTerpakai": m["jumlah_terpakai"],
                        "satuan":        m["satuan"],
                    }
                    for m in mats
                ],
            })
    return result


@router.post("/productions", status_code=201)
def create_production(body: ProductionIn) -> dict:
    """
    Catat batch produksi baru.

    Alur yang terjadi secara atomik (1 transaksi):
    1. Ambil resep produk
    2. Hitung kebutuhan bahan = resep × jumlah produksi
    3. Validasi stok semua bahan CUKUP (jika tidak, tolak dengan pesan detail)
    4. Kurangi stok setiap bahan
    5. Tambah stok produk jadi
    6. Simpan log produksi + detail bahan terpakai

    Simulasi yang kamu ceritakan:
    - Resep: karton 0.2 lembar per dompet
    - Produksi 5 dompet → karton berkurang 1 lembar, stok dompet +5
    """
    if body.jumlah <= 0:
        raise HTTPException(400, "Jumlah produksi harus lebih dari 0")

    tgl_str = body.tanggalStr or _fmt(body.tanggal)

    with get_conn() as conn:
        # ── 1. Cek produk ada ────────────────────────────
        produk = conn.execute(
            "SELECT id, nama, stok FROM products WHERE id=?", (body.produkId,)
        ).fetchone()
        if not produk:
            raise HTTPException(404, "Produk tidak ditemukan")

        # ── 2. Ambil resep ────────────────────────────────
        recipe_items = _get_recipe(conn, body.produkId)
        if not recipe_items:
            raise HTTPException(
                400,
                f"Produk '{produk['nama']}' belum punya resep bahan. "
                "Buat resep dulu di menu Resep Produk."
            )

        # ── 3. Hitung kebutuhan & validasi stok ──────────
        kebutuhan = []
        kekurangan = []
        for item in recipe_items:
            dibutuhkan = round(item["jumlah_per_unit"] * body.jumlah, 6)
            tersedia   = item["stok_tersedia"]
            kebutuhan.append({
                "material_id":   item["material_id"],
                "nama_material": item["nama_material"],
                "satuan":        item["satuan"],
                "dibutuhkan":    dibutuhkan,
                "tersedia":      tersedia,
                "cukup":         tersedia >= dibutuhkan,
            })
            if tersedia < dibutuhkan:
                kekurangan.append({
                    "namaMaterial": item["nama_material"],
                    "dibutuhkan":   dibutuhkan,
                    "tersedia":     tersedia,
                    "kurang":       round(dibutuhkan - tersedia, 4),
                    "satuan":       item["satuan"],
                })

        if kekurangan:
            raise HTTPException(
                status_code=422,
                detail={
                    "pesan": f"Stok bahan tidak cukup untuk produksi {body.jumlah} unit.",
                    "kekurangan": kekurangan,
                }
            )

        # ── 4 & 5. Atomik: kurangi bahan, tambah produk ──
        prod_id = f"PROD-{int(time.time() * 1000)}"

        for k in kebutuhan:
            conn.execute(
                "UPDATE materials SET stok = MAX(0, stok - ?) WHERE id=?",
                (k["dibutuhkan"], k["material_id"]),
            )

        stok_baru_produk = produk["stok"] + body.jumlah
        conn.execute(
            "UPDATE products SET stok=? WHERE id=?",
            (stok_baru_produk, body.produkId),
        )

        # ── 6. Simpan log produksi ────────────────────────
        conn.execute(
            "INSERT INTO productions (id, produk_id, nama_produk, jumlah, tanggal, tanggal_str, catatan) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (prod_id, body.produkId, produk["nama"],
             body.jumlah, body.tanggal, tgl_str, body.catatan),
        )
        for k in kebutuhan:
            conn.execute(
                "INSERT INTO production_materials "
                "(production_id, material_id, nama_material, jumlah_terpakai, satuan) "
                "VALUES (?, ?, ?, ?, ?)",
                (prod_id, k["material_id"], k["nama_material"], k["dibutuhkan"], k["satuan"]),
            )

        conn.commit()

    return {
        "ok":           True,
        "id":           prod_id,
        "produkId":     body.produkId,
        "namaProduk":   produk["nama"],
        "jumlah":       body.jumlah,
        "stokProdukBaru": stok_baru_produk,
        "bahanTerpakai": [
            {
                "namaMaterial":   k["nama_material"],
                "jumlahTerpakai": k["dibutuhkan"],
                "satuan":         k["satuan"],
            }
            for k in kebutuhan
        ],
    }


@router.delete("/productions/{production_id}")
def delete_production(production_id: str) -> dict:
    """
    Batalkan / hapus log produksi.
    PERHATIAN: ini MEMBALIKKAN stok (tambah bahan kembali, kurangi produk).
    Gunakan hanya jika yakin batch tersebut salah input.
    """
    with get_conn() as conn:
        prod = conn.execute(
            "SELECT * FROM productions WHERE id=?", (production_id,)
        ).fetchone()
        if not prod:
            raise HTTPException(404, "Log produksi tidak ditemukan")

        mats = conn.execute(
            "SELECT * FROM production_materials WHERE production_id=?", (production_id,)
        ).fetchall()

        # Balikkan stok bahan
        for m in mats:
            conn.execute(
                "UPDATE materials SET stok = stok + ? WHERE id=?",
                (m["jumlah_terpakai"], m["material_id"]),
            )

        # Balikkan stok produk
        conn.execute(
            "UPDATE products SET stok = MAX(0, stok - ?) WHERE id=?",
            (prod["jumlah"], prod["produk_id"]),
        )

        conn.execute("DELETE FROM productions WHERE id=?", (production_id,))
        conn.commit()

    return {"ok": True, "pesanBatalkan": f"Produksi {production_id} dibatalkan, stok dikembalikan."}
