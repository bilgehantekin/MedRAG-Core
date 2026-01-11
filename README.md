# 🏥 3D Medical Chatbot - Sağlık Asistanı

Türkçe sağlık odaklı bilgilendirme chatbot'u. 3D insan modeli üzerinde etkileşimli bölge seçimi veya direkt sohbet ile AI destekli sağlık bilgilendirme.

> ⚠️ **Önemli:** Bu uygulama teşhis koymaz, sadece bilgilendirme ve yönlendirme yapar.

## 📸 Ekran Görüntüleri

![Hoş Geldin Ekranı](docs/screenshots/welcome-screen.png)
![3D Model Görünümü](docs/screenshots/3d-model-view.png)
![Chat Paneli](docs/screenshots/chat-panel.png)

## ✨ Özellikler

### İki Farklı Etkileşim Modu
- **🧍 3D Model ile Göster** - 24 farklı vücut bölgesi, yapısal semptom seçimi, şiddet skalası
- **💬 Direkt Yazarak Anlat** - Serbest metin girişi ile doğal dil anlatımı

### Chatbot Özellikleri
- ✅ Türkçe ilaç ismi tanıma (117+ ilaç, typo düzeltme, ek kırpma)
- ✅ Çoklu kelime ilaç tespiti (tylol hot, aferin forte)
- ✅ Sağlık dışı soruları filtreleme (hard/soft ayrımı)
- ✅ Acil durum tespiti ve 112 yönlendirmesi
- ✅ Groq LLM + Translation Pipeline (TR → EN → LLM → TR)

## 🛠️ Teknoloji Stack

| Frontend | Backend |
|----------|---------|
| React 18 + TypeScript | FastAPI |
| Three.js (@react-three/fiber) | Groq LLM (Llama 3.3) |
| Zustand | Deep Translator |
| Tailwind CSS | Pydantic |

## 📁 Proje Yapısı

```
medical_chatbot/
├── backend/
│   └── app/
│       ├── main.py           # FastAPI ana uygulama
│       ├── health_filter.py  # Sağlık/acil durum filtresi
│       ├── medicines.py      # İlaç veritabanı (tek kaynak)
│       └── prompts.py        # LLM prompt şablonları
├── frontend-3d/
│   └── src/
│       ├── components/       # HumanModel, ChatPanel, SymptomPanel
│       ├── store/            # Zustand state management
│       └── data/             # Vücut bölgeleri verisi
└── docs/screenshots/
```

## 🚀 Kurulum

### 1. Groq API Key
[Groq Console](https://console.groq.com/)'dan ücretsiz API key alın.

### 2. Backend
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
echo "GROQ_API_KEY=your_key" > .env
```

### 3. Frontend
```bash
cd frontend-3d
npm install
```

### 4. Çalıştır
```bash
# Terminal 1 - Backend
cd backend && source venv/bin/activate && uvicorn app.main:app --port 8000

# Terminal 2 - Frontend
cd frontend-3d && npm run dev
```

Tarayıcıda: **http://localhost:3000**

## 📡 API Endpoints

| Endpoint | Açıklama |
|----------|----------|
| POST /chat | Ana sohbet endpoint'i |
| GET /health | API sağlık kontrolü |
| GET /models | Mevcut Groq modelleri |

## 🛡️ Güvenlik Özellikleri

- **Domain Filtresi:** Sağlık dışı sorular reddedilir
- **Acil Durum Tespiti:** Kritik semptomlar için 112 yönlendirmesi
- **Negasyon Kontrolü:** "Göğüs ağrım yok" gibi ifadeler false positive tetiklemez
- **Teşhis Engeli:** LLM teşhis koymamak üzere yapılandırılmış

## 📝 Sürüm Geçmişi

### v2.2 (Ocak 2026)
- ✨ `medicines.py` - İlaç veritabanı tek kaynakta toplandı
- ✨ Çoklu kelime ilaç tespiti (n-gram: tylol hot, aferin forte)
- ✨ Hard/soft non-health ayrımı (fiyat, ne kadar artık soft)
- ✨ Acil durum negasyon kontrolü (false positive önleme)
- ✨ temperature=0 classifier (deterministik sınıflandırma)
- 🐛 "nasıl hissediyorsun" greeting bug düzeltildi
- 🐛 "aferin ya" pattern düzeltmesi (sadece cümle sonunda)

### v2.1 (Ocak 2026)
- ✨ Direkt chat modu eklendi
- ✨ Hoş geldin ekranında mod seçimi
- ✨ Streaming yanıt efekti
- 🐛 Türkçe dilbilgisine uygun mesaj formatları

### v2.0
- 3D insan modeli entegrasyonu
- Yapısal semptom raporlama
- 24 vücut bölgesi desteği

### v1.0
- Temel chatbot işlevselliği
- Sağlık filtresi
- Acil durum tespiti

## 📝 Lisans

MIT License

---

⚠️ **Uyarı:** Bu uygulama sadece bilgilendirme amaçlıdır. Tıbbi tavsiye yerine geçmez. Acil durumlarda **112**'yi arayın!
