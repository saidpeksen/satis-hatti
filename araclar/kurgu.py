"""Kurgu aracı (The Picked Few satış hattı).

TALİMAT (zamanlanmış Claude görevi için)
1. Köprüdeki GORSEL-HAVUZU klasöründen işin kullandığı görselleri indir; dosyaları
   koduyla adlandırarak tek bir klasöre koy: G01.png, G07.png, H01.png ...
   (Drive'daki ad "G01-keten.png" gibidir; kod, adın ilk üç karakteridir.)
2. İşin plan dosyasını yaz: isler/NN-kisa-ad/plan.json (biçim aşağıda). Plan, PAKET
   belgesindeki görsel sırasını, sürelerini ve ekran yazılarını izler.
3. Çalıştır:
     python3 -I araclar/kurgu.py isler/NN-kisa-ad/plan.json <gorsel_klasoru> isler/NN-kisa-ad/video.mp4
4. Çıkan videodan birkaç kare çıkarıp bak (ffmpeg -ss <saniye> -i video.mp4 -frames:v 1 kare.png):
   yazılar okunuyor mu, yansıma sahnesinde "Illustration" yazısı var mı, görüntü bozuk mu.
5. Araç sonunda baytı ve sha256'yı yazdırır; YAYIN-BILGISI belgesine bunları yaz.

PLAN BİÇİMİ (JSON)
{
  "sahneler": [
    {"gorsel": "G03", "sure": 3.0, "hareket": "yakinlas", "odak": [0.5, 0.45],
     "yazi": "There's a photo hidden in this stone"},
    {"gorsel": "G07", "sure": 3.5, "hareket": "sabit",
     "yerlestir": {"foto": "H01", "alan": "daire", "belir": true}}
  ]
}
- gorsel: ONAYLI-GORSELLER'deki G kodu. Yalnız onaylı görseller kullanılır.
- sure: saniye (1.5–5). Toplam 12–20 saniye olmalı.
- hareket: "yakinlas", "uzaklas", "sola", "saga" ya da "sabit".
- odak: [x, y] 0–1 arası; yakınlaşmanın merkezi. Varsayılan [0.5, 0.5].
- yazi: İngilizce, en çok 8 kelime. En çok 4 sahnede yazı olur.
- yerlestir: yalnız G07 (alan "daire") ve G11 (alan "baski") için. foto bir H kodudur.
  "belir": true ise fotoğraf sahne boyunca yavaşça belirir.
  Bu sahnelerde "Illustration" yazısını araç kendisi ekler; kapatılamaz.

Çıktı: 1080 × 1920, 30 kare/sn, H.264, sessiz ses izi (müzik yok).
"""

import hashlib
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
GECIS = 0.35  # sahneler arası yumuşak geçiş (saniye)

# Görsellerdeki boş alanlar (1024 × 1536 görsel koordinatı)
ALANLAR = {
    "G07": {"daire": (610, 462, 245)},          # merkez x, merkez y, yarıçap
    "G11": {"baski": (592, 508, 960, 1026)},    # sol, üst, sağ, alt
}

YAZI_FONT = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
ETIKET_FONT = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"


def font(yol, boy):
    for aday in (yol, "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(aday):
            return ImageFont.truetype(aday, boy)
    return ImageFont.load_default()


def kirp_kapla(img, w, h):
    """Görseli w×h alanı tam kaplayacak biçimde ölçekler (taşan kenarlar kırpılır)."""
    oran = max(w / img.width, h / img.height)
    return img.resize((round(img.width * oran), round(img.height * oran)), Image.LANCZOS)


def daireye_yerlestir(sahne, foto, alan, guc):
    cx, cy, r = alan
    boy = 2 * r
    f = kirp_kapla(foto.convert("RGB"), boy, boy)
    f = f.crop(((f.width - boy) // 2, (f.height - boy) // 2,
                (f.width - boy) // 2 + boy, (f.height - boy) // 2 + boy))
    # Gerçek yansıma: soluk, sıcak tonlu, hafif bulanık
    f = f.filter(ImageFilter.GaussianBlur(1.6))
    sicak = Image.new("RGB", f.size, (255, 236, 205))
    f = Image.blend(f, sicak, 0.28)
    maske = Image.new("L", (boy, boy), 0)
    ImageDraw.Draw(maske).ellipse((boy * 0.08, boy * 0.08, boy * 0.92, boy * 0.92), fill=255)
    maske = maske.filter(ImageFilter.GaussianBlur(boy * 0.06))
    maske = maske.point(lambda v: int(v * 0.62 * guc))
    out = sahne.copy()
    out.paste(f, (cx - r, cy - r), maske)
    return out


def baskiya_yerlestir(sahne, foto, alan, guc):
    x0, y0, x1, y1 = alan
    w, h = x1 - x0, y1 - y0
    f = kirp_kapla(foto.convert("RGB"), w, h)
    f = f.crop(((f.width - w) // 2, (f.height - h) // 2, (f.width - w) // 2 + w, (f.height - h) // 2 + h))
    maske = Image.new("L", (w, h), int(255 * guc))
    out = sahne.copy()
    out.paste(f, (x0, y0), maske)
    return out


def kare(gorsel, ilerleme, hareket, odak):
    """Görselden 1080×1920 kare üretir (ilerleme 0–1)."""
    taban = kirp_kapla(gorsel, W, H)
    z0, z1 = {"yakinlas": (1.0, 1.14), "uzaklas": (1.14, 1.0)}.get(hareket, (1.0, 1.0))
    z = z0 + (z1 - z0) * ilerleme
    cw, ch = W / z, H / z
    ox, oy = odak
    cx = taban.width * ox
    cy = taban.height * oy
    if hareket in ("sola", "saga"):
        kay = (taban.width - cw) * (0.15 + 0.7 * (ilerleme if hareket == "saga" else 1 - ilerleme))
        cx = kay + cw / 2
    x0 = min(max(cx - cw / 2, 0), taban.width - cw)
    y0 = min(max(cy - ch / 2, 0), taban.height - ch)
    return taban.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


def yazi_ciz(img, metin, saydamlik):
    if not metin or saydamlik <= 0:
        return img
    d = ImageDraw.Draw(img, "RGBA")
    f = font(YAZI_FONT, 66)
    satirlar, satir = [], ""
    for k in metin.split():
        dene = (satir + " " + k).strip()
        if d.textlength(dene, font=f) > W - 180 and satir:
            satirlar.append(satir)
            satir = k
        else:
            satir = dene
    satirlar.append(satir)
    yuk = 84 * len(satirlar)
    y = int(H * 0.60) - yuk // 2
    a = int(255 * saydamlik)
    kutu_w = max(d.textlength(s, font=f) for s in satirlar) + 70
    d.rounded_rectangle(((W - kutu_w) / 2, y - 26, (W + kutu_w) / 2, y + yuk + 16),
                        radius=22, fill=(20, 26, 23, int(150 * saydamlik)))
    for i, s in enumerate(satirlar):
        tw = d.textlength(s, font=f)
        d.text(((W - tw) / 2, y + i * 84), s, font=f, fill=(255, 255, 255, a))
    return img


def etiket_ciz(img):
    d = ImageDraw.Draw(img, "RGBA")
    f = font(ETIKET_FONT, 34)
    metin = "Illustration"
    tw = d.textlength(metin, font=f)
    x, y = 60, 200
    d.rounded_rectangle((x - 18, y - 12, x + tw + 18, y + 50), radius=14, fill=(0, 0, 0, 120))
    d.text((x, y), metin, font=f, fill=(255, 255, 255, 235))
    return img


def sahne_karesi(s, gorseller, t):
    sure = s["sure"]
    ilerleme = min(max(t / sure, 0), 1)
    g = gorseller[s["gorsel"]]
    y = s.get("yerlestir")
    if y:
        alan = ALANLAR[s["gorsel"]][y["alan"]]
        guc = min(1.0, 0.15 + ilerleme * 1.4) if y.get("belir") else 1.0
        g = (daireye_yerlestir if y["alan"] == "daire" else baskiya_yerlestir)(g, gorseller[y["foto"]], alan, guc)
    k = kare(g, ilerleme, s.get("hareket", "sabit"), s.get("odak", [0.5, 0.5])).convert("RGB")
    if y:
        k = etiket_ciz(k)
    giris = min(1, t / 0.35)
    k = yazi_ciz(k, s.get("yazi"), giris)
    return k


def denetle(plan, gorseller):
    sahneler = plan["sahneler"]
    toplam = sum(s["sure"] for s in sahneler) - GECIS * (len(sahneler) - 1)
    if not 12 <= toplam <= 20.5:
        raise SystemExit(f"Toplam süre {toplam:.1f} sn; 12–20 olmalı.")
    if sum(1 for s in sahneler if s.get("yazi")) > 4:
        raise SystemExit("En çok 4 sahnede yazı olabilir.")
    for s in sahneler:
        if s["gorsel"] not in gorseller:
            raise SystemExit(f"Görsel yok: {s['gorsel']}")
        if s.get("yazi") and len(s["yazi"].split()) > 8:
            raise SystemExit(f"Yazı 8 kelimeyi aşıyor: {s['yazi']}")
        y = s.get("yerlestir")
        if y and (s["gorsel"] not in ALANLAR or y["alan"] not in ALANLAR[s["gorsel"]]):
            raise SystemExit(f"{s['gorsel']} görselinde '{y['alan']}' alanı yok.")
        if y and y["foto"] not in gorseller:
            raise SystemExit(f"Fotoğraf yok: {y['foto']}")
    return toplam


def main():
    if len(sys.argv) != 4:
        raise SystemExit("Kullanım: kurgu.py plan.json gorsel_klasoru cikis.mp4")
    plan = json.load(open(sys.argv[1], encoding="utf-8"))
    klasor, cikis = sys.argv[2], sys.argv[3]
    gorseller = {}
    for ad in os.listdir(klasor):
        kod = ad[:3]
        if ad.lower().endswith((".png", ".jpg", ".jpeg")) and kod[0] in "GH":
            gorseller[kod] = Image.open(os.path.join(klasor, ad)).convert("RGB")
    toplam = denetle(plan, gorseller)

    os.makedirs(os.path.dirname(os.path.abspath(cikis)), exist_ok=True)
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", cikis],
        stdin=subprocess.PIPE)

    sahneler = plan["sahneler"]
    baslangic, t0 = [], 0.0
    for s in sahneler:
        baslangic.append(t0)
        t0 += s["sure"] - GECIS
    for n in range(round(toplam * FPS)):
        t = n / FPS
        i = max(j for j in range(len(sahneler)) if baslangic[j] <= t + 1e-9)
        k = sahne_karesi(sahneler[i], gorseller, t - baslangic[i])
        if i > 0 and t - baslangic[i] < GECIS:
            onceki = sahne_karesi(sahneler[i - 1], gorseller, t - baslangic[i - 1])
            k = Image.blend(onceki, k, (t - baslangic[i]) / GECIS)
        ff.stdin.write(k.tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        raise SystemExit("ffmpeg hata verdi.")
    veri = open(cikis, "rb").read()
    print(json.dumps({"sure": round(toplam, 2), "bayt": len(veri),
                      "sha256": hashlib.sha256(veri).hexdigest()}))


if __name__ == "__main__":
    main()
