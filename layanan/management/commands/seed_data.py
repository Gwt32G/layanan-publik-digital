from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from layanan.models import JenisSurat, Layanan


class Command(BaseCommand):
    help = "Mengisi data awal: jenis surat, layanan antrean, dan akun petugas contoh."

    def handle(self, *args, **options):
        for nama in [
            "Surat Keterangan Domisili",
            "Surat Keterangan Tidak Mampu",
            "Surat Pengantar KTP",
            "Surat Keterangan Usaha",
        ]:
            JenisSurat.objects.get_or_create(nama=nama)

        for kode, nama in [("A", "Pelayanan Umum"), ("B", "Kependudukan"), ("C", "Perizinan")]:
            Layanan.objects.get_or_create(kode=kode, defaults={"nama": nama})

        if not User.objects.filter(username="petugas").exists():
            User.objects.create_user("petugas", "petugas@example.com", "petugas12345", is_staff=True)
            self.stdout.write("Akun petugas dibuat: petugas / petugas12345 (ganti sebelum produksi)")
        self.stdout.write(self.style.SUCCESS("Data awal siap."))
