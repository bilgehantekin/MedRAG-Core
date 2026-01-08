# 🏥 Medical Chatbot - Sağlık Asistanı

Türkçe sağlık odaklı bilgilendirme chatbot'u. Kullanıcıların sağlıkla ilgili sorularını yanıtlar, genel bilgi ve yönlendirme sağlar.

> ⚠️ **Önemli:** Bu bot teşhis koymaz, sadece bilgilendirme ve yönlendirme yapar.

## 🎯 Özellikler

- ✅ Sağlık sorularını yanıtlama
- ✅ Sağlık dışı soruları filtreleme
- ✅ Acil durum tespiti ve yönlendirme
- ✅ Selamlaşma türlerine göre özel yanıtlar
- ✅ Follow-up soru desteği
- ✅ Modern chat arayüzü
- ✅ Groq LLM + Translation Pipeline (TR → EN → LLM → TR)

## 📁 Proje Yapısı

```
medical_chatbot/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI ana uygulama
│   │   ├── health_filter.py # Sağlık filtresi
│   │   └── prompts.py       # LLM prompt şablonları
│   └── requirements.txt
├── frontend/
│   ├── index.html           # Ana sayfa
│   ├── styles.css           # Stiller
│   └── app.js               # JavaScript uygulaması
└── README.md
```

## 🚀 Kurulum

### 1. Groq API Key Alın

1. [Groq Console](https://console.groq.com/)'a gidin
2. Ücretsiz hesap oluşturun
3. API Keys bölümünden yeni bir key oluşturun

### 2. Backend Kurulumu

```bash
cd backend

# Virtual environment oluştur
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Bağımlılıkları yükle
pip install -r requirements.txt

# .env dosyası oluştur
cp .env.example .env
# .env dosyasına GROQ_API_KEY'inizi ekleyin
```

### 3. Backend'i Çalıştır

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Frontend'i Çalıştır

```bash
cd frontend

# Basit HTTP server ile
python3 -m http.server 3000

# veya
npx serve .
```

Tarayıcıda aç: http://localhost:3000

## 🔧 Yapılandırma

### Ortam Değişkenleri (.env)

```bash
GROQ_API_KEY="your-groq-api-key-here"
GROQ_MODEL="llama-3.3-70b-versatile"  # veya llama-3.1-70b-versatile, mixtral-8x7b-32768
```

### Desteklenen Groq Modelleri

- `llama-3.3-70b-versatile` (önerilen)
- `llama-3.1-70b-versatile`
- `mixtral-8x7b-32768`

## 📡 API Endpoints

### POST /chat

```json
{
  "message": "Baş ağrısı için ne yapabilirim?",
  "history": [],
  "detailed_response": false
}
```

**Yanıt:**
```json
{
  "response": "Baş ağrısı için...",
  "is_emergency": false,
  "disclaimer": "⚠️ Bu bilgiler eğitim amaçlıdır..."
}
```

### GET /health
API sağlık kontrolü

### GET /models
Mevcut Groq modellerini listele

## 🛡️ Güvenlik Özellikleri

1. **Domain Filtresi:** Sağlık dışı sorular reddedilir
2. **Acil Durum Tespiti:** Kritik semptomlar için 112 yönlendirmesi
3. **Uyarı Mesajları:** Her yanıtta bilgilendirme disclaimeri
4. **Teşhis Engeli:** LLM teşhis koymamak üzere eğitilmiş

## 🎨 Ekran Görüntüleri

- Modern chat arayüzü
- Mesaj baloncukları (kullanıcı/asistan)
- Yazıyor animasyonu
- Acil durum uyarıları
- Mobil uyumlu tasarım

## 📝 Lisans

MIT License

## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Commit edin (`git commit -m 'Add amazing feature'`)
4. Push edin (`git push origin feature/amazing-feature`)
5. Pull Request açın

---

⚠️ **Uyarı:** Bu uygulama sadece bilgilendirme amaçlıdır. Tıbbi tavsiye yerine geçmez. Acil durumlarda 112'yi arayın.
