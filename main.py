# main.py — BatikCraft Backend API (FastAPI + SQLite)
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from database import get_conn, init_db, fmt_date_id
from datetime import datetime

from auth import router as auth_router
from consignment import router as consignment_router
from printing import router as printing_router         
                 

# ─────────────────────────────────────────────────────
# LIFESPAN — inisialisasi DB saat startup
# ─────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("🪡  Risena Collection siap dijalankan.")
    yield


app = FastAPI(title="Risena API", version="2.1", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(consignment_router)
app.include_router(printing_router)

PUBLIC_DIR = Path(__file__).parent / "public"


# ─────────────────────────────────────────────────────
# PYDANTIC MODELS (request body)
# ─────────────────────────────────────────────────────
class ProductIn(BaseModel):
    kode:      str  = ""
    nama:      str
    kategori:  str  = "Lainnya"
    stok:      int  = 0
    minStok:   int  = Field(5, alias="minStok")
    satuan:    str  = "pcs"
    deskripsi: str  = ""

    model_config = {"populate_by_name": True}


class MaterialIn(BaseModel):
    kode:        str   = ""
    nama:        str
    kategori:    str   = "Lainnya"
    stok:        float = 0
    minStok:     float = Field(5, alias="minStok")
    satuan:      str   = "meter"
    hargaSatuan: float = Field(0, alias="hargaSatuan")
    supplier:    str   = ""
    catatan:     str   = ""

    model_config = {"populate_by_name": True}


class StokAdjIn(BaseModel):
    type:       str   = "in"   # "in" = stok masuk, "out" = stok keluar
    jumlah:     float = 0
    keterangan: str   = ""


class ComponentIn(BaseModel):
    nama:  str
    harga: float = 0


class PriceIn(BaseModel):
    produkId:   int
    overhead:   float = 0
    hargaJual:  float = 0
    components: list[ComponentIn] = []


class OrderItemIn(BaseModel):
    priceId:  Optional[int] = None
    nama:     str
    harga:    float
    qty:      int
    subtotal: float


class OrderIn(BaseModel):
    id:       str
    customer: str   = "Umum"
    date:     str
    dateStr:  str   = ""
    subtotal: float = 0
    discount: float = 0
    total:    float = 0
    note:     str   = ""
    items:    list[OrderItemIn] = []


class CashflowIn(BaseModel):
    id:       Optional[str] = None
    type:     str  = "in"
    date:     str
    dateStr:  str  = ""
    desc:     str
    category: str  = "Lain-lain"
    amount:   float


# ─────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────
def _fmt_date_from_iso(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return fmt_date_id(dt)
    except Exception:
        return iso


def _material_row(r) -> dict:
    return {
        "id":          r["id"],
        "kode":        r["kode"],
        "nama":        r["nama"],
        "kategori":    r["kategori"],
        "stok":        r["stok"],
        "minStok":     r["min_stok"],
        "satuan":      r["satuan"],
        "hargaSatuan": r["harga_satuan"],
        "supplier":    r["supplier"],
        "catatan":     r["catatan"],
    }


# ═══════════════════════════════════════════════════════════
# PRODUCTS
# ═══════════════════════════════════════════════════════════

@app.get("/api/products")
def get_products() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM products ORDER BY id").fetchall()
    return [
        {
            "id":        r["id"],
            "kode":      r["kode"],
            "nama":      r["nama"],
            "kategori":  r["kategori"],
            "stok":      r["stok"],
            "minStok":   r["min_stok"],
            "satuan":    r["satuan"],
            "deskripsi": r["deskripsi"],
        }
        for r in rows
    ]


@app.post("/api/products", status_code=status.HTTP_201_CREATED)
def create_product(body: ProductIn) -> dict:
    if not body.nama.strip():
        raise HTTPException(400, "Nama produk wajib diisi")
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO products (kode,nama,kategori,stok,min_stok,satuan,deskripsi) "
            "VALUES (?,?,?,?,?,?,?)",
            (body.kode, body.nama, body.kategori, body.stok,
             body.minStok, body.satuan, body.deskripsi),
        )
        conn.commit()
        new_id = cur.lastrowid
    return {
        "id": new_id, "kode": body.kode, "nama": body.nama,
        "kategori": body.kategori, "stok": body.stok, "minStok": body.minStok,
        "satuan": body.satuan, "deskripsi": body.deskripsi,
    }


@app.put("/api/products/{product_id}")
def update_product(product_id: int, body: ProductIn) -> dict:
    with get_conn() as conn:
        conn.execute(
            "UPDATE products SET kode=?,nama=?,kategori=?,stok=?,min_stok=?,satuan=?,deskripsi=? "
            "WHERE id=?",
            (body.kode, body.nama, body.kategori, body.stok,
             body.minStok, body.satuan, body.deskripsi, product_id),
        )
        conn.commit()
    return {
        "id": product_id, "kode": body.kode, "nama": body.nama,
        "kategori": body.kategori, "stok": body.stok, "minStok": body.minStok,
        "satuan": body.satuan, "deskripsi": body.deskripsi,
    }


@app.delete("/api/products/{product_id}")
def delete_product(product_id: int) -> dict:
    with get_conn() as conn:
        conn.execute("DELETE FROM products WHERE id=?", (product_id,))
        conn.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# MATERIALS (Stok Bahan Baku)
# ═══════════════════════════════════════════════════════════

@app.get("/api/materials")
def get_materials() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM materials ORDER BY id").fetchall()
    return [_material_row(r) for r in rows]


@app.post("/api/materials", status_code=status.HTTP_201_CREATED)
def create_material(body: MaterialIn) -> dict:
    if not body.nama.strip():
        raise HTTPException(400, "Nama bahan wajib diisi")
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO materials (kode,nama,kategori,stok,min_stok,satuan,harga_satuan,supplier,catatan) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (body.kode, body.nama, body.kategori, body.stok,
             body.minStok, body.satuan, body.hargaSatuan, body.supplier, body.catatan),
        )
        conn.commit()
        new_id = cur.lastrowid
        row = conn.execute("SELECT * FROM materials WHERE id=?", (new_id,)).fetchone()
    return _material_row(row)


@app.put("/api/materials/{material_id}")
def update_material(material_id: int, body: MaterialIn) -> dict:
    with get_conn() as conn:
        conn.execute(
            "UPDATE materials SET kode=?,nama=?,kategori=?,stok=?,min_stok=?,satuan=?,harga_satuan=?,supplier=?,catatan=? "
            "WHERE id=?",
            (body.kode, body.nama, body.kategori, body.stok,
             body.minStok, body.satuan, body.hargaSatuan, body.supplier, body.catatan,
             material_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
    return _material_row(row)


@app.delete("/api/materials/{material_id}")
def delete_material(material_id: int) -> dict:
    with get_conn() as conn:
        conn.execute("DELETE FROM materials WHERE id=?", (material_id,))
        conn.commit()
    return {"ok": True}


@app.post("/api/materials/{material_id}/stok")
def adjust_material_stok(material_id: int, body: StokAdjIn) -> dict:
    """Tambah atau kurangi stok bahan baku."""
    if body.jumlah <= 0:
        raise HTTPException(400, "Jumlah harus lebih dari 0")
    with get_conn() as conn:
        row = conn.execute("SELECT stok FROM materials WHERE id=?", (material_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Bahan tidak ditemukan")
        current = row["stok"]
        if body.type == "in":
            new_stok = current + body.jumlah
        else:
            new_stok = max(0.0, current - body.jumlah)
        conn.execute("UPDATE materials SET stok=? WHERE id=?", (new_stok, material_id))
        conn.commit()
    return {"stok": new_stok}


# ═══════════════════════════════════════════════════════════
# PRICES (Harga & HPP)
# ═══════════════════════════════════════════════════════════

@app.get("/api/prices")
def get_prices() -> list[dict]:
    with get_conn() as conn:
        price_rows = conn.execute("SELECT * FROM prices ORDER BY id").fetchall()
        result = []
        for p in price_rows:
            comps = conn.execute(
                "SELECT nama, harga FROM price_components WHERE price_id=?", (p["id"],)
            ).fetchall()
            result.append({
                "id":         p["id"],
                "produkId":   p["produk_id"],
                "overhead":   p["overhead"],
                "hargaJual":  p["harga_jual"],
                "components": [{"nama": c["nama"], "harga": c["harga"]} for c in comps],
            })
    return result


@app.post("/api/prices", status_code=status.HTTP_201_CREATED)
def create_price(body: PriceIn) -> dict:
    if not body.produkId:
        raise HTTPException(400, "Produk wajib dipilih")
    comps = [c for c in body.components if c.nama.strip()]
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO prices (produk_id,overhead,harga_jual) VALUES (?,?,?)",
            (body.produkId, body.overhead, body.hargaJual),
        )
        pid = cur.lastrowid
        for c in comps:
            conn.execute(
                "INSERT INTO price_components (price_id,nama,harga) VALUES (?,?,?)",
                (pid, c.nama, c.harga),
            )
        conn.commit()
    return {
        "id": pid, "produkId": body.produkId,
        "overhead": body.overhead, "hargaJual": body.hargaJual,
        "components": [{"nama": c.nama, "harga": c.harga} for c in comps],
    }


@app.put("/api/prices/{price_id}")
def update_price(price_id: int, body: PriceIn) -> dict:
    comps = [c for c in body.components if c.nama.strip()]
    with get_conn() as conn:
        conn.execute(
            "UPDATE prices SET produk_id=?,overhead=?,harga_jual=? WHERE id=?",
            (body.produkId, body.overhead, body.hargaJual, price_id),
        )
        conn.execute("DELETE FROM price_components WHERE price_id=?", (price_id,))
        for c in comps:
            conn.execute(
                "INSERT INTO price_components (price_id,nama,harga) VALUES (?,?,?)",
                (price_id, c.nama, c.harga),
            )
        conn.commit()
    return {
        "id": price_id, "produkId": body.produkId,
        "overhead": body.overhead, "hargaJual": body.hargaJual,
        "components": [{"nama": c.nama, "harga": c.harga} for c in comps],
    }


@app.delete("/api/prices/{price_id}")
def delete_price(price_id: int) -> dict:
    with get_conn() as conn:
        conn.execute("DELETE FROM prices WHERE id=?", (price_id,))
        conn.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# ORDERS
# ═══════════════════════════════════════════════════════════

@app.get("/api/orders")
def get_orders() -> list[dict]:
    with get_conn() as conn:
        orders = conn.execute("SELECT * FROM orders ORDER BY date DESC").fetchall()
        result = []
        for o in orders:
            items = conn.execute(
                "SELECT * FROM order_items WHERE order_id=?", (o["id"],)
            ).fetchall()
            result.append({
                "id":       o["id"],
                "customer": o["customer"],
                "date":     o["date"],
                "dateStr":  o["date_str"],
                "subtotal": o["subtotal"],
                "discount": o["discount"],
                "total":    o["total"],
                "note":     o["note"],
                "items": [
                    {
                        "priceId":  it["price_id"],
                        "nama":     it["nama"],
                        "harga":    it["harga"],
                        "qty":      it["qty"],
                        "subtotal": it["subtotal"],
                    }
                    for it in items
                ],
            })
    return result


@app.post("/api/orders", status_code=status.HTTP_201_CREATED)
def create_order(body: OrderIn) -> dict:
    if not body.id or not body.items:
        raise HTTPException(400, "Order tidak valid")

    date_str = body.dateStr or _fmt_date_from_iso(body.date)
    cf_id    = f"CF-{int(time.time() * 1000)}"
    customer = body.customer or "Umum"

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO orders (id,customer,date,date_str,subtotal,discount,total,note) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (body.id, customer, body.date, date_str,
             body.subtotal, body.discount, body.total, body.note),
        )
        for it in body.items:
            conn.execute(
                "INSERT INTO order_items (order_id,price_id,nama,harga,qty,subtotal) "
                "VALUES (?,?,?,?,?,?)",
                (body.id, it.priceId, it.nama, it.harga, it.qty, it.subtotal),
            )
        # Auto-catat cashflow pemasukan
        conn.execute(
            "INSERT INTO cashflows (id,type,date,date_str,desc_text,category,amount) "
            "VALUES (?,?,?,?,?,?,?)",
            (cf_id, "in", body.date, date_str,
             f"Penjualan - {customer}", "Penjualan", body.total),
        )
        conn.commit()
    return {"ok": True, "id": body.id}


@app.delete("/api/orders/{order_id}")
def delete_order(order_id: str) -> dict:
    with get_conn() as conn:
        conn.execute("DELETE FROM orders WHERE id=?", (order_id,))
        conn.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# CASHFLOW
# ═══════════════════════════════════════════════════════════

@app.get("/api/cashflows")
def get_cashflows() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM cashflows ORDER BY date DESC").fetchall()
    return [
        {
            "id":       r["id"],
            "type":     r["type"],
            "date":     r["date"],
            "dateStr":  r["date_str"],
            "desc":     r["desc_text"],
            "category": r["category"],
            "amount":   r["amount"],
        }
        for r in rows
    ]


@app.post("/api/cashflows", status_code=status.HTTP_201_CREATED)
def create_cashflow(body: CashflowIn) -> dict:
    if not body.desc.strip() or not body.amount:
        raise HTTPException(400, "Data tidak lengkap")

    cf_id    = body.id or f"CF-{int(time.time() * 1000)}"
    date_str = body.dateStr or _fmt_date_from_iso(body.date)

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO cashflows (id,type,date,date_str,desc_text,category,amount) "
            "VALUES (?,?,?,?,?,?,?)",
            (cf_id, body.type, body.date, date_str,
             body.desc, body.category, body.amount),
        )
        conn.commit()
    return {
        "id": cf_id, "type": body.type, "date": body.date,
        "dateStr": date_str, "desc": body.desc,
        "category": body.category, "amount": body.amount,
    }


@app.delete("/api/cashflows/{cashflow_id}")
def delete_cashflow(cashflow_id: str) -> dict:
    with get_conn() as conn:
        conn.execute("DELETE FROM cashflows WHERE id=?", (cashflow_id,))
        conn.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# STATIC FILES — sajikan frontend dari folder public/
# ═══════════════════════════════════════════════════════════

if PUBLIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=PUBLIC_DIR), name="static")

@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str):
    """Semua request non-API diarahkan ke index.html (SPA fallback)."""
    index = PUBLIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse({"detail": "Frontend tidak ditemukan"}, status_code=404)


# ─────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

