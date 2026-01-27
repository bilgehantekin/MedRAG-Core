# 🏥 3D Medical Chatbot - Sağlık Asistanı

Türkçe sağlık odaklı bilgilendirme chatbot'u. 3D insan modeli üzerinde etkileşimli bölge seçimi veya direkt sohbet ile AI destekli sağlık bilgilendirme.

> ⚠️ **Önemli:** Bu uygulama teşhis koymaz, sadece bilgilendirme ve yönlendirme yapar.

## 📸 Ekran Görüntüleri

### Hoş Geldin Ekranı
Kullanıcılar iki farklı mod arasında seçim yapabilir: 3D Model ile göster veya Direkt yazarak anlat.

![Hoş Geldin Ekranı](docs/screenshots/welcome-screen.png)

### 3D Model ile Bölge Seçimi
İnteraktif 3D insan modeli üzerinde ağrıyan veya şikayetin olduğu bölgeye tıklayarak başlayın.

![3D Model Görünümü](docs/screenshots/3d-model-view.png)

### Serbest Yazım Modu (Chat)
Chatbot'a doğrudan yazarak şikayetlerinizi kendi cümlelerinizle anlatın.

![Chat Paneli](docs/screenshots/chat-panel.png)

## ✨ Özellikler

### İki Farklı Etkileşim Modu
- **🧍 3D Model ile Göster** - 24 farklı vücut bölgesi, yapısal semptom seçimi, şiddet skalası
- **💬 Direkt Yazarak Anlat** - Serbest metin girişi ile doğal dil anlatımı

### Chatbot Özellikleri
- ✅ **RAG (Retrieval-Augmented Generation)** - Tıbbi bilgi tabanı ile zenginleştirilmiş yanıtlar
- ✅ **İlaç Görsel Analizi** - Fotoğraftan ilaç tanıma ve bilgi sunma (OCR + Groq LLM)
- ✅ Türkçe ilaç ismi tanıma (117+ ilaç, typo düzeltme, ek kırpma)
- ✅ Çoklu kelime ilaç tespiti (tylol hot, aferin forte)
- ✅ Sağlık dışı soruları filtreleme (hard/soft ayrımı)
- ✅ Acil durum tespiti ve 112 yönlendirmesi
- ✅ Groq LLM + Translation Pipeline (TR → EN → LLM → TR)
- ✅ LLM tabanlı yüksek kaliteli Türkçe çeviri

## 🛠️ Teknoloji Stack

| Frontend | Backend | RAG | Vision |
|----------|---------|-----|--------|
| React 18 + TypeScript | FastAPI | FAISS Vector Store | Tesseract OCR |
| Three.js (@react-three/fiber) | Groq LLM (Llama 3.3) | Sentence Transformers | OpenCV |
| Zustand | Deep Translator | Medical Knowledge Base | PIL/Pillow |
| Tailwind CSS | Pydantic | Semantic Search | Drug Database (32 ilaç) |

## 📁 Proje Yapısı

```
medical_chatbot/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI ana uygulama
│   │   ├── health_filter.py     # Sağlık/acil durum filtresi
│   │   ├── medicines.py         # İlaç sözlüğü (v2.0 - canonical isimler)
│   │   ├── medicine_utils.py    # İlaç işleme yardımcı fonksiyonları
│   │   ├── domain.py            # Domain sınıflandırma
│   │   ├── prompts.py           # LLM prompt şablonları
│   │   ├── vision_router.py     # İlaç görsel analizi endpoint'leri
│   │   ├── rag/                 # RAG Modülü
│   │   │   ├── router.py            # RAG API endpoint'leri
│   │   │   ├── rag_chain.py         # RAG zinciri ve LLM entegrasyonu
│   │   │   ├── knowledge_base.py    # Tıbbi bilgi tabanı (3-doküman chunking)
│   │   │   ├── vector_store.py      # FAISS vektör deposu
│   │   │   └── embeddings.py        # Sentence Transformers
│   │   └── vision/              # Vision Modülü (İlaç Görsel Analizi)
│   │       └── data/
│   │           └── drug_knowledge_base/
│   │               └── drugs.json   # Türkçe ilaç veritabanı (32 ilaç)
│   ├── scripts/
│   │   ├── etl/                         # ETL Pipeline
│   │   │   ├── fetch_openfda_targeted.py    # Hedefli OpenFDA veri çekme
│   │   │   ├── medlineplus_etl.py           # MedlinePlus veri çıkarma
│   │   │   ├── clean_enrich.py              # Temizleme ve zenginleştirme
│   │   │   ├── clean_medications_v2.py      # İlaç verisi temizleme
│   │   │   └── run_etl.py                   # Ana ETL çalıştırıcı
│   │   └── evaluate_rag.py              # RAG performans değerlendirme
│   └── data/
│       └── medical_knowledge/           # Tıbbi bilgi JSON dosyaları
│           ├── emergency.json                              # Acil durumlar
│           ├── medications.json                            # El yapımı ilaç verileri
│           ├── medications_openfda_only_tr.json            # OpenFDA hedefli (75 ilaç)
│           ├── symptoms_diseases.json                      # Semptom-hastalık
│           └── symptoms_diseases_medlineplus_tr_enriched.json  # MedlinePlus TR
├── frontend-3d/
│   └── src/
│       ├── components/
│       │   ├── HumanModel/      # 3D insan modeli
│       │   ├── ChatPanel/       # Sohbet paneli (+ görsel yükleme)
│       │   └── SymptomPanel/    # Semptom seçimi
│       ├── store/               # Zustand state management
│       ├── types/               # TypeScript tip tanımları
│       └── data/                # Vücut bölgeleri verisi
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

# Tesseract OCR kurulumu (İlaç görsel analizi için)
# macOS:
brew install tesseract tesseract-lang
# Ubuntu/Debian:
# sudo apt-get install tesseract-ocr tesseract-ocr-tur
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
| POST /rag/chat | RAG destekli sohbet endpoint'i |
| POST /rag/search | Bilgi tabanında arama |
| GET /rag/stats | RAG istatistikleri |
| POST /vision/analyze-image | İlaç görseli analizi (base64) |
| POST /vision/analyze-upload | İlaç görseli analizi (file upload) |
| GET /vision/health | Vision servisi sağlık kontrolü |
| GET /vision/drugs | İlaç veritabanı listesi |
| GET /health | API sağlık kontrolü |
| GET /models | Mevcut Groq modelleri |

## 🛡️ Güvenlik Özellikleri

- **Domain Filtresi:** Sağlık dışı sorular reddedilir
- **Acil Durum Tespiti:** Kritik semptomlar için 112 yönlendirmesi
- **Teşhis Engeli:** LLM teşhis koymamak üzere yapılandırılmış

## 📝 Sürüm Geçmişi

### v5.0 (Ocak 2026) - İlaç Görsel Analizi (Vision Module)
- ✨ **İlaç Fotoğrafından Tanıma** - Kullanıcı ilaç kutusu fotoğrafı yükleyerek bilgi alabilir
- ✨ Tesseract OCR ile metin çıkarma (Türkçe + İngilizce dil desteği)
- ✨ OpenCV ile görsel ön işleme (6 farklı işleme varyantı)
- ✨ Akıllı ilaç eşleştirme algoritması (fuzzy matching, OCR hata düzeltme)
- ✨ 32 Türkçe ilaç veritabanı (Parol, Nurofen, Augmentin, Aspirin vb.)
- ✨ Groq LLM ile bağlamsal ilaç bilgisi yanıtları
- ✨ Frontend'de görsel yükleme UI (önizleme, iptal, analiz)
- ✨ Kullanıcı sorusu desteği (görsel + soru kombinasyonu)
- ✨ `/vision/analyze-image` ve `/vision/analyze-upload` endpoint'leri
- ✨ Vision health check endpoint'i (`/vision/health`)

### v4.2 (Ocak 2026) - Performance Optimizasyonu & Streaming UX
- ✨ FAISS IVF index aktivasyonu (1000+ döküman için hızlı arama)
- ✨ Inverted keyword index ile O(1) keyword lookup (O(N) tarama yerine)
- ✨ SSE streaming optimizasyonu (10ms delay, 8-word chunks)
- ✨ RequestProfiler ile detaylı timing breakdown (t_translate_in, t_llm, t_retrieve vb.)
- ✨ Döküman duplikasyonu önleme (index diskten yüklendiyse JSON atlanıyor)
- ✨ Deep merge ile timing metriklerinin birleştirilmesi
- ✨ Streaming sırasında otomatik scroll (UX iyileştirmesi)

### v4.1 (Ocak 2026) - Hedefli OpenFDA ETL & Veri Optimizasyonu
- ✨ `fetch_openfda_targeted.py` - TURKISH_MEDICINE_DICTIONARY bazlı hedefli OpenFDA veri çekme
- ✨ Sadece Türkiye'de kullanılan ilaçların canonical isimleri için API sorgusu
- ✨ Full veri çekme (truncation kapalı) - chunking knowledge_base.py'de yapılıyor
- ✨ `medications_openfda_only_tr.json` - 75 hedefli ilaç kaydı (726 KB)
- ✨ Veri seti %83 küçültüldü (1.2 MB → 196 KB → 726 KB full)
- ✨ Gürültü filtreleme (WATER, DILUENT, PLACEBO vb. atlanıyor)
- ✨ `clean_medications_v2.py` - keywords_tr ve typos_tr temizleme
- ✨ Kullanılmayan veri dosyaları temp/ klasörüne arşivlendi
- ✨ 676 MB ham OpenFDA verisi silindi (openfda_drug_labels.json)

### v4.0 (Ocak 2026) - ETL Pipeline & RAG İyileştirmeleri
- ✨ MedlinePlus Health Topics XML veri çıkarma
- ✨ OpenFDA ilaç veritabanı entegrasyonu
- ✨ Türkçe çeviri ve zenginleştirme pipeline'ı
- ✨ Veri temizleme ve deduplication
- ✨ Yapılandırılmış JSON çıktı formatı
- ✨ evaluate_rag.py - Otomatik RAG performans değerlendirme scripti
- ✨ evaluation_test_set.json - Test soruları ve beklenen yanıtlar
- ✨ Zenginleştirilmiş Türkçe semptom-hastalık veri seti (MedlinePlus kaynaklı)
- ✨ knowledge_base.py defensive coding iyileştirmeleri
- ✨ rag_chain.py performans ve güvenilirlik iyileştirmeleri

### v3.3 (Ocak 2026) - RAG Bilgi Tabanı Güçlendirmesi
- ✨ Gerçek kaynak URL'leri ve metadata (source_name, source_url, retrieved_date)
- ✨ Güvenlik alanları: contraindications, drug_interactions, warnings, do_not
- ✨ Acil durum severity seviyeleri (CRITICAL/HIGH) ve call_emergency flag'leri
- ✨ Yapılandırılmış dosage_info ve tedavi rehberliği
- ✨ Türkçe konuşma dili ifadeleri (başım zonkluyor, midem kazınıyor)
- ✨ Yaygın Türkçe yazım hataları desteği (baş ağırısı, mide bulantsi)
- ✨ red_flags ve time_critical uyarıları
- ✨ Kalp krizi için aspirin güvenlik notu (kontrendikasyonlar ile)
- ✨ Ayrılmış keyword'ler: keywords_en, keywords_tr, typos_tr
- ✨ Riskli genel aspirin tavsiyesi kaldırıldı

### v3.2 (Ocak 2026) - İlaç İsim Pipeline Güçlendirmesi
- ✨ Mask-based ilaç ismi koruma (TR → EN → LLM → TR pipeline)
- ✨ Regex word boundary ile güvenli replace
- ✨ Kullanıcı yazımını koruma (`.title()` yerine `orig_word`)
- ✨ Jenerik ilaç isimleri (marka yerine, kontrollü maddeler çıkarıldı)

### v3.1 (Ocak 2026) - RAG İyileştirmeleri & Kod Kalitesi
- ✨ `medicine_utils.py` - Ortak ilaç işleme modülü (kod tekrarı önleme)
- ✨ `domain.py` - Ortak tri-state domain kontrolü (YES/NO/UNCERTAIN)
- ✨ Embedding normalization (cosine similarity eşdeğeri, daha iyi retrieval)
- ✨ Index uyumluluk kontrolü (`index_metadata.json` ile versiyon/model takibi)
- ✨ Vector store robustness (atomic load, dimension validation, isdir check)
- ✨ Double search düzeltmesi (performans optimizasyonu)
- ✨ RAG prompt iyileştirmeleri (verbatim kopyalama önleme, doğal dil)
- ✨ Follow-up domain gate (`/chat` ve `/rag/chat` tutarlılığı)
- ✨ Lazy init for Groq/Translator (startup crash önleme)
- ✨ Stricter classifier (max_tokens=3, stop newline, startswith parsing)
- ✨ Frontend drift önleme (`content_en` saklama ve geri gönderme)

### v3.0 (Ocak 2026) - RAG Entegrasyonu 
- ✨ **RAG (Retrieval-Augmented Generation)** sistemi eklendi
- ✨ FAISS vektör veritabanı ile semantic search
- ✨ Tıbbi bilgi tabanı (semptomlar, ilaçlar, acil durumlar)
- ✨ Sentence Transformers ile embedding
- ✨ Frontend'de RAG/Normal mod geçiş butonu
- ✨ LLM tabanlı yüksek kaliteli Türkçe çeviri
- ✨ Bağlamsal selamlaşma yanıtları (teşekkür, vedalaşma)
- ✨ İlk sağlık sorusu / takip sorusu ayrımı
- ✨ Kaynak gösterimi ile güvenilir bilgi sunumu

### v2.2 (Ocak 2026)
- ✨ `medicines.py` - İlaç veritabanı tek kaynakta toplandı
- ✨ Çoklu kelime ilaç tespiti (n-gram: tylol hot, aferin forte)
- ✨ Hard/soft non-health ayrımı 
- ✨ Acil durum negasyon kontrolü (false positive önleme)
- ✨ temperature=0 classifier (deterministik sınıflandırma)

### v2.1 (Ocak 2026)
- ✨ Direkt chat modu eklendi
- ✨ Hoş geldin ekranında mod seçimi
- ✨ Streaming yanıt efekti
- ✨ Türkçe dilbilgisine uygun mesaj formatları

### v2.0
- ✨ 3D insan modeli entegrasyonu
- ✨ Yapısal semptom raporlama
- ✨ 24 vücut bölgesi desteği

### v1.0
- ✨ Temel chatbot işlevselliği
- ✨ Sağlık filtresi
- ✨ Acil durum tespiti

## 📝 Lisans

MIT License

---

⚠️ **Uyarı:** Bu uygulama sadece bilgilendirme amaçlıdır. Tıbbi tavsiye yerine geçmez. Acil durumlarda **112**'yi arayın!
