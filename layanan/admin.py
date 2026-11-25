from django.contrib import admin

from .models import Antrean, JenisSurat, Layanan, PengajuanSurat

admin.site.site_header = "Layanan Publik Digital – Administrasi"
admin.site.site_title = "Administrasi Layanan Publik Digital"
admin.site.index_title = "Kelola data master"


@admin.register(JenisSurat)
class JenisSuratAdmin(admin.ModelAdmin):
    list_display = ("nama", "aktif")
    list_filter = ("aktif",)
    search_fields = ("nama",)


@admin.register(PengajuanSurat)
class PengajuanSuratAdmin(admin.ModelAdmin):
    list_display = ("id", "pemohon", "jenis", "status", "dibuat")
    list_filter = ("status", "jenis")
    search_fields = ("pemohon__username", "nik")


@admin.register(Layanan)
class LayananAdmin(admin.ModelAdmin):
    list_display = ("kode", "nama", "aktif")
    list_filter = ("aktif",)


@admin.register(Antrean)
class AntreanAdmin(admin.ModelAdmin):
    list_display = ("nomor_tampil", "pengguna", "tanggal", "status")
    list_filter = ("status", "layanan", "tanggal")
