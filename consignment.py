# consignment.py — Fitur Konsinyasi & Rekomendasi Harga untuk BatikCraft
# ─────────────────────────────────────────────────────────────────────────
# Dua fitur utama:
#   1. Konsinyasi  → catat barang titip, update terjual, laporan profit
#   2. Rekomendasi → saat harga bahan naik, sarankan harga jual baru
# ─────────────────────────────────────────────────────────────────────────

import time
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_conn, fmt_date_id

router = APIRouter(prefix="/api", tags=["konsinyasi"])


# ════════════════════════════════════════════════════════════
# SCHEMAS
# ════════════════════════════════════════════════════════════

class ConsignmentIn(BaseModel):
    produkId:     int
    namaProduk:   str
    tempat:       str           # nama toko/konsinyee
    tanggalMulai: str           # ISO date string
    durasibulan:  int  = 3      # 1, 2, atau 3 bulan
    qtyTitip:     int  = 0      # jumlah unit dititipkan
    hargaJual:    float = 0     # harga jual ke konsinyee
    hargaModal:   float = 0     # HPP / modal per unit
    komisiPersen: float = 0     # % komisi untuk toko (misal 20 = 20%)
    catatan:      str  = ""


class UpdateSoldIn(BaseModel):
    qtyTerjual:  int   = 0
    qtyKembali:  int   = 0


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


def _hitung_profit(row: dict) -> dict:
    """
    Hitung summary profit untuk konsinyasi.
    - Pendapatan bersih = qty_terjual × harga_jual × (1 - komisi/100)
    - Modal terpakai    = qty_terjual × harga_modal
    - Profit            = pendapatan_bersih - modal_terpakai
    - Sisa di tangan    = qty_titip - qty_terjual - qty_kembali
    """
    terjual   = row["qty_terjual"]
    modal_u   = row["harga_modal"]
    jual_u    = row["harga_jual"]
    komisi    = row["komisi_persen"] / 100

    pendapatan_kotor  = terjual * jual_u
    komisi_nominal    = pendapatan_kotor * komisi
    pendapatan_bersih = pendapatan_kotor - komisi_nominal
    modal_terpakai    = terjual * modal_u
    profit            = pendapatan_bersih - modal_terpakai
    sisa              = row["qty_titip"] - terjual - row["qty_kembali"]
    nilai_sisa        = sisa * modal_u  # nilai modal yang masih "mengendap"

    return {
        "qtyTitip":          row["qty_titip"],
        "qtyTerjual":        terjual,
        "qtyKembali":        row["qty_kembali"],
        "qtySisaDitangan":   max(0, sisa),
        "pendapatanKotor":   round(pendapatan_kotor, 2),
        "komisiNominal":     round(komisi_nominal, 2),
        "pendapatanBersih":  round(pendapatan_bersih, 2),
        "modalTerpakai":     round(modal_terpakai, 2),
        "profit":            round(profit, 2),
        "nilaiSisaDitangan": round(nilai_sisa, 2),
        "statusProfit":      "untung" if profit > 0 else ("impas" if profit == 0 else "rugi"),
    }


def _hitung_proyeksi(row: dict) -> list[dict]:
    """
    Proyeksi profit untuk 1, 2, 3 bulan berdasarkan rata-rata laju penjualan.
    Jika konsinyasi masih baru (0 terjual), gunakan asumsi 30% terjual/bulan.
    """
    terjual  = row["qty_terjual"]
    titip    = row["qty_titip"]
    jual_u   = row["harga_jual"]
    modal_u  = row["harga_modal"]
    komisi   = row["komisi_persen"] / 100

    # Hitung sudah berapa bulan berjalan
    try:
        mulai = datetime.fromisoformat(row["tanggal_mulai"])
        bulan_berjalan = max(1, ((datetime.now() - mulai).days // 30) or 1)
    except Exception:
        bulan_berjalan = 1

    # Laju penjualan per bulan (unit)
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


def _row_to_dict(r) -> dict:
    return {
        "id":           r["id"],
        "produkId":     r["produk_id"],
        "namaProduk":   r["nama_produk"],
        "tempat":       r["tempat"],
        "tanggalMulai": r["tanggal_mulai"],
        "tanggalStr":   r["tanggal_str"],
        "durasibulan":  r["durasi_bulan"],
        "qtyTitip":     r["qty_titip"],
        "qtyTerjual":   r["qty_terjual"],
        "qtyKembali":   r["qty_kembali"],
        "hargaJual":    r["harga_jual"],
        "hargaModal":   r["harga_modal"],
        "komisiPersen": r["komisi_persen"],
        "status":       r["status"],
        "catatan":      r["catatan"],
    }


# ════════════════════════════════════════════════════════════
# ENDPOINTS — KONSINYASI
# ════════════════════════════════════════════════════════════

@router.get("/consignments")
def get_consignments(status: Optional[str] = None) -> list[dict]:
    """List semua konsinyasi. Filter opsional: ?status=aktif atau ?status=selesai"""
    with get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM consignments WHERE status=? ORDER BY tanggal_mulai DESC",
                (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM consignments ORDER BY tanggal_mulai DESC"
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


@router.get("/consignments/{consignment_id}")
def get_consignment(consignment_id: str) -> dict:
    """Detail satu konsinyasi."""
    with get_conn() as conn:
        r = conn.execute(
            "SELECT * FROM consignments WHERE id=?", (consignment_id,)
        ).fetchone()
    if not r:
        raise HTTPException(404, "Konsinyasi tidak ditemukan")
    return _row_to_dict(r)


@router.get("/consignments/{consignment_id}/report")
def consignment_report(consignment_id: str) -> dict:
    """
    Laporan lengkap konsinyasi:
    - Ringkasan aktual (sudah terjual berapa, profit nyata)
    - Proyeksi profit untuk 1, 2, 3 bulan ke depan
    """
    with get_conn() as conn:
        r = conn.execute(
            "SELECT * FROM consignments WHERE id=?", (consignment_id,)
        ).fetchone()
    if not r:
        raise HTTPException(404, "Konsinyasi tidak ditemukan")

    row = dict(r)
    return {
        "info":      _row_to_dict(r),
        "aktual":    _hitung_profit(row),
        "proyeksi":  _hitung_proyeksi(row),
    }


@router.post("/consignments", status_code=201)
def create_consignment(body: ConsignmentIn) -> dict:
    """Catat konsinyasi baru."""
    if not body.namaProduk.strip() or not body.tempat.strip():
        raise HTTPException(400, "Nama produk dan tempat wajib diisi")
    if body.qtyTitip <= 0:
        raise HTTPException(400, "Qty titip harus lebih dari 0")
    if body.hargaJual < body.hargaModal:
        raise HTTPException(400, "Harga jual tidak boleh lebih kecil dari modal")

    cid      = f"KS-{int(time.time() * 1000)}"
    tgl_str  = _fmt(body.tanggalMulai)

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO consignments
               (id, produk_id, nama_produk, tempat,
                tanggal_mulai, tanggal_str, durasi_bulan,
                qty_titip, qty_terjual, qty_kembali,
                harga_jual, harga_modal, komisi_persen, status, catatan)
               VALUES (?,?,?,?,?,?,?,?,0,0,?,?,?,?,?)""",
            (cid, body.produkId, body.namaProduk, body.tempat,
             body.tanggalMulai, tgl_str, body.durasibulan,
             body.qtyTitip, body.hargaJual, body.hargaModal,
             body.komisiPersen, "aktif", body.catatan),
        )
        conn.commit()

    return {"ok": True, "id": cid}


@router.put("/consignments/{consignment_id}/update-sold")
def update_consignment_sold(consignment_id: str, body: UpdateSoldIn) -> dict:
    """
    Update qty terjual dan qty kembali.
    Jika (terjual + kembali) >= titip → status otomatis jadi 'selesai'.
    """
    with get_conn() as conn:
        r = conn.execute(
            "SELECT * FROM consignments WHERE id=?", (consignment_id,)
        ).fetchone()
        if not r:
            raise HTTPException(404, "Konsinyasi tidak ditemukan")

        titip   = r["qty_titip"]
        terjual = body.qtyTerjual
        kembali = body.qtyKembali

        if terjual + kembali > titip:
            raise HTTPException(400, f"Total terjual+kembali ({terjual+kembali}) melebihi qty titip ({titip})")

        new_status = "selesai" if (terjual + kembali >= titip) else "aktif"

        conn.execute(
            "UPDATE consignments SET qty_terjual=?, qty_kembali=?, status=? WHERE id=?",
            (terjual, kembali, new_status, consignment_id),
        )
        conn.commit()

        updated = conn.execute(
            "SELECT * FROM consignments WHERE id=?", (consignment_id,)
        ).fetchone()

    return {
        "ok":     True,
        "status": new_status,
        "aktual": _hitung_profit(dict(updated)),
    }


@router.put("/consignments/{consignment_id}/selesai")
def mark_consignment_done(consignment_id: str) -> dict:
    """Tandai konsinyasi sebagai selesai secara manual."""
    with get_conn() as conn:
        r = conn.execute(
            "SELECT id FROM consignments WHERE id=?", (consignment_id,)
        ).fetchone()
        if not r:
            raise HTTPException(404, "Konsinyasi tidak ditemukan")
        conn.execute(
            "UPDATE consignments SET status='selesai' WHERE id=?",
            (consignment_id,),
        )
        conn.commit()
    return {"ok": True}


@router.delete("/consignments/{consignment_id}")
def delete_consignment(consignment_id: str) -> dict:
    """Hapus konsinyasi."""
    with get_conn() as conn:
        conn.execute("DELETE FROM consignments WHERE id=?", (consignment_id,))
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
        # ── Ambil data bahan ──────────────────────────────
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

        # ── Cari price_components yang nama-nya mengandung nama bahan ─
        nama_bahan = mat["nama"].lower()
        all_comps  = conn.execute(
            "SELECT pc.id, pc.price_id, pc.nama, pc.harga "
            "FROM price_components pc"
        ).fetchall()

        # Filter komponen yang cocok (case-insensitive partial match)
        matched_comp_ids = [
            c for c in all_comps
            if nama_bahan in c["nama"].lower() or c["nama"].lower() in nama_bahan
        ]

        hasil_rekomendasi = []

        for comp in matched_comp_ids:
            price_id = comp["price_id"]

            # Ambil price record
            price_row = conn.execute(
                "SELECT p.id, p.produk_id, p.overhead, p.harga_jual, pr.nama as nama_produk "
                "FROM prices p "
                "JOIN products pr ON pr.id = p.produk_id "
                "WHERE p.id=?",
                (price_id,)
            ).fetchone()
            if not price_row:
                continue

            # Ambil semua komponen untuk price ini → hitung total HPP lama
            semua_comp = conn.execute(
                "SELECT nama, harga FROM price_components WHERE price_id=?",
                (price_id,)
            ).fetchall()

            hpp_lama   = sum(c["harga"] for c in semua_comp) + price_row["overhead"]

            # Hitung HPP baru: komponen yg cocok naik proporsional
            selisih_comp = naik_nominal  # asumsi 1 satuan bahan per komponen
            hpp_baru     = hpp_lama + selisih_comp

            # Harga jual rekomendasi = HPP baru / (1 - margin%)
            margin_frac  = body.targetMargin / 100
            harga_rec    = round(hpp_baru / (1 - margin_frac), 0) if margin_frac < 1 else hpp_baru * 2

            # Margin yang sedang berjalan saat ini
            hj_lama      = price_row["harga_jual"]
            margin_lama  = round((hj_lama - hpp_lama) / hj_lama * 100, 1) if hj_lama > 0 else 0
            margin_baru  = round((harga_rec - hpp_baru) / harga_rec * 100, 1) if harga_rec > 0 else 0

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
