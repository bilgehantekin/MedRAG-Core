# 🏥 3D Medical Chatbot - Sağlık Asistanı

Türkçe sağlık odaklı bilgilendirme chatbot'u. 3D insan modeli üzerinde etkileşimli bölge seçimi ile yapısal semptom raporlama ve AI destekli sağlık bilgilendirme.

> ⚠️ **Önemli:** Bu uygulama teşhis koymaz, sadece bilgilendirme ve yönlendirme yapar.

## 🎯 Özellikler

### 3D Etkileşim (v2.0)
- ✅ 3D insan modeli üzerinde tıklanabilir vücut bölgeleri
- ✅ Hover efektleri ve seçim animasyonları
- ✅ 24 farklı vücut bölgesi (baş, boyun, göğüs, karın, kollar, bacaklar vb.)
- ✅ OrbitControls ile döndürme ve yakınlaştırma
- ✅ Yapısal semptom seçimi (ağrı, şişlik, uyuşma, morluk vb.)
- ✅ Şiddet skalası (0-10)
- ✅ Başlangıç zamanı ve tetikleyici seçimi
- ✅ Kırmızı bayrak (acil durum) işaretleme

### Chatbot
- ✅ Sağlık sorularını yanıtlama
- ✅ Yapısal semptom context'i ile zenginleştirilmiş yanıtlar
- ✅ Sağlık dışı soruları filtreleme
- ✅ Acil durum tespiti ve yönlendirme
- ✅ Selamlaşma türlerine göre özel yanıtlar
- ✅ Follow-up soru desteği
- ✅ Groq LLM + Translation Pipeline (TR → EN → LLM → TR)

## 🏗️ Teknoloji Stack

### Frontend (React + Three.js)
- **React 18** + TypeScript
- **Vite** - Build tool
- **@react-three/fiber (R3F)** - Three.js React entegrasyonu
- **@react-three/drei** - Hazır 3D bileşenler (OrbitControls, Environment)
- **Zustand** - State management
- **Tailwind CSS** - Styling

### Backend (Python + FastAPI)
- **FastAPI** - API framework
- **Groq** - LLM API (Llama 3.3)
- **Deep Translator** - Çeviri pipeline
- **Pydantic** - Data validation

## 📁 Proje Yapısı

```
medical_chatbot/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI ana uygulama
│   │   ├── health_filter.py # Sağlık filtresi
│   │   └── prompts.py       # LLM prompt şablonları
│   ├── requirements.txt
│   └── .env
├── frontend-new/            # React + Three.js frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── HumanModel.tsx   # 3D insan modeli
│   │   │   ├── Scene3D.tsx      # Three.js sahne
│   │   │   ├── SymptomPanel.tsx # Semptom seçim paneli
│   │   │   └── ChatPanel.tsx    # Chat arayüzü
│   │   ├── store/
│   │   │   └── useAppStore.ts   # Zustand store
│   │   ├── types/
│   │   │   └── index.ts         # TypeScript tipleri
│   │   └── data/
│   │       └── bodyData.ts      # Vücut bölgeleri verisi
│   ├── package.json
│   └── vite.config.ts
├── frontend-old/            # Eski basit frontend (yedek)
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
source venv/bin/activate
pip install -r requirements.txt
# .env dosyasına GROQ_API_KEY ekle
```

### 3. Frontend Kurulumu (React)

```bash
cd frontend-new
npm install
npm run dev
```

### 4. Uygulamayı Çalıştır

**Terminal 1 - Backend:**
```bash
cd backend && ./venv/bin/python -m uvicorn app.main:app --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend-new && npm run dev
```

Tarayıcıda aç: http://localhost:3000

## 📡 API - Yapısal Semptom Context

**POST /chat** - Yapısal semptom bilgisi ile istek:

```json
{
  "message": "Sol kaval kemiğimde ağrı var",
  "history": [],
  "symptom_context": {
    "region": "left_shin",
    "region_name_tr": "Sol Kaval Kemiği",
    "region_name_en": "Left Shin (Tibia)",
    "symptom": "pain",
    "symptom_name_tr": "Ağrı",
    "symptom_name_en": "Pain",
    "severity_0_10": 7,
    "onset": "2_3_days",
    "trigger": "after_running",
    "red_flags": ["cannot_bear_weight"]
  }
}
```

## 🎨 Vücut Bölgeleri

24 farklı bölge: Baş, Boyun, Göğüs, Karın, Üst/Alt Sırt, Omuzlar, Üst Kollar, Ön Kollar, Eller, Kalçalar, Üst Bacaklar, Dizler, Kaval Kemikleri, Ayaklar

## 🚨 Semptom Türleri

Ağrı 🤕 | Şişlik 🔴 | Uyuşma 😶 | Karıncalanma ✨ | Morluk 💜 | Kesik 🩹 | Yanık 🔥 | Döküntü 🔶 | Sertlik 🔒 | Güçsüzlük 💫 | Kramp ⚡ | Kanama 🩸

---

🏥 **Uyarı:** Bu uygulama sadece bilgilendirme amaçlıdır. Acil durumlarda **112**'yi arayın!

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
