# consignment.py — Fitur Konsinyasi & Rekomendasi Harga untuk BatikCraft
# ─────────────────────────────────────────────────────────────────────────
# Konsinyasi memakai pola header/detail:
#   - 1 "batch" (consignment_batches) = 1 surat jalan/pengiriman ke 1 toko
#   - 1 batch bisa berisi banyak "item" (consignment_items) = banyak produk
#     dengan qty & harga masing-masing berbeda.
#
# Dua fitur utama:
#   1. Konsinyasi  → catat barang titip (multi produk), update terjual, laporan profit
#   2. Rekomendasi → saat harga bahan naik, sarankan harga jual baru
# ─────────────────────────────────────────────────────────────────────────

import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database import get_conn, fmt_date_id

router = APIRouter(prefix="/api", tags=["konsinyasi"])


# ════════════════════════════════════════════════════════════
# SCHEMAS
# ════════════════════════════════════════════════════════════

class ConsignmentItemIn(BaseModel):
    produkId:   int
    namaProduk: str
    qtyTitip:   int   = 0      # jumlah unit dititipkan
    hargaJual:  float = 0      # harga jual ke konsinyee
    hargaModal: float = 0      # HPP / modal per unit


class ConsignmentIn(BaseModel):
    tempat:       str                          # nama toko/konsinyee
    tanggalMulai: str                          # ISO date string
    durasibulan:  int  = 3                     # 1, 2, atau 3 bulan
    komisiPersen: float = 0                    # % komisi toko, berlaku utk seluruh batch
    catatan:      str  = ""
    items:        list[ConsignmentItemIn] = Field(default_factory=list)


class UpdateSoldItemIn(BaseModel):
    itemId:     int
    qtyTerjual: int = 0
    qtyKembali: int = 0


class UpdateSoldIn(BaseModel):
    items: list[UpdateSoldItemIn] = Field(default_factory=list)


class PriceRecIn(BaseModel):
    materialId:    int           # ID bahan yang naik harganya
    hargaBaruPerSatuan: float    # harga satuan baru
    targetMargin:  float = 30.0  # margin keuntungan yang diinginkan (%)


# ════════════════════════════════════════════════════════════
# HELPER
# ════════════════════════════════════════════════════════════

def _fmt(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return fmt_date_id(dt)
    except Exception:
        return iso


def _item_to_dict(r) -> dict:
    return {
        "id":         r["id"],
        "produkId":   r["produk_id"],
        "namaProduk": r["nama_produk"],
        "qtyTitip":   r["qty_titip"],
        "qtyTerjual": r["qty_terjual"],
        "qtyKembali": r["qty_kembali"],
        "hargaJual":  r["harga_jual"],
        "hargaModal": r["harga_modal"],
    }


def _item_profit(item: dict, komisi_persen: float) -> dict:
    """Hitung profit untuk 1 item (1 produk di dalam batch)."""
    terjual = item["qtyTerjual"]
    modal_u = item["hargaModal"]
    jual_u  = item["hargaJual"]
    komisi  = komisi_persen / 100

    pendapatan_kotor  = terjual * jual_u
    komisi_nominal    = pendapatan_kotor * komisi
    pendapatan_bersih = pendapatan_kotor - komisi_nominal
    modal_terpakai    = terjual * modal_u
    profit            = pendapatan_bersih - modal_terpakai
    sisa              = item["qtyTitip"] - terjual - item["qtyKembali"]
    nilai_sisa        = sisa * modal_u

    return {
        "itemId":            item["id"],
        "produkId":          item["produkId"],
        "namaProduk":        item["namaProduk"],
        "qtyTitip":          item["qtyTitip"],
        "qtyTerjual":        terjual,
        "qtyKembali":        item["qtyKembali"],
        "qtySisaDitangan":   max(0, sisa),
        "pendapatanKotor":   round(pendapatan_kotor, 2),
        "komisiNominal":     round(komisi_nominal, 2),
        "pendapatanBersih":  round(pendapatan_bersih, 2),
        "modalTerpakai":     round(modal_terpakai, 2),
        "profit":            round(profit, 2),
        "nilaiSisaDitangan": round(nilai_sisa, 2),
        "statusProfit":      "untung" if profit > 0 else ("impas" if profit == 0 else "rugi"),
    }


def _agregasi_profit(item_profits: list[dict]) -> dict:
    """Jumlahkan profit semua item dalam 1 batch jadi 1 ringkasan."""
    agg = {
        "qtyTitip": 0, "qtyTerjual": 0, "qtyKembali": 0, "qtySisaDitangan": 0,
        "pendapatanKotor": 0.0, "komisiNominal": 0.0, "pendapatanBersih": 0.0,
        "modalTerpakai": 0.0, "profit": 0.0, "nilaiSisaDitangan": 0.0,
    }
    for p in item_profits:
        for k in agg:
            agg[k] += p[k]
    for k in ["pendapatanKotor", "komisiNominal", "pendapatanBersih",
              "modalTerpakai", "profit", "nilaiSisaDitangan"]:
        agg[k] = round(agg[k], 2)
    agg["statusProfit"] = "untung" if agg["profit"] > 0 else ("impas" if agg["profit"] == 0 else "rugi")
    return agg


def _proyeksi_item(item: dict, komisi_persen: float, tanggal_mulai: str) -> list[dict]:
    """Proyeksi profit 1, 2, 3 bulan untuk 1 item, berdasar laju penjualan."""
    terjual = item["qtyTerjual"]
    titip   = item["qtyTitip"]
    jual_u  = item["hargaJual"]
    modal_u = item["hargaModal"]
    komisi  = komisi_persen / 100

    try:
        mulai = datetime.fromisoformat(tanggal_mulai)
        bulan_berjalan = max(1, ((datetime.now() - mulai).days // 30) or 1)
    except Exception:
        bulan_berjalan = 1

    laju = terjual / bulan_berjalan if terjual > 0 else titip * 0.30

    hasil = []
    for bln in [1, 2, 3]:
        qty_proyeksi = min(titip, round(laju * bln))
        pend_k  = qty_proyeksi * jual_u
        komisi_ = pend_k * komisi
        pend_b  = pend_k - komisi_
        modal_  = qty_proyeksi * modal_u
        profit_ = pend_b - modal_

        hasil.append({
            "bulan":              bln,
            "qtyProyeksiTerjual": qty_proyeksi,
            "pendapatanBersih":   round(pend_b, 2),
            "modalTerpakai":      round(modal_, 2),
            "profit":             round(profit_, 2),
            "statusProfit":       "untung" if profit_ > 0 else ("impas" if profit_ == 0 else "rugi"),
        })
    return hasil


def _proyeksi_agregasi(items: list[dict], komisi_persen: float, tanggal_mulai: str) -> list[dict]:
    """Jumlahkan proyeksi semua item per periode (1/2/3 bulan)."""
    per_item = [_proyeksi_item(it, komisi_persen, tanggal_mulai) for it in items]
    hasil = []
    for idx, bln in enumerate([1, 2, 3]):
        agg = {"bulan": bln, "qtyProyeksiTerjual": 0, "pendapatanBersih": 0.0,
               "modalTerpakai": 0.0, "profit": 0.0}
        for proj in per_item:
            row = proj[idx]
            agg["qtyProyeksiTerjual"] += row["qtyProyeksiTerjual"]
            agg["pendapatanBersih"]   += row["pendapatanBersih"]
            agg["modalTerpakai"]      += row["modalTerpakai"]
            agg["profit"]             += row["profit"]
        agg["pendapatanBersih"] = round(agg["pendapatanBersih"], 2)
        agg["modalTerpakai"]    = round(agg["modalTerpakai"], 2)
        agg["profit"]           = round(agg["profit"], 2)
        agg["statusProfit"] = "untung" if agg["profit"] > 0 else ("impas" if agg["profit"] == 0 else "rugi")
        hasil.append(agg)
    return hasil


def _get_batch_with_items(conn, batch_id: str):
    b = conn.execute(
        "SELECT * FROM consignment_batches WHERE id=?", (batch_id,)
    ).fetchone()
    if not b:
        return None, []
    items = conn.execute(
        "SELECT * FROM consignment_items WHERE batch_id=? ORDER BY id",
        (batch_id,)
    ).fetchall()
    return b, [_item_to_dict(i) for i in items]


def _batch_to_dict(b, items: list[dict]) -> dict:
    profits = [_item_profit(it, b["komisi_persen"]) for it in items]
    agg = _agregasi_profit(profits)
    return {
        "id":           b["id"],
        "tempat":       b["tempat"],
        "tanggalMulai": b["tanggal_mulai"],
        "tanggalStr":   b["tanggal_str"],
        "durasibulan":  b["durasi_bulan"],
        "komisiPersen": b["komisi_persen"],
        "status":       b["status"],
        "catatan":      b["catatan"],
        "items":        items,
        "jumlahProduk": len(items),
        "qtyTitip":     agg["qtyTitip"],
        "qtyTerjual":   agg["qtyTerjual"],
        "qtyKembali":   agg["qtyKembali"],
        "qtySisa":      agg["qtySisaDitangan"],
        "profit":       agg["profit"],
        "statusProfit": agg["statusProfit"],
    }


# ════════════════════════════════════════════════════════════
# ENDPOINTS — KONSINYASI
# ════════════════════════════════════════════════════════════

@router.get("/consignments")
def get_consignments(status: Optional[str] = None) -> list[dict]:
    """List semua batch konsinyasi (tiap batch bisa berisi banyak produk)."""
    with get_conn() as conn:
        if status:
            batches = conn.execute(
                "SELECT * FROM consignment_batches WHERE status=? ORDER BY tanggal_mulai DESC",
                (status,)
            ).fetchall()
        else:
            batches = conn.execute(
                "SELECT * FROM consignment_batches ORDER BY tanggal_mulai DESC"
            ).fetchall()

        hasil = []
        for b in batches:
            items = conn.execute(
                "SELECT * FROM consignment_items WHERE batch_id=? ORDER BY id",
                (b["id"],)
            ).fetchall()
            hasil.append(_batch_to_dict(b, [_item_to_dict(i) for i in items]))
    return hasil


@router.get("/consignments/{batch_id}")
def get_consignment(batch_id: str) -> dict:
    """Detail 1 batch konsinyasi beserta semua produk di dalamnya."""
    with get_conn() as conn:
        b, items = _get_batch_with_items(conn, batch_id)
    if not b:
        raise HTTPException(404, "Konsinyasi tidak ditemukan")
    return _batch_to_dict(b, items)


@router.get("/consignments/{batch_id}/report")
def consignment_report(batch_id: str) -> dict:
    """
    Laporan lengkap 1 batch konsinyasi:
    - Ringkasan aktual per produk + agregat keseluruhan batch
    - Proyeksi profit untuk 1, 2, 3 bulan ke depan (per produk + agregat)
    """
    with get_conn() as conn:
        b, items = _get_batch_with_items(conn, batch_id)
    if not b:
        raise HTTPException(404, "Konsinyasi tidak ditemukan")

    komisi = b["komisi_persen"]
    item_profits = [_item_profit(it, komisi) for it in items]

    return {
        "info":          _batch_to_dict(b, items),
        "aktualPerItem": item_profits,
        "aktual":        _agregasi_profit(item_profits),
        "proyeksi":      _proyeksi_agregasi(items, komisi, b["tanggal_mulai"]),
    }


@router.post("/consignments", status_code=201)
def create_consignment(body: ConsignmentIn) -> dict:
    """Catat konsinyasi baru — bisa berisi banyak produk sekaligus dalam 1 surat jalan."""
    if not body.tempat.strip():
        raise HTTPException(400, "Nama tempat wajib diisi")
    if not body.items:
        raise HTTPException(400, "Minimal 1 produk harus ditambahkan")

    for it in body.items:
        if not it.namaProduk.strip():
            raise HTTPException(400, "Nama produk wajib diisi untuk setiap baris")
        if it.qtyTitip <= 0:
            raise HTTPException(400, f"Qty titip untuk '{it.namaProduk}' harus lebih dari 0")
        if it.hargaJual < it.hargaModal:
            raise HTTPException(400, f"Harga jual '{it.namaProduk}' tidak boleh lebih kecil dari modal")

    bid     = f"KS-{int(time.time() * 1000)}"
    tgl_str = _fmt(body.tanggalMulai)

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO consignment_batches
               (id, tempat, tanggal_mulai, tanggal_str, durasi_bulan,
                komisi_persen, status, catatan)
               VALUES (?,?,?,?,?,?,?,?)""",
            (bid, body.tempat, body.tanggalMulai, tgl_str, body.durasibulan,
             body.komisiPersen, "aktif", body.catatan),
        )
        for it in body.items:
            conn.execute(
                """INSERT INTO consignment_items
                   (batch_id, produk_id, nama_produk, qty_titip,
                    qty_terjual, qty_kembali, harga_jual, harga_modal)
                   VALUES (?,?,?,?,0,0,?,?)""",
                (bid, it.produkId, it.namaProduk, it.qtyTitip,
                 it.hargaJual, it.hargaModal),
            )
        conn.commit()

    return {"ok": True, "id": bid}


@router.put("/consignments/{batch_id}/update-sold")
def update_consignment_sold(batch_id: str, body: UpdateSoldIn) -> dict:
    """
    Update qty terjual & qty kembali untuk 1 atau lebih produk dalam batch.
    Batch otomatis jadi 'selesai' kalau SEMUA produk sudah (terjual+kembali >= titip).
    """
    with get_conn() as conn:
        b, items = _get_batch_with_items(conn, batch_id)
        if not b:
            raise HTTPException(404, "Konsinyasi tidak ditemukan")

        items_by_id = {it["id"]: it for it in items}

        for upd in body.items:
            item = items_by_id.get(upd.itemId)
            if not item:
                raise HTTPException(404, f"Item konsinyasi #{upd.itemId} tidak ditemukan di batch ini")
            if upd.qtyTerjual + upd.qtyKembali > item["qtyTitip"]:
                raise HTTPException(
                    400,
                    f"'{item['namaProduk']}': total terjual+kembali "
                    f"({upd.qtyTerjual + upd.qtyKembali}) melebihi qty titip ({item['qtyTitip']})"
                )
            conn.execute(
                "UPDATE consignment_items SET qty_terjual=?, qty_kembali=? WHERE id=?",
                (upd.qtyTerjual, upd.qtyKembali, upd.itemId),
            )
            item["qtyTerjual"] = upd.qtyTerjual
            item["qtyKembali"] = upd.qtyKembali

        semua_selesai = all(
            it["qtyTerjual"] + it["qtyKembali"] >= it["qtyTitip"] for it in items_by_id.values()
        )
        new_status = "selesai" if semua_selesai else "aktif"
        conn.execute(
            "UPDATE consignment_batches SET status=? WHERE id=?",
            (new_status, batch_id),
        )
        conn.commit()

        b2, items2 = _get_batch_with_items(conn, batch_id)

    return {
        "ok":     True,
        "status": new_status,
        "aktual": _agregasi_profit([_item_profit(it, b2["komisi_persen"]) for it in items2]),
    }


@router.put("/consignments/{batch_id}/selesai")
def mark_consignment_done(batch_id: str) -> dict:
    """Tandai batch konsinyasi sebagai selesai secara manual."""
    with get_conn() as conn:
        r = conn.execute(
            "SELECT id FROM consignment_batches WHERE id=?", (batch_id,)
        ).fetchone()
        if not r:
            raise HTTPException(404, "Konsinyasi tidak ditemukan")
        conn.execute(
            "UPDATE consignment_batches SET status='selesai' WHERE id=?",
            (batch_id,),
        )
        conn.commit()
    return {"ok": True}


@router.delete("/consignments/{batch_id}")
def delete_consignment(batch_id: str) -> dict:
    """Hapus batch konsinyasi beserta semua produk di dalamnya."""
    with get_conn() as conn:
        conn.execute("DELETE FROM consignment_batches WHERE id=?", (batch_id,))
        conn.commit()
    return {"ok": True}


# ════════════════════════════════════════════════════════════
# ENDPOINTS — REKOMENDASI HARGA
# ════════════════════════════════════════════════════════════

@router.post("/price-recommendation")
def price_recommendation(body: PriceRecIn) -> dict:
    """
    Saat harga bahan baku dari supplier naik, endpoint ini:
    1. Ambil harga lama bahan
    2. Hitung kenaikan % dan nominal
    3. Cari semua produk yang komponen harganya mengandung nama bahan ini
    4. Hitung ulang HPP baru per produk
    5. Rekomendasikan harga jual baru berdasarkan target margin
    """
    with get_conn() as conn:
        mat = conn.execute(
            "SELECT id, nama, harga_satuan, satuan FROM materials WHERE id=?",
            (body.materialId,)
        ).fetchone()
        if not mat:
            raise HTTPException(404, "Bahan tidak ditemukan")

        harga_lama = mat["harga_satuan"]
        harga_baru = body.hargaBaruPerSatuan
        if harga_baru <= 0:
            raise HTTPException(400, "Harga baru harus lebih dari 0")

        naik_nominal = harga_baru - harga_lama
        naik_persen  = round((naik_nominal / harga_lama * 100), 2) if harga_lama > 0 else 0

        nama_bahan = mat["nama"].lower()
        all_comps  = conn.execute(
            "SELECT pc.id, pc.price_id, pc.nama, pc.harga "
            "FROM price_components pc"
        ).fetchall()

        matched_comp_ids = [
            c for c in all_comps
            if nama_bahan in c["nama"].lower() or c["nama"].lower() in nama_bahan
        ]

        hasil_rekomendasi = []

        for comp in matched_comp_ids:
            price_id = comp["price_id"]

            price_row = conn.execute(
                "SELECT p.id, p.produk_id, p.overhead, p.harga_jual, pr.nama as nama_produk "
                "FROM prices p "
                "JOIN products pr ON pr.id = p.produk_id "
                "WHERE p.id=?",
                (price_id,)
            ).fetchone()
            if not price_row:
                continue

            semua_comp = conn.execute(
                "SELECT nama, harga FROM price_components WHERE price_id=?",
                (price_id,)
            ).fetchall()

            hpp_lama = sum(c["harga"] for c in semua_comp) + price_row["overhead"]

            selisih_comp = naik_nominal
            hpp_baru     = hpp_lama + selisih_comp

            margin_frac = body.targetMargin / 100
            harga_rec   = round(hpp_baru / (1 - margin_frac), 0) if margin_frac < 1 else hpp_baru * 2

            hj_lama     = price_row["harga_jual"]
            margin_lama = round((hj_lama - hpp_lama) / hj_lama * 100, 1) if hj_lama > 0 else 0
            margin_baru = round((harga_rec - hpp_baru) / harga_rec * 100, 1) if harga_rec > 0 else 0

            hasil_rekomendasi.append({
                "priceId":          price_id,
                "produkId":         price_row["produk_id"],
                "namaProduk":       price_row["nama_produk"],
                "komponenTerdampak": comp["nama"],
                "hppLama":          round(hpp_lama, 2),
                "hppBaru":          round(hpp_baru, 2),
                "hargaJualLama":    round(hj_lama, 2),
                "hargaJualRekomen": harga_rec,
                "selisihHarga":     round(harga_rec - hj_lama, 2),
                "marginLama":       margin_lama,
                "marginBaru":       margin_baru,
            })

    return {
        "material": {
            "id":          mat["id"],
            "nama":        mat["nama"],
            "satuan":      mat["satuan"],
            "hargaLama":   harga_lama,
            "hargaBaru":   harga_baru,
            "naikNominal": round(naik_nominal, 2),
            "naikPersen":  naik_persen,
        },
        "targetMarginPersen": body.targetMargin,
        "rekomendasi":        hasil_rekomendasi,
        "pesanJikaKosong":    (
            "Tidak ada produk terdampak langsung. "
            "Pastikan nama bahan di price_components mengandung kata yang sama dengan nama bahan ini."
        ) if not hasil_rekomendasi else None,
    }
