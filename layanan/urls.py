from django.urls import path

from . import views

app_name = "layanan"

urlpatterns = [
    path("", views.beranda, name="beranda"),
    path("daftar/", views.register, name="register"),
    path("profil/", views.profil, name="profil"),
    # Surat
    path("surat/", views.surat_daftar, name="surat_daftar"),
    path("surat/baru/", views.surat_buat, name="surat_buat"),
    path("surat/<int:pk>/", views.surat_detail, name="surat_detail"),
    path("petugas/surat/", views.kelola_surat, name="kelola_surat"),
    path("petugas/surat/<int:pk>/", views.kelola_surat_ubah, name="kelola_surat_ubah"),
    # Antrean
    path("antrean/", views.antrean_pilih, name="antrean_pilih"),
    path("antrean/ambil/<int:layanan_id>/", views.antrean_ambil, name="antrean_ambil"),
    path("antrean/tiket/<int:pk>/", views.antrean_tiket, name="antrean_tiket"),
    path("antrean/batal/<int:pk>/", views.antrean_batal, name="antrean_batal"),
    path("antrean/layar/", views.antrean_layar, name="antrean_layar"),
    path("petugas/antrean/", views.antrean_panel, name="antrean_panel"),
    path("petugas/antrean/panggil/<int:layanan_id>/", views.antrean_panggil, name="antrean_panggil"),
    path("petugas/antrean/selesai/<int:pk>/", views.antrean_selesai, name="antrean_selesai"),
]
