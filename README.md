# Layanan Publik Digital (MVP)

Proyek mata kuliah Manajemen Proyek TI, topik 4: pengajuan surat online dan antrean digital.
Teknologi: Python, Django, SQLite.

## Fitur inti
1. Autentikasi: registrasi, login, logout, peran warga dan petugas (`is_staff`)
2. Pengajuan surat online oleh warga (NIK tervalidasi 16 digit) beserta pelacakan status
3. Pengelolaan pengajuan oleh petugas (diproses, selesai, ditolak dengan alasan wajib)
4. Antrean digital: ambil nomor per layanan, nomor reset tiap hari, satu antrean aktif per layanan
5. Panel petugas (panggil berikutnya, selesai) dan layar antrean publik tanpa login
6. Panel admin Django untuk data master (jenis surat, layanan)
7. Dashboard dan menu terpisah untuk warga dan petugas, menu samping (garis 3), halaman muka, dan halaman profil
8. Pencarian dan paginasi pengajuan surat, kode pengajuan (SRT-xxxxx), tahapan status visual

## Struktur
- `config/` pengaturan dan routing proyek
- `layanan/models.py` data (JenisSurat, PengajuanSurat, Layanan, Antrean)
- `layanan/views.py`, `forms.py`, `urls.py` logika aplikasi
- `layanan/templates/` tampilan (`base.html`, partial `_form`, `_status`, `_paging`)
- `layanan/static/layanan/style.css` gaya tampilan
- `layanan/tests.py` pengujian

## Menjalankan
```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations layanan
python manage.py migrate
python manage.py seed_data          # data awal + akun petugas contoh
python manage.py runserver
```
Buka http://127.0.0.1:8000/ . Akun petugas contoh: `petugas` / `petugas12345` (ganti sebelum produksi).

## Pengujian
```bash
python manage.py test
```
Berisi 49 test case (autentikasi, pengajuan surat, hak akses, logika antrean).

## Rencana Git
- Cabang: `main` (stabil), `develop`, `feature/<nama-fitur>` per user story
- Commit kecil dengan pesan deskriptif, merge lewat pull request
