from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import PengajuanForm, StatusForm
from .models import Antrean, AntreanAktifError, JenisSurat, Layanan, PengajuanSurat

NIK = "3201010101010001"


class DasarTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.warga = User.objects.create_user("warga", "w@example.com", "rahasia12345")
        cls.warga2 = User.objects.create_user("warga2", "w2@example.com", "rahasia12345")
        cls.petugas = User.objects.create_user("petugas", "p@example.com", "rahasia12345", is_staff=True)
        cls.jenis = JenisSurat.objects.create(nama="Surat Domisili")
        cls.layanan = Layanan.objects.create(nama="Umum", kode="A")
        cls.layanan_b = Layanan.objects.create(nama="Kependudukan", kode="B")

    def buat_surat(self, pemohon=None, **kw):
        return PengajuanSurat.objects.create(
            pemohon=pemohon or self.warga, jenis=self.jenis, nik=NIK, keperluan="Melamar kerja", **kw
        )


class AutentikasiTests(DasarTestCase):
    def test_01_register_berhasil_dan_login_otomatis(self):
        r = self.client.post(
            reverse("layanan:register"),
            {"username": "baru", "email": "b@example.com", "password1": "KataSandi!2026x", "password2": "KataSandi!2026x"},
        )
        self.assertRedirects(r, reverse("layanan:beranda"))
        self.assertTrue(User.objects.filter(username="baru").exists())
        self.assertIn("_auth_user_id", self.client.session)

    def test_02_register_password_tidak_sama_gagal(self):
        r = self.client.post(
            reverse("layanan:register"),
            {"username": "baru", "email": "b@example.com", "password1": "KataSandi!2026x", "password2": "lain"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="baru").exists())

    def test_03_login_berhasil(self):
        r = self.client.post(reverse("login"), {"username": "warga", "password": "rahasia12345"})
        self.assertRedirects(r, reverse("layanan:beranda"))

    def test_04_halaman_surat_wajib_login(self):
        r = self.client.get(reverse("layanan:surat_daftar"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r.url)


class SuratTests(DasarTestCase):
    def test_05_warga_membuat_pengajuan(self):
        self.client.force_login(self.warga)
        r = self.client.post(
            reverse("layanan:surat_buat"), {"jenis": self.jenis.pk, "nik": NIK, "keperluan": "Melamar kerja"}
        )
        p = PengajuanSurat.objects.get()
        self.assertRedirects(r, reverse("layanan:surat_detail", args=[p.pk]))
        self.assertEqual(p.pemohon, self.warga)
        self.assertEqual(p.status, PengajuanSurat.Status.DIAJUKAN)

    def test_06_nik_harus_16_digit(self):
        form = PengajuanForm({"jenis": self.jenis.pk, "nik": "123", "keperluan": "x"})
        self.assertFalse(form.is_valid())
        self.assertIn("nik", form.errors)

    def test_07_nik_tidak_boleh_huruf(self):
        form = PengajuanForm({"jenis": self.jenis.pk, "nik": "abcdefghijklmnop", "keperluan": "x"})
        self.assertFalse(form.is_valid())

    def test_08_jenis_nonaktif_tidak_bisa_dipilih(self):
        nonaktif = JenisSurat.objects.create(nama="Lama", aktif=False)
        form = PengajuanForm({"jenis": nonaktif.pk, "nik": NIK, "keperluan": "x"})
        self.assertFalse(form.is_valid())

    def test_09_warga_hanya_melihat_surat_sendiri(self):
        self.buat_surat(self.warga)
        self.buat_surat(self.warga2)
        self.client.force_login(self.warga)
        r = self.client.get(reverse("layanan:surat_daftar"))
        self.assertEqual(len(r.context["daftar"]), 1)

    def test_10_warga_tidak_bisa_lihat_detail_surat_orang_lain(self):
        p = self.buat_surat(self.warga2)
        self.client.force_login(self.warga)
        self.assertEqual(self.client.get(reverse("layanan:surat_detail", args=[p.pk])).status_code, 403)

    def test_11_petugas_bisa_lihat_detail_surat_siapa_pun(self):
        p = self.buat_surat(self.warga)
        self.client.force_login(self.petugas)
        self.assertEqual(self.client.get(reverse("layanan:surat_detail", args=[p.pk])).status_code, 200)

    def test_12_warga_tidak_bisa_akses_kelola_surat(self):
        self.client.force_login(self.warga)
        self.assertEqual(self.client.get(reverse("layanan:kelola_surat")).status_code, 403)

    def test_13_petugas_mengubah_status_surat(self):
        p = self.buat_surat()
        self.client.force_login(self.petugas)
        r = self.client.post(
            reverse("layanan:kelola_surat_ubah", args=[p.pk]),
            {"status": "selesai", "catatan_petugas": "Silakan ambil di loket"},
        )
        self.assertRedirects(r, reverse("layanan:kelola_surat"))
        p.refresh_from_db()
        self.assertEqual(p.status, PengajuanSurat.Status.SELESAI)

    def test_14_penolakan_wajib_ada_alasan(self):
        p = self.buat_surat()
        form = StatusForm({"status": "ditolak", "catatan_petugas": ""}, instance=p)
        self.assertFalse(form.is_valid())
        self.assertIn("catatan_petugas", form.errors)

    def test_15_filter_status_di_kelola_surat(self):
        self.buat_surat()
        self.buat_surat(status=PengajuanSurat.Status.SELESAI)
        self.client.force_login(self.petugas)
        r = self.client.get(reverse("layanan:kelola_surat"), {"status": "selesai"})
        self.assertEqual(len(r.context["daftar"]), 1)


class AntreanModelTests(DasarTestCase):
    def test_16_nomor_berurutan_per_layanan(self):
        a1 = Antrean.ambil_nomor(self.layanan, self.warga)
        a2 = Antrean.ambil_nomor(self.layanan, self.warga2)
        self.assertEqual((a1.nomor, a2.nomor), (1, 2))

    def test_17_nomor_terpisah_antar_layanan(self):
        Antrean.ambil_nomor(self.layanan, self.warga)
        b = Antrean.ambil_nomor(self.layanan_b, self.warga)
        self.assertEqual(b.nomor, 1)

    def test_18_nomor_reset_tiap_hari(self):
        kemarin = timezone.localdate() - timedelta(days=1)
        Antrean.ambil_nomor(self.layanan, self.warga, tanggal=kemarin)
        hari_ini = Antrean.ambil_nomor(self.layanan, self.warga2)
        self.assertEqual(hari_ini.nomor, 1)

    def test_19_tidak_boleh_punya_dua_antrean_aktif(self):
        Antrean.ambil_nomor(self.layanan, self.warga)
        with self.assertRaises(AntreanAktifError):
            Antrean.ambil_nomor(self.layanan, self.warga)

    def test_20_boleh_ambil_lagi_setelah_selesai(self):
        a = Antrean.ambil_nomor(self.layanan, self.warga)
        a.status = Antrean.Status.SELESAI
        a.save()
        self.assertEqual(Antrean.ambil_nomor(self.layanan, self.warga).nomor, 2)

    def test_21_format_nomor_tampil(self):
        self.assertEqual(Antrean.ambil_nomor(self.layanan, self.warga).nomor_tampil, "A-001")

    def test_22_panggil_berikutnya_urut_nomor(self):
        Antrean.ambil_nomor(self.layanan, self.warga)
        Antrean.ambil_nomor(self.layanan, self.warga2)
        dipanggil = Antrean.panggil_berikutnya(self.layanan)
        self.assertEqual(dipanggil.nomor, 1)
        self.assertEqual(dipanggil.status, Antrean.Status.DIPANGGIL)
        self.assertIsNotNone(dipanggil.dipanggil_pada)

    def test_23_panggil_berikutnya_kosong_mengembalikan_none(self):
        self.assertIsNone(Antrean.panggil_berikutnya(self.layanan))

    def test_24_jumlah_di_depan(self):
        Antrean.ambil_nomor(self.layanan, self.warga)
        a2 = Antrean.ambil_nomor(self.layanan, self.warga2)
        self.assertEqual(a2.jumlah_di_depan, 1)


class AntreanViewTests(DasarTestCase):
    def test_25_warga_ambil_antrean_lewat_view(self):
        self.client.force_login(self.warga)
        r = self.client.post(reverse("layanan:antrean_ambil", args=[self.layanan.pk]))
        a = Antrean.objects.get()
        self.assertRedirects(r, reverse("layanan:antrean_tiket", args=[a.pk]))

    def test_26_ambil_antrean_tidak_bisa_lewat_get(self):
        self.client.force_login(self.warga)
        r = self.client.get(reverse("layanan:antrean_ambil", args=[self.layanan.pk]))
        self.assertEqual(r.status_code, 405)

    def test_27_ambil_antrean_ganda_ditolak(self):
        self.client.force_login(self.warga)
        url = reverse("layanan:antrean_ambil", args=[self.layanan.pk])
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(Antrean.objects.count(), 1)

    def test_28_tiket_orang_lain_tidak_bisa_dilihat(self):
        a = Antrean.ambil_nomor(self.layanan, self.warga2)
        self.client.force_login(self.warga)
        self.assertEqual(self.client.get(reverse("layanan:antrean_tiket", args=[a.pk])).status_code, 403)

    def test_29_batalkan_antrean_menunggu(self):
        a = Antrean.ambil_nomor(self.layanan, self.warga)
        self.client.force_login(self.warga)
        self.client.post(reverse("layanan:antrean_batal", args=[a.pk]))
        a.refresh_from_db()
        self.assertEqual(a.status, Antrean.Status.BATAL)

    def test_30_petugas_memanggil_lalu_menyelesaikan(self):
        a = Antrean.ambil_nomor(self.layanan, self.warga)
        self.client.force_login(self.petugas)
        self.client.post(reverse("layanan:antrean_panggil", args=[self.layanan.pk]))
        a.refresh_from_db()
        self.assertEqual(a.status, Antrean.Status.DIPANGGIL)
        self.client.post(reverse("layanan:antrean_selesai", args=[a.pk]))
        a.refresh_from_db()
        self.assertEqual(a.status, Antrean.Status.SELESAI)

    def test_31_tidak_bisa_panggil_saat_masih_ada_yang_dipanggil(self):
        Antrean.ambil_nomor(self.layanan, self.warga)
        Antrean.ambil_nomor(self.layanan, self.warga2)
        self.client.force_login(self.petugas)
        url = reverse("layanan:antrean_panggil", args=[self.layanan.pk])
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(Antrean.objects.filter(status=Antrean.Status.DIPANGGIL).count(), 1)

    def test_32_warga_tidak_bisa_akses_panel_petugas(self):
        self.client.force_login(self.warga)
        self.assertEqual(self.client.get(reverse("layanan:antrean_panel")).status_code, 403)

    def test_33_layar_publik_tanpa_login(self):
        a = Antrean.ambil_nomor(self.layanan, self.warga)
        Antrean.panggil_berikutnya(self.layanan)
        r = self.client.get(reverse("layanan:antrean_layar"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, a.nomor_tampil)


class DashboardPerPeranTests(DasarTestCase):
    def test_34_halaman_muka_untuk_pengunjung(self):
        r = self.client.get(reverse("layanan:beranda"))
        self.assertContains(r, 'class="hero"')
        self.assertContains(r, "Layanan Publik Digital")

    def test_35_menu_warga_tidak_memuat_menu_petugas(self):
        self.client.force_login(self.warga)
        r = self.client.get(reverse("layanan:beranda"))
        self.assertContains(r, "Surat Saya")
        self.assertContains(r, "Ambil Antrean")
        self.assertNotContains(r, "Kelola Surat")
        self.assertNotContains(r, "Panel Antrean")

    def test_36_menu_petugas_tidak_memuat_menu_warga(self):
        self.client.force_login(self.petugas)
        r = self.client.get(reverse("layanan:beranda"))
        self.assertContains(r, "Dashboard Petugas")
        self.assertContains(r, "Kelola Surat")
        self.assertContains(r, "Panel Antrean")
        self.assertNotContains(r, "Surat Saya")
        self.assertNotContains(r, "Ambil Antrean")

    def test_37_menu_garis_tiga_tersedia(self):
        self.client.force_login(self.warga)
        r = self.client.get(reverse("layanan:beranda"))
        self.assertContains(r, 'id="tombol-menu"')
        self.assertContains(r, 'id="drawer"')

    def test_38_petugas_diarahkan_dari_halaman_warga(self):
        self.client.force_login(self.petugas)
        for nama in ("layanan:surat_daftar", "layanan:surat_buat", "layanan:antrean_pilih"):
            r = self.client.get(reverse(nama))
            self.assertRedirects(r, reverse("layanan:beranda"))

    def test_39_statistik_dashboard_petugas(self):
        self.buat_surat()
        Antrean.ambil_nomor(self.layanan, self.warga)
        self.client.force_login(self.petugas)
        r = self.client.get(reverse("layanan:beranda"))
        self.assertEqual(r.context["jml_diajukan"], 1)
        self.assertEqual(r.context["jml_menunggu"], 1)


class PenyempurnaanTests(DasarTestCase):
    def test_44_kode_pengajuan(self):
        p = self.buat_surat()
        self.assertEqual(p.kode, f"SRT-{p.pk:05d}")

    def test_45_pencarian_kelola_surat(self):
        self.buat_surat(self.warga)
        self.buat_surat(self.warga2)
        self.client.force_login(self.petugas)
        r = self.client.get(reverse("layanan:kelola_surat"), {"q": "warga2"})
        self.assertEqual(len(r.context["daftar"]), 1)

    def test_46_paginasi_kelola_surat(self):
        for _ in range(12):
            self.buat_surat()
        self.client.force_login(self.petugas)
        r1 = self.client.get(reverse("layanan:kelola_surat"))
        r2 = self.client.get(reverse("layanan:kelola_surat"), {"page": 2})
        self.assertEqual((len(r1.context["daftar"]), len(r2.context["daftar"])), (10, 2))

    def test_47_antrean_pilih_menampilkan_ringkasan(self):
        Antrean.ambil_nomor(self.layanan, self.warga2)
        self.client.force_login(self.warga)
        r = self.client.get(reverse("layanan:antrean_pilih"))
        baris = {b["layanan"].kode: b for b in r.context["daftar_layanan"]}
        self.assertEqual(baris["A"]["menunggu"], 1)

    def test_48_detail_surat_menampilkan_kode(self):
        p = self.buat_surat()
        self.client.force_login(self.warga)
        self.assertContains(self.client.get(reverse("layanan:surat_detail", args=[p.pk])), p.kode)

    def test_49_dashboard_petugas_daftar_surat_baru(self):
        self.buat_surat()
        self.client.force_login(self.petugas)
        r = self.client.get(reverse("layanan:beranda"))
        self.assertEqual(len(r.context["surat_perlu_diproses"]), 1)


class ProfilTests(DasarTestCase):
    def test_40_profil_wajib_login(self):
        r = self.client.get(reverse("layanan:profil"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r.url)

    def test_41_profil_menampilkan_peran(self):
        self.client.force_login(self.petugas)
        self.assertContains(self.client.get(reverse("layanan:profil")), "Petugas")
        self.client.force_login(self.warga)
        self.assertContains(self.client.get(reverse("layanan:profil")), "Warga")

    def test_42_ubah_profil(self):
        self.client.force_login(self.warga)
        r = self.client.post(
            reverse("layanan:profil"),
            {"first_name": "Budi", "last_name": "Santoso", "email": "budi@example.com"},
        )
        self.assertRedirects(r, reverse("layanan:profil"))
        self.warga.refresh_from_db()
        self.assertEqual(self.warga.get_full_name(), "Budi Santoso")

    def test_43_email_profil_wajib_diisi(self):
        self.client.force_login(self.warga)
        r = self.client.post(
            reverse("layanan:profil"), {"first_name": "Budi", "last_name": "", "email": ""}
        )
        self.assertEqual(r.status_code, 200)
        self.warga.refresh_from_db()
        self.assertEqual(self.warga.email, "w@example.com")
