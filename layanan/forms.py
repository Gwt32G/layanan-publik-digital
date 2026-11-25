from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import JenisSurat, PengajuanSurat


class RegisterForm(UserCreationForm):
    email = forms.EmailField(label="Email", required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Nama pengguna"
        self.fields["password1"].label = "Kata sandi"
        self.fields["password2"].label = "Konfirmasi kata sandi"

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class ProfilForm(forms.ModelForm):
    email = forms.EmailField(label="Email", required=True)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        labels = {"first_name": "Nama depan", "last_name": "Nama belakang"}


class PengajuanForm(forms.ModelForm):
    class Meta:
        model = PengajuanSurat
        fields = ("jenis", "nik", "keperluan")
        labels = {"jenis": "Jenis surat", "nik": "NIK", "keperluan": "Keperluan"}
        help_texts = {"nik": "16 digit angka, sesuai KTP."}
        widgets = {
            "nik": forms.TextInput(attrs={"placeholder": "3201010101010001", "inputmode": "numeric", "maxlength": 16}),
            "keperluan": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Jelaskan untuk apa surat ini dibutuhkan"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["jenis"].queryset = JenisSurat.objects.filter(aktif=True)
        self.fields["jenis"].empty_label = "Pilih jenis surat"


class StatusForm(forms.ModelForm):
    class Meta:
        model = PengajuanSurat
        fields = ("status", "catatan_petugas")
        labels = {"status": "Status pengajuan", "catatan_petugas": "Catatan untuk pemohon"}
        help_texts = {"catatan_petugas": "Wajib diisi jika pengajuan ditolak."}
        widgets = {"catatan_petugas": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        data = super().clean()
        if data.get("status") == PengajuanSurat.Status.DITOLAK and not data.get("catatan_petugas"):
            self.add_error("catatan_petugas", "Alasan penolakan wajib diisi.")
        return data
