# 🏥 3D Medical Chatbot - Sağlık Asistanı

Türkçe sağlık odaklı bilgilendirme chatbot'u. 3D insan modeli üzerinde etkileşimli bölge seçimi veya direkt sohbet ile AI destekli sağlık bilgilendirme.

> ⚠️ **Önemli:** Bu uygulama teşhis koymaz, sadece bilgilendirme ve yönlendirme yapar.

## 🎯 Özellikler

### İki Farklı Etkileşim Modu (v2.1)
Kullanıcılar şikayetlerini anlatmak için iki farklı yöntem seçebilir:

#### 🧍 3D Model ile Göster
- 3D insan modeli üzerinde tıklanabilir vücut bölgeleri
- 24 farklı vücut bölgesi (baş, boyun, göğüs, karın, kollar, bacaklar vb.)
- Yapısal semptom seçimi (ağrı, şişlik, uyuşma, morluk vb.)
- Şiddet skalası (0-10)
- Başlangıç zamanı ve tetikleyici seçimi
- Kırmızı bayrak (acil durum) işaretleme
- OrbitControls ile döndürme ve yakınlaştırma

#### 💬 Direkt Yazarak Anlat
- Serbest metin girişi ile doğal dil anlatımı
- Hızlı başlangıç - form doldurmadan sohbet
- Sorulu cevaplı interaktif diyalog

### Chatbot Özellikleri
- ✅ Streaming yanıt efekti (harf harf yazım animasyonu)
- ✅ Akıllı auto-scroll (kullanıcı yukarı bakarken scroll etmez)
- ✅ Sağlık sorularını yanıtlama
- ✅ Yapısal semptom context'i ile zenginleştirilmiş yanıtlar
- ✅ Türkçe dilbilgisine uygun otomatik mesaj oluşturma
- ✅ Sağlık dışı soruları filtreleme
- ✅ Acil durum tespiti ve yönlendirme
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

\`\`\`
medical_chatbot/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI ana uygulama
│   │   ├── health_filter.py # Sağlık filtresi
│   │   └── prompts.py       # LLM prompt şablonları
│   ├── requirements.txt
│   └── .env
├── frontend-3d/             # React + Three.js frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── HumanModel.tsx   # 3D insan modeli
│   │   │   ├── Scene3D.tsx      # Three.js sahne
│   │   │   ├── SymptomPanel.tsx # Semptom seçim paneli
│   │   │   └── ChatPanel.tsx    # Chat arayüzü (streaming)
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
\`\`\`

## 🚀 Kurulum

### 1. Groq API Key Alın

1. [Groq Console](https://console.groq.com/)'a gidin
2. Ücretsiz hesap oluşturun
3. API Keys bölümünden yeni bir key oluşturun

### 2. Backend Kurulumu

\`\`\`bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# .env dosyası oluşturun
echo "GROQ_API_KEY=your_api_key_here" > .env
\`\`\`

### 3. Frontend Kurulumu

\`\`\`bash
cd frontend-3d
npm install
\`\`\`

### 4. Uygulamayı Çalıştır

**Terminal 1 - Backend:**
\`\`\`bash
cd backend && source venv/bin/activate && python -m uvicorn app.main:app --port 8000
\`\`\`

**Terminal 2 - Frontend:**
\`\`\`bash
cd frontend-3d && npm run dev
\`\`\`

Tarayıcıda aç: http://localhost:3000

## 📡 API Endpoints

### POST /chat
Yapısal semptom bilgisi ile istek:

\`\`\`json
{
  "message": "Sol kaval kemiğimde ağrı var. Şiddeti 10 üzerinden 7. 2-3 gündür devam ediyor.",
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
\`\`\`

**Yanıt:**
\`\`\`json
{
  "response": "...",
  "is_emergency": false,
  "disclaimer": "⚠️ Bu bilgiler eğitim amaçlıdır..."
}
\`\`\`

### GET /health
API sağlık kontrolü

### GET /models
Mevcut Groq modellerini listele

## 🎨 Vücut Bölgeleri

24 farklı bölge: Baş, Boyun, Göğüs, Karın, Üst/Alt Sırt, Omuzlar, Üst Kollar, Ön Kollar, Eller, Kalçalar, Üst Bacaklar, Dizler, Kaval Kemikleri, Ayaklar

## 🚨 Semptom Türleri

| Semptom | İkon |
|---------|------|
| Ağrı | 🤕 |
| Şişlik | 🔴 |
| Uyuşma | 😶 |
| Karıncalanma | ✨ |
| Morluk | 💜 |
| Kesik | 🩹 |
| Yanık | 🔥 |
| Döküntü | 🔶 |
| Sertlik/Tutulma | 🔒 |
| Güçsüzlük | 💫 |
| Kramp | ⚡ |
| Kanama | 🩸 |

## 🛡️ Güvenlik Özellikleri

1. **Domain Filtresi:** Sağlık dışı sorular reddedilir
2. **Acil Durum Tespiti:** Kritik semptomlar için 112 yönlendirmesi
3. **Uyarı Mesajları:** Her yanıtta bilgilendirme disclaimeri
4. **Teşhis Engeli:** LLM teşhis koymamak üzere yapılandırılmış

## 📝 Sürüm Geçmişi

### v2.1 (Ocak 2026)
- ✨ Direkt chat modu eklendi
- ✨ Hoş geldin ekranında mod seçimi
- ✨ Streaming yanıt efekti (harf harf yazım)
- ✨ Akıllı auto-scroll
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

## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (\`git checkout -b feature/amazing-feature\`)
3. Commit edin (\`git commit -m 'Add amazing feature'\`)
4. Push edin (\`git push origin feature/amazing-feature\`)
5. Pull Request açın

---

⚠️ **Uyarı:** Bu uygulama sadece bilgilendirme amaçlıdır. Tıbbi tavsiye yerine geçmez. Acil durumlarda **112**'yi arayın!
