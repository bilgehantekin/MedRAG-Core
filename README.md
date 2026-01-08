# 🏥 Medical Chatbot - Sağlık Asistanı

Türkçe sağlık odaklı bilgilendirme chatbot'u. Kullanıcıların sağlıkla ilgili sorularını yanıtlar, genel bilgi ve yönlendirme sağlar.

> ⚠️ **Önemli:** Bu bot teşhis koymaz, sadece bilgilendirme ve yönlendirme yapar.

## 🎯 Özellikler

- ✅ Sağlık sorularını yanıtlama
- ✅ Sağlık dışı soruları filtreleme
- ✅ Acil durum tespiti ve yönlendirme
- ✅ Detaylı/kısa yanıt modu
- ✅ Modern chat arayüzü
- ✅ Lokal LLM desteği (Ollama)

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

### 1. Ollama Kurulumu (Lokal LLM)

```bash
# macOS
brew install ollama

# veya curl ile
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Model İndirme

```bash
# Ollama servisini başlat
ollama serve

# Başka bir terminalde model indir (önerilen)
ollama pull llama3.2

# Alternatif modeller:
# ollama pull phi3
# ollama pull mistral
# ollama pull gemma2
```

### 3. Backend Kurulumu

```bash
cd backend

# Virtual environment oluştur
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Bağımlılıkları yükle
pip install -r requirements.txt
```

### 4. Backend'i Çalıştır

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Frontend'i Çalıştır

```bash
cd frontend

# Basit HTTP server ile
python3 -m http.server 3000

# veya
npx serve .
```

Tarayıcıda aç: http://localhost:3000

## 🔧 Yapılandırma

### Ortam Değişkenleri

```bash
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="llama3.2"
```

### Frontend Ayarları

Arayüzdeki ayarlar butonundan:
- **Detaylı Yanıtlar:** Daha kapsamlı açıklamalar için
- **API Adresi:** Backend URL'ini değiştirmek için

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
Mevcut Ollama modellerini listele

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
