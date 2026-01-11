# 🏥 3D Medical Chatbot

Türkçe sağlık bilgilendirme chatbot'u. 3D insan modeli veya serbest sohbet ile AI destekli sağlık yönlendirme.

> ⚠️ Bu uygulama teşhis koymaz, sadece bilgilendirme yapar.

![Hoş Geldin Ekranı](docs/screenshots/welcome-screen.png)

## ✨ Özellikler

- **🧍 3D Model Modu** - İnteraktif insan modeli üzerinde bölge seçimi
- **💬 Chat Modu** - Doğal dil ile serbest sohbet
- **🚨 Acil Durum Tespiti** - Kritik semptomlar için 112 yönlendirmesi
- **🔒 Sağlık Filtresi** - Sadece sağlık konularına yanıt

## 🛠️ Teknoloji

| Frontend | Backend |
|----------|---------|
| React 18 + TypeScript | FastAPI |
| Three.js (R3F) | Groq LLM (Llama 3.3) |
| Zustand | Deep Translator |
| Tailwind CSS | Pydantic |

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

## 📁 Yapı

```
medical_chatbot/
├── backend/
│   └── app/
│       ├── main.py           # API endpoints
│       ├── health_filter.py  # Sağlık/acil durum filtresi
│       ├── medicines.py      # İlaç veritabanı
│       └── prompts.py        # LLM promptları
├── frontend-3d/
│   └── src/
│       ├── components/       # React bileşenleri
│       ├── store/            # Zustand state
│       └── data/             # Vücut bölgeleri
└── docs/screenshots/
```

## 📝 Lisans

MIT License

---

⚠️ **Tıbbi tavsiye yerine geçmez. Acil durumlarda 112'yi arayın!**
