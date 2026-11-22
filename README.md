# Satış hattı

The Picked Few satış hattının durum deposu. AI Ofisi panelindeki Satış sayfası bu depodaki `durum.json` dosyasını okur ve hattın nerede olduğunu gösterir.

## Bu depo herkese açıktır

Şunlar bu depoya yazılmaz: maliyet, tedarikçi adı, kâr rakamı, müşteri bilgisi, kişisel bilgi, e-posta adresi, Drive bağlantısı, şifre ya da belirteç. Bunlar hattın özel klasöründe kalır.

## İçerik

| Yol | İçerik |
|---|---|
| `durum.json` | Hattın güncel durumu |
| `isler/<slug>/video.mp4` | Onaya sunulan video |
| `isler/<slug>/gorsel.jpg` | Onaya sunulan görsel |
| `isler/<slug>/metin.md` | Onaya sunulan metin |

Mesaj ve ürün adayı türündeki işlerin dosyası bu depoya konmaz.

## `durum.json` kuralları

- Zorunlu alanlar: `"schema": 1`, `"line": "satis"`, `updated_at`, `items`.
- İsteğe bağlı bölümler: `name`, `note`, `runs`, `phase`, `metrics` (en çok 8), `tasks` (en çok 30). `items` en çok 60 satırdır.
- İş türleri (`kind`): `video`, `gorsel`, `metin`, `mesaj`, `urun`.
- Aşamalar (`stage`): `cekim`, `siparis`, `kurgu`, `onay`, `duzeltme`, `beklemede`, `yayin`, `yayinda`.
- `next` (`sen`, `claude`, `chatgpt`) sıradaki adımın sahibini değiştirir.
- `slug` "NN-kisa-ad" biçimindedir; tarihler saat dilimi içeren ISO biçimindedir, `due` ve `gate_date` yalnız gün (`YYYY-AA-GG`).
- `public_url` yalnız YouTube, TikTok ya da Instagram içerik adresi olabilir.
- Dosya 60 KB'ı aşmaz.

Biçim bozulursa panel son geçerli kopyayı gösterir ve hatayı bildirir.

## Kim yazar

`durum.json` dosyasını hattın Claude görevi günceller. Yayın, mesaj, sipariş ve ödeme bu depodan yapılmaz; hepsi kullanıcı onayıyla hattın dışında yürür.
