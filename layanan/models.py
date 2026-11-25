from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.db.models import Max
from django.utils import timezone


class AntreanAktifError(Exception):
    """Pengguna masih punya antrean aktif di layanan yang sama hari ini."""


class JenisSurat(models.Model):
    nama = models.CharField(max_length=100, unique=True)
    deskripsi = models.TextField(blank=True)
    aktif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nama"]
        verbose_name = "jenis surat"
        verbose_name_plural = "jenis surat"

    def __str__(self):
        return self.nama


class PengajuanSurat(models.Model):
    class Status(models.TextChoices):
        DIAJUKAN = "diajukan", "Diajukan"
        DIPROSES = "diproses", "Diproses"
        SELESAI = "selesai", "Selesai"
        DITOLAK = "ditolak", "Ditolak"

    pemohon = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pengajuan_surat"
    )
    jenis = models.ForeignKey(JenisSurat, on_delete=models.PROTECT, related_name="pengajuan")
    nik = models.CharField(
        "NIK",
        max_length=16,
        validators=[RegexValidator(r"^\d{16}$", "NIK harus 16 digit angka.")],
    )
    keperluan = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DIAJUKAN)
    catatan_petugas = models.TextField(blank=True)
    dibuat = models.DateTimeField(auto_now_add=True)
    diperbarui = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-dibuat"]
        verbose_name = "pengajuan surat"
        verbose_name_plural = "pengajuan surat"

    def __str__(self):
        return f"#{self.pk} {self.jenis} - {self.pemohon}"

    @property
    def kode(self):
        return f"SRT-{self.pk:05d}"

    @property
    def selesai_diproses(self):
        return self.status in (self.Status.SELESAI, self.Status.DITOLAK)


class Layanan(models.Model):
    nama = models.CharField(max_length=100, unique=True)
    kode = models.CharField(max_length=3, unique=True, help_text="Awalan nomor antrean, mis. A")
    aktif = models.BooleanField(default=True)

    class Meta:
        ordering = ["kode"]
        verbose_name = "layanan"
        verbose_name_plural = "layanan"

    def __str__(self):
        return f"{self.kode} - {self.nama}"


class Antrean(models.Model):
    class Status(models.TextChoices):
        MENUNGGU = "menunggu", "Menunggu"
        DIPANGGIL = "dipanggil", "Dipanggil"
        SELESAI = "selesai", "Selesai"
        BATAL = "batal", "Batal"

    layanan = models.ForeignKey(Layanan, on_delete=models.CASCADE, related_name="antrean")
    pengguna = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="antrean"
    )
    tanggal = models.DateField(default=timezone.localdate)
    nomor = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.MENUNGGU)
    dibuat = models.DateTimeField(auto_now_add=True)
    dipanggil_pada = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["tanggal", "nomor"]
        constraints = [
            models.UniqueConstraint(
                fields=["layanan", "tanggal", "nomor"], name="nomor_unik_per_layanan_per_hari"
            )
        ]
        verbose_name = "antrean"
        verbose_name_plural = "antrean"

    def __str__(self):
        return self.nomor_tampil

    @property
    def nomor_tampil(self):
        return f"{self.layanan.kode}-{self.nomor:03d}"

    @property
    def aktif(self):
        return self.status in (self.Status.MENUNGGU, self.Status.DIPANGGIL)

    @property
    def jumlah_di_depan(self):
        """Banyaknya antrean menunggu dengan nomor lebih kecil di hari dan layanan yang sama."""
        return Antrean.objects.filter(
            layanan=self.layanan,
            tanggal=self.tanggal,
            status=self.Status.MENUNGGU,
            nomor__lt=self.nomor,
        ).count()

    @classmethod
    def ambil_nomor(cls, layanan, pengguna, tanggal=None):
        tanggal = tanggal or timezone.localdate()
        with transaction.atomic():
            sudah_ada = cls.objects.filter(
                layanan=layanan,
                pengguna=pengguna,
                tanggal=tanggal,
                status__in=[cls.Status.MENUNGGU, cls.Status.DIPANGGIL],
            ).exists()
            if sudah_ada:
                raise AntreanAktifError("Anda masih memiliki antrean aktif di layanan ini.")
            terakhir = (
                cls.objects.filter(layanan=layanan, tanggal=tanggal).aggregate(m=Max("nomor"))["m"]
                or 0
            )
            return cls.objects.create(
                layanan=layanan, pengguna=pengguna, tanggal=tanggal, nomor=terakhir + 1
            )

    @classmethod
    def panggil_berikutnya(cls, layanan, tanggal=None):
        """Panggil antrean menunggu dengan nomor terkecil. Kembalikan None bila kosong."""
        tanggal = tanggal or timezone.localdate()
        with transaction.atomic():
            berikutnya = (
                cls.objects.filter(layanan=layanan, tanggal=tanggal, status=cls.Status.MENUNGGU)
                .order_by("nomor")
                .first()
            )
            if berikutnya is None:
                return None
            berikutnya.status = cls.Status.DIPANGGIL
            berikutnya.dipanggil_pada = timezone.now()
            berikutnya.save(update_fields=["status", "dipanggil_pada"])
            return berikutnya
