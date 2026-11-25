from functools import wraps

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import PengajuanForm, ProfilForm, RegisterForm, StatusForm
from .models import Antrean, AntreanAktifError, Layanan, PengajuanSurat

PER_HALAMAN = 10
TUNGGU_DITAMPILKAN = 5


# ---------- Pembantu ----------


def petugas_required(view):
    """Hanya akun staf (petugas) yang boleh mengakses."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def warga_required(view):
    """Halaman khusus warga; petugas diarahkan kembali ke dashboard-nya."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_staff:
            messages.info(request, "Halaman ini khusus untuk warga.")
            return redirect("layanan:beranda")
        return view(request, *args, **kwargs)

    return wrapper


def halaman(request, queryset, per_halaman=PER_HALAMAN):
    return Paginator(queryset, per_halaman).get_page(request.GET.get("page"))


def ringkasan_layanan(hari_ini, dengan_daftar_tunggu=False):
    """Ringkasan antrean hari ini untuk setiap layanan aktif."""
    baris = []
    for layanan in Layanan.objects.filter(aktif=True):
        qs = layanan.antrean.filter(tanggal=hari_ini)
        menunggu = qs.filter(status=Antrean.Status.MENUNGGU)
        item = {
            "layanan": layanan,
            "dipanggil": qs.filter(status=Antrean.Status.DIPANGGIL)
            .select_related("pengguna", "layanan")
            .first(),
            "menunggu": menunggu.count(),
        }
        if dengan_daftar_tunggu:
            item["daftar_tunggu"] = list(
                menunggu.select_related("pengguna", "layanan").order_by("nomor")[:TUNGGU_DITAMPILKAN]
            )
        baris.append(item)
    return baris


# ---------- Umum ----------


def beranda(request):
    konteks = {}
    user = request.user
    if user.is_authenticated:
        hari_ini = timezone.localdate()
        if user.is_staff:
            Status = PengajuanSurat.Status
            konteks["jml_diajukan"] = PengajuanSurat.objects.filter(status=Status.DIAJUKAN).count()
            konteks["jml_diproses"] = PengajuanSurat.objects.filter(status=Status.DIPROSES).count()
            konteks["jml_menunggu"] = Antrean.objects.filter(
                tanggal=hari_ini, status=Antrean.Status.MENUNGGU
            ).count()
            konteks["jml_dipanggil"] = Antrean.objects.filter(
                tanggal=hari_ini, status=Antrean.Status.DIPANGGIL
            ).count()
            konteks["surat_perlu_diproses"] = list(
                PengajuanSurat.objects.filter(status=Status.DIAJUKAN)
                .select_related("jenis", "pemohon")
                .order_by("dibuat")[:5]
            )
        else:
            konteks["jumlah_surat"] = user.pengajuan_surat.count()
            konteks["surat_terbaru"] = list(user.pengajuan_surat.select_related("jenis")[:3])
            konteks["antrean_aktif"] = [
                a for a in user.antrean.filter(tanggal=hari_ini).select_related("layanan") if a.aktif
            ]
    return render(request, "layanan/beranda.html", konteks)


def register(request):
    if request.user.is_authenticated:
        return redirect("layanan:beranda")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Pendaftaran berhasil. Selamat datang!")
            return redirect("layanan:beranda")
    else:
        form = RegisterForm()
    return render(request, "registration/register.html", {"form": form})


@login_required
def profil(request):
    if request.method == "POST":
        form = ProfilForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil berhasil diperbarui.")
            return redirect("layanan:profil")
    else:
        form = ProfilForm(instance=request.user)
    konteks = {
        "form": form,
        "peran": "Petugas" if request.user.is_staff else "Warga",
        "jumlah_surat": request.user.pengajuan_surat.count(),
        "jumlah_antrean": request.user.antrean.count(),
    }
    return render(request, "layanan/profil.html", konteks)


# ---------- Pengajuan surat (warga) ----------


@warga_required
def surat_daftar(request):
    daftar = halaman(request, request.user.pengajuan_surat.select_related("jenis"))
    return render(request, "layanan/surat_daftar.html", {"daftar": daftar})


@warga_required
def surat_buat(request):
    if request.method == "POST":
        form = PengajuanForm(request.POST)
        if form.is_valid():
            pengajuan = form.save(commit=False)
            pengajuan.pemohon = request.user
            pengajuan.save()
            messages.success(
                request, f"Pengajuan berhasil dikirim. Kode pengajuan Anda: {pengajuan.kode}."
            )
            return redirect("layanan:surat_detail", pk=pengajuan.pk)
    else:
        form = PengajuanForm()
    return render(request, "layanan/surat_form.html", {"form": form})


@login_required
def surat_detail(request, pk):
    pengajuan = get_object_or_404(PengajuanSurat.objects.select_related("jenis", "pemohon"), pk=pk)
    if pengajuan.pemohon != request.user and not request.user.is_staff:
        raise PermissionDenied
    return render(request, "layanan/surat_detail.html", {"p": pengajuan})


# ---------- Pengajuan surat (petugas) ----------


@petugas_required
def kelola_surat(request):
    status = request.GET.get("status", "")
    q = request.GET.get("q", "").strip()
    qs = PengajuanSurat.objects.select_related("jenis", "pemohon")
    if status in PengajuanSurat.Status.values:
        qs = qs.filter(status=status)
    else:
        status = ""
    if q:
        kondisi = (
            Q(pemohon__username__icontains=q) | Q(nik__icontains=q) | Q(jenis__nama__icontains=q)
        )
        angka = q.upper().removeprefix("SRT-").lstrip("0")
        if angka.isdigit() and len(angka) <= 9:
            kondisi |= Q(pk=int(angka))
        qs = qs.filter(kondisi)
    params = request.GET.copy()
    params.pop("page", None)
    return render(
        request,
        "layanan/kelola_surat.html",
        {
            "daftar": halaman(request, qs),
            "status": status,
            "q": q,
            "qs": params.urlencode(),
            "pilihan_status": PengajuanSurat.Status.choices,
        },
    )


@petugas_required
def kelola_surat_ubah(request, pk):
    pengajuan = get_object_or_404(PengajuanSurat.objects.select_related("jenis", "pemohon"), pk=pk)
    if request.method == "POST":
        form = StatusForm(request.POST, instance=pengajuan)
        if form.is_valid():
            form.save()
            messages.success(request, f"Status pengajuan {pengajuan.kode} berhasil diperbarui.")
            return redirect("layanan:kelola_surat")
    else:
        form = StatusForm(instance=pengajuan)
    return render(request, "layanan/kelola_surat_ubah.html", {"form": form, "p": pengajuan})


# ---------- Antrean digital (warga) ----------


@warga_required
def antrean_pilih(request):
    hari_ini = timezone.localdate()
    saya = request.user.antrean.filter(tanggal=hari_ini).select_related("layanan")
    return render(
        request,
        "layanan/antrean_pilih.html",
        {"daftar_layanan": ringkasan_layanan(hari_ini), "saya": saya},
    )


@warga_required
@require_POST
def antrean_ambil(request, layanan_id):
    layanan = get_object_or_404(Layanan, pk=layanan_id, aktif=True)
    try:
        antrean = Antrean.ambil_nomor(layanan, request.user)
    except AntreanAktifError as e:
        messages.error(request, str(e))
        return redirect("layanan:antrean_pilih")
    messages.success(request, f"Nomor antrean Anda: {antrean.nomor_tampil}.")
    return redirect("layanan:antrean_tiket", pk=antrean.pk)


@login_required
def antrean_tiket(request, pk):
    antrean = get_object_or_404(Antrean.objects.select_related("layanan"), pk=pk)
    if antrean.pengguna != request.user and not request.user.is_staff:
        raise PermissionDenied
    return render(request, "layanan/antrean_tiket.html", {"a": antrean})


@warga_required
@require_POST
def antrean_batal(request, pk):
    antrean = get_object_or_404(Antrean, pk=pk, pengguna=request.user)
    if antrean.status == Antrean.Status.MENUNGGU:
        antrean.status = Antrean.Status.BATAL
        antrean.save(update_fields=["status"])
        messages.success(request, "Antrean berhasil dibatalkan.")
    else:
        messages.error(request, "Antrean ini tidak dapat dibatalkan.")
    return redirect("layanan:antrean_pilih")


# ---------- Antrean digital (petugas & layar publik) ----------


@petugas_required
def antrean_panel(request):
    baris = ringkasan_layanan(timezone.localdate(), dengan_daftar_tunggu=True)
    return render(request, "layanan/antrean_panel.html", {"baris": baris})


@petugas_required
@require_POST
def antrean_panggil(request, layanan_id):
    layanan = get_object_or_404(Layanan, pk=layanan_id)
    if layanan.antrean.filter(
        tanggal=timezone.localdate(), status=Antrean.Status.DIPANGGIL
    ).exists():
        messages.error(request, "Selesaikan antrean yang sedang dilayani terlebih dahulu.")
        return redirect("layanan:antrean_panel")
    antrean = Antrean.panggil_berikutnya(layanan)
    if antrean is None:
        messages.info(request, "Tidak ada antrean yang menunggu.")
    else:
        messages.success(request, f"Memanggil nomor {antrean.nomor_tampil}.")
    return redirect("layanan:antrean_panel")


@petugas_required
@require_POST
def antrean_selesai(request, pk):
    antrean = get_object_or_404(Antrean, pk=pk, status=Antrean.Status.DIPANGGIL)
    antrean.status = Antrean.Status.SELESAI
    antrean.save(update_fields=["status"])
    messages.success(request, f"Nomor {antrean.nomor_tampil} selesai dilayani.")
    return redirect("layanan:antrean_panel")


def antrean_layar(request):
    """Layar publik (tanpa login) yang menampilkan nomor yang sedang dipanggil."""
    return render(
        request, "layanan/antrean_layar.html", {"baris": ringkasan_layanan(timezone.localdate())}
    )
