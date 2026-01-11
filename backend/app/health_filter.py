"""
Sağlık Filtresi Modülü
- Keyword bazlı sağlık kontrolü
- Acil durum tespiti
"""

import re
from typing import Tuple

# İlaç isimlerini tek kaynaktan al
from app.medicines import MEDICINE_BRANDS

# Sağlık DIŞI anahtar kelimeler - İKİ SEVİYE
# HARD: Kesinlikle sağlık dışı - direkt NO
# SOFT: Bağlama bağlı - sadece puan katar, direkt NO yaptırmaz

HARD_NON_HEALTH_KEYWORDS = {
    # Yemek/Tarif (sağlık diyeti değilse)
    "tarif", "tarifi", "yemek tarifi", "nasıl yapılır yemek", "malzemeler",
    "pişir", "pişirme", "fırın", "tencere", "tava", "ocak",
    "makarna", "pilav", "çorba tarifi", "kek", "pasta", "kurabiye",
    "yemek yap", "aşçı", "mutfak", "restoran önerisi",
    
    # Spor/Fitness (sağlık dışı bağlam)
    "maç skoru", "maç sonucu", "lig", "şampiyon",
    "transfer", "teknik direktör", "gol", "penaltı",
    
    # Teknoloji
    "telefon önerisi", "bilgisayar önerisi", "laptop", "tablet",
    "uygulama önerisi", "oyun önerisi", "yazılım", "programlama",
    "kod yaz", "python", "javascript",
    
    # Astronomi/Uzay/Bilim
    "kara delik", "yıldız nasıl", "gezegen", "uzay", "galaksi",
    "büyük patlama", "big bang", "mars", "ay'a", "nasa",
    "evren nasıl", "güneş sistemi", "asteroid", "kuyruklu yıldız",
    
    # Matematik/Fizik
    "denklem", "integral", "türev", "fizik formül",
    
    # Tarih/Coğrafya
    "dünya savaşı", "osmanlı", "tarihte", "hangi yılda",
    "başkenti", "nüfusu kaç", "hangi kıtada",
    
    # Eğlence
    "film önerisi", "dizi önerisi", "kitap önerisi", "müzik önerisi",
    "şarkı sözleri",
    
    # Politika/Finans
    "politika", "seçim", "parti", "cumhurbaşkanı", "başbakan",
    "borsa", "dolar", "euro", "kripto", "bitcoin",
    
    # Astroloji
    "astroloji", "burç", "fal", "rüya tabiri",
}

# SOFT: Bağlama bağlı kelimeler - sağlık içinde de geçebilir
SOFT_NON_HEALTH_KEYWORDS = {
    # Bunlar sağlık bağlamında da kullanılabilir
    "fiyat",  # ilaç fiyatı
    "ne kadar",  # ne kadar sürer (sağlık), ne kadar (fiyat)
    "kaç para",  # ilaç kaç para
    "ucuz", "pahalı",  # ucuz/pahalı ilaç
    "hava durumu", "hava nasıl", "sıcaklık kaç derece",  # ama genelde sağlık dışı
    "tatil", "otel", "uçak bileti", "seyahat",
    "araba", "otomobil", "motor", "benzin",
    "çeviri yap", "tercüme",
    "futbol", "basketbol",  # spor yaparken yaralanma olabilir
}

# Eski uyumluluk için birleşik set
NON_HEALTH_KEYWORDS = HARD_NON_HEALTH_KEYWORDS | SOFT_NON_HEALTH_KEYWORDS

# Selamlaşma kelimeleri - kategorilere ayrıldı
GREETING_HELLO = {
    "selam", "merhaba", "günaydın", "iyi günler", "iyi akşamlar",
    "hey", "sa", "slm", "mrb", "selamlar",
}

GREETING_HOWRU = {
    "nasılsın", "naber", "nasıl gidiyor", "ne haber", "nabır",
    "ne var ne yok", "naptın",
    # NOT: "nasıl hissediyorsun" sağlık bağlamında da kullanılabiliyor, bu yüzden çıkarıldı
}

GREETING_THANKS = {
    "teşekkür", "teşekkürler", "sağol", "sağ ol", "eyvallah",
    "çok teşekkürler", "teşekkür ederim", "minnettarim",
}

GREETING_BYE = {
    "görüşürüz", "hoşça kal", "bye", "bb", "hoşçakal",
    "iyi geceler", "kendine iyi bak",
}

GREETING_TRUST = {
    "sana güvenebilir miyim", "güvenilir misin", "sen gerçek doktor",
    "sen doktor musun", "sen kimsin", "ne yapabilirsin",
    "yapay zeka mısın", "robot musun", "sen nesin",
    "yeteneklerin", "ne biliyorsun",
}

# Tüm selamlaşmalar (genel kontrol için)
GREETING_KEYWORDS = GREETING_HELLO | GREETING_HOWRU | GREETING_THANKS | GREETING_BYE | GREETING_TRUST

# Sağlıkla ilgili anahtar kelimeler
HEALTH_KEYWORDS = {
    # Semptomlar - isim ve fiil çekimleri
    "ağrı", "ağrısı", "ağrıyor", "ağrıyorum", "ağrıyordu", "ağrır", "ağrımaya",
    "acı", "acıyor", "acıyorum", "acır",
    "sızı", "sızlıyor", "sızlama", "sızladı",
    "sancı", "sancılanıyor", "sancılandı",
    "yanma", "yanıyor", "yanıyorum", "yanar",
    "batma", "batıyor", "batıyorum",
    "baş ağrısı", "başım ağrıyor", "başı ağrıyor", "başımda ağrı",
    "karın ağrısı", "karnım ağrıyor", "karnımda ağrı",
    "göğüs ağrısı", "göğsüm ağrıyor", "göğsümde ağrı",
    "bel ağrısı", "belim ağrıyor", "belimde ağrı",
    "sırt ağrısı", "sırtım ağrıyor", "sırtımda ağrı",
    "ateş", "yüksek ateş", "ateşim var", "ateşim çıktı", "ateşlenme",
    "titreme", "titriyorum", "titriyor", "titredi",
    "üşüme", "üşüyorum", "üşüyor",
    "öksürük", "öksürme", "öksürüyorum", "öksürüyor", "öksürdüm",
    "hapşırma", "hapşırıyorum", "hapşırdım",
    "burun akıntısı", "burun tıkanıklığı", "burnum akıyor", "burnum tıkalı",
    "bulantı", "bulantım var", "midem bulanıyor",
    "kusma", "kusuyorum", "kustu", "kustum",
    "mide bulantısı", "midem bulanıyor",
    "ishal", "ishale yakalandım", "ishal oldum",
    "kabızlık", "kabız oldum",
    "baş dönmesi", "başım dönüyor", "başım döndü",
    "sersemlik", "sersem hissediyorum",
    "bayılma", "bayılacak gibi", "bayıldım",
    "halsizlik", "halsizim", "halim yok",
    "yorgunluk", "yorgunum", "yoruldum", "yorgun hissediyorum",
    "kaşıntı", "kaşınıyor", "kaşınıyorum",
    "döküntü", "döküntüm var",
    "kızarıklık", "kızarıyor", "kızardı",
    "şişlik", "şiş", "şişti", "şişiyor", "şişmiş",
    "morarma", "morarıyor", "morardı",
    "nefes darlığı", "nefes alamıyorum", "nefes almak", "soluk", "soluk alamıyorum",
    "ödem", "şişme",
    "çarpıntı", "kalp çarpıntısı", "kalbim çarpıyor",
    "tansiyon", "tansiyonum yüksek", "tansiyonum düşük",
    "uyku problemi", "uykusuzluk", "uyku bozukluğu", "uyuyamıyorum",
    "kilo", "zayıflama", "kilo kaybı", "kilo aldım", "kilo verdim",
    "iştahsızlık", "iştahım yok",
    "kanama", "kan", "yara", "kanıyor", "kanadı",
    
    # Hastalıklar
    "hastalık", "rahatsızlık", "şikayet", "belirti", "semptom",
    "grip", "nezle", "soğuk algınlığı", "enfeksiyon", "virüs", "bakteri",
    "diyabet", "şeker hastalığı", "tansiyon", "hipertansiyon",
    "astım", "bronşit", "zatürre", "pnömoni",
    "kalp", "kalp hastalığı", "damar", "kolesterol",
    "kanser", "tümör",
    "alerji", "alerjik", "egzama", "sedef",
    "depresyon", "anksiyete", "kaygı", "stres", "panik atak",
    "migren", "vertigo",
    "gastrit", "ülser", "reflü", "mide",
    "böbrek", "karaciğer", "safra",
    "tiroid", "guatr",
    "artrit", "romatizma", "kireçlenme",
    "covid", "korona", "koronavirüs",
    
    # Tıbbi terimler
    "tedavi", "ilaç", "hap", "şurup", "krem", "merhem",
    "doktor", "hekim", "hastane", "klinik", "acil",
    "ameliyat", "operasyon", "cerrahi",
    "tahlil", "test", "tetkik", "röntgen", "mr", "tomografi", "ultrason",
    "aşı", "aşılama",
    "reçete", "antibiyotik", "ağrı kesici",
    "vitamin", "mineral", "takviye",
    "tanı", "teşhis",
    "kronik", "akut",
    "bağışıklık", "immün",
    
    # Vücut bölgeleri (sağlık bağlamında)
    "boğaz", "bademcik", "kulak", "göz", "burun", "diş", "dişeti",
    "akciğer", "mide", "bağırsak", "kolon",
    "eklem", "kas", "kemik", "omurga",
    "cilt", "deri", "saç dökülme",
    
    # Sağlık soruları
    "ne yapmalı", "ne zaman doktora", "doktora gitmeli", "tehlikeli mi",
    "normal mi", "endişelenmeli", "acil mi", "ciddi mi",
    "bulaşıcı mı", "geçer mi", "ne kadar sürer",
    "iyi gelir", "zararlı mı", "yan etki",
    
    # İlaç kullanım soruları
    "ilaç almalı", "ilaç kullanmalı", "ilaç almam", "ilaç içmeli",
    "hangi ilaç", "ilaç önerisi", "ilaç tavsiye",
    "almalı mıyım", "içmeli miyim", "kullanmalı mıyım",
    "kaç tane", "kaç mg", "dozaj", "doz", "günde kaç",
    
    # NOT: İlaç markaları MEDICINE_BRANDS'den otomatik ekleniyor (aşağıda birleştiriliyor)
}

# HEALTH_KEYWORDS'e tüm ilaç markalarını ekle (tek kaynak: medicines.py)
HEALTH_KEYWORDS = HEALTH_KEYWORDS | MEDICINE_BRANDS

# Acil durum anahtar kelimeleri
EMERGENCY_KEYWORDS = {
    # Kalp krizi belirtileri
    "göğüs ağrısı": "Göğüs ağrısı kalp krizi belirtisi olabilir!",
    "göğsüme baskı": "Göğüs baskısı kalp krizi belirtisi olabilir!",
    "koluma yayılan ağrı": "Kola yayılan ağrı kalp krizi belirtisi olabilir!",
    "çene ağrısı ve terleme": "Bu belirtiler kalp krizi işareti olabilir!",
    
    # Felç belirtileri
    "yüzüm uyuşuyor": "Ani yüz uyuşması felç belirtisi olabilir!",
    "kolum uyuşuyor": "Ani kol uyuşması felç belirtisi olabilir!",
    "konuşamıyorum": "Ani konuşma bozukluğu felç belirtisi olabilir!",
    "bir tarafım uyuşuyor": "Vücudun bir tarafında uyuşma felç belirtisi olabilir!",
    "felç": "Felç şüphesi acil müdahale gerektirir!",
    
    # Solunum acilleri
    "nefes alamıyorum": "Nefes alamama acil müdahale gerektiren bir durumdur!",
    "boğuluyorum": "Boğulma hissi acil bir durumdur!",
    "nefessiz kaldım": "Nefes darlığı acil değerlendirme gerektirir!",
    
    # Ciddi kanamalar
    "çok kan kaybediyorum": "Ciddi kanama acil müdahale gerektirir!",
    "kan durmuyor": "Durdurulamayan kanama acil müdahale gerektirir!",
    
    # Bilinç kaybı
    "bayılıyorum": "Bayılma/bilinç kaybı acil değerlendirme gerektirir!",
    "bilincimi kaybediyorum": "Bilinç kaybı acil müdahale gerektirir!",
    
    # Ciddi alerjik reaksiyon
    "boğazım şişiyor": "Boğaz şişmesi anafilaksi belirtisi olabilir!",
    "dudaklarım şişiyor": "Dudak şişmesi ciddi alerjik reaksiyon olabilir!",
    "nefes almakta zorlanıyorum": "Nefes zorluğu acil değerlendirme gerektirir!",
    
    # Diğer aciller
    "intihar": "İntihar düşüncesi acil psikolojik destek gerektirir!",
    "kendime zarar": "Kendinize zarar verme düşüncesi acil destek gerektirir!",
    "zehirlendim": "Zehirlenme acil müdahale gerektirir!",
    "kaza geçirdim": "Kaza sonrası acil değerlendirme gerekebilir!",
}

EMERGENCY_RESPONSE_TEMPLATE = """🚨 **ACİL DURUM UYARISI** 🚨

{reason}

**HEMEN 112'Yİ ARAYIN!**

⏰ Zaman çok önemli! Acil sağlık ekibi size en hızlı şekilde ulaşacaktır.

📞 **112** - Acil Sağlık Hattı
📞 **182** - ALO Sağlık Danışma Hattı

Eğer konuşamıyorsanız, yanınızdaki birisinden yardım isteyin.

**Sakin kalmaya çalışın ve acil yardım gelene kadar hareket etmeyin (travma durumunda).**
"""


# Kısa kısaltmalar - bunlar için kelime sınırı kontrolü yapılacak
SHORT_GREETINGS = {"sa", "slm", "mrb", "bb"}


def is_greeting(message: str) -> bool:
    """
    Mesajın selamlaşma olup olmadığını kontrol eder.
    
    Args:
        message: Kullanıcı mesajı
        
    Returns:
        bool: Selamlaşma ise True
    """
    message_lower = message.lower().strip()
    words = set(re.findall(r'\b\w+\b', message_lower))
    
    # Kısa kısaltmalar için tam kelime eşleşmesi kontrol et
    for keyword in SHORT_GREETINGS:
        if keyword in words:
            return True
    
    # Diğer selamlaşma kelimeleri için substring kontrolü
    for keyword in GREETING_KEYWORDS - SHORT_GREETINGS:
        if keyword in message_lower:
            return True
    
    return False


def _check_keyword_in_message(keyword: str, message_lower: str, words: set) -> bool:
    """Keyword'ün mesajda olup olmadığını kontrol eder. Kısa kısaltmalar için kelime sınırı kontrolü yapar."""
    if keyword in SHORT_GREETINGS:
        return keyword in words
    return keyword in message_lower


def get_greeting_type(message: str) -> str:
    """
    Selamlaşma türünü döndürür: 'hello', 'howru', 'thanks', 'bye', 'trust', None
    """
    message_lower = message.lower().strip()
    words = set(re.findall(r'\b\w+\b', message_lower))
    
    # Önce trust kontrolü (daha uzun ifadeler)
    for keyword in GREETING_TRUST:
        if _check_keyword_in_message(keyword, message_lower, words):
            return 'trust'
    
    for keyword in GREETING_HOWRU:
        if _check_keyword_in_message(keyword, message_lower, words):
            return 'howru'
    
    for keyword in GREETING_THANKS:
        if _check_keyword_in_message(keyword, message_lower, words):
            return 'thanks'
    
    for keyword in GREETING_BYE:
        if _check_keyword_in_message(keyword, message_lower, words):
            return 'bye'
    
    for keyword in GREETING_HELLO:
        if _check_keyword_in_message(keyword, message_lower, words):
            return 'hello'
    
    return None


def count_non_health_signals(message: str) -> tuple:
    """
    Mesajdaki sağlık DIŞI sinyalleri sayar ve bulduklarını döndürür.
    Hard ve soft ayrımı yapar.
    
    Args:
        message: Kullanıcı mesajı
        
    Returns:
        tuple: (hard_sayı, soft_sayı, bulunan_hard, bulunan_soft)
    """
    message_lower = message.lower()
    found_hard = []
    found_soft = []
    
    for keyword in HARD_NON_HEALTH_KEYWORDS:
        if keyword in message_lower:
            found_hard.append(keyword)
    
    for keyword in SOFT_NON_HEALTH_KEYWORDS:
        if keyword in message_lower:
            found_soft.append(keyword)
    
    return len(found_hard), len(found_soft), found_hard, found_soft


def is_non_health_topic(message: str) -> bool:
    """
    Mesajın kesinlikle sağlık DIŞI olup olmadığını kontrol eder.
    Sadece HARD non-health keywords direkt reddettirir.
    
    Args:
        message: Kullanıcı mesajı
        
    Returns:
        bool: Kesinlikle sağlık dışı ise True
    """
    hard_count, _, _, _ = count_non_health_signals(message)
    return hard_count > 0


def count_health_signals(message: str) -> tuple:
    """
    Mesajdaki sağlık sinyallerini sayar ve bulduklarını döndürür.
    
    Args:
        message: Kullanıcı mesajı
        
    Returns:
        tuple: (keyword_sayısı, pattern_sayısı, bulunan_keywordler, eşleşen_patternler)
    """
    message_lower = message.lower()
    found_keywords = []
    found_patterns = []
    
    # Anahtar kelimeleri kontrol et
    for keyword in HEALTH_KEYWORDS:
        if keyword in message_lower:
            found_keywords.append(keyword)
    
    # Soru kalıplarını kontrol et - Türkçe semptom ifadeleri
    health_patterns = [
        (r"ne\s+yapmalı", "ne yapmalı"),
        (r"doktora\s+git", "doktora git"),
        (r"tedavi\s+(?:ne|nasıl)", "tedavi sorusu"),
        (r"ilaç\s+(?:öner|kullan)", "ilaç kullanımı"),
        (r"(?:bu|şu)\s+normal\s+mi", "normal mi sorusu"),
        (r"endişelen(?:meli|iyorum)", "endişe ifadesi"),
        (r"(?:ne|hangi)\s+(?:hastalık|rahatsızlık)", "hastalık sorusu"),
        (r"\b\w+[ıiuü]m\s+ağrıyor", "X ağrıyor kalıbı"),
        (r"\b\w+[ıiuü]mda\s+ağrı", "X'da ağrı kalıbı"),
        (r"\b\w+[ıiuü]m\s+(?:şiş|uyuş|yanıyor|acıyor|sızlıyor|zonkluyor)", "semptom fiili"),
        (r"(?:sağ|sol)\s+(?:taraf|kol|bacak|göz|kulak)\w*\s+ağrıyor", "sağ/sol ağrı"),
        (r"(?:ne|neden)\s+olmuş\s+olabilir", "ne olmuş olabilir"),
        (r"neden\s+(?:ağrıyor|acıyor|şişti|kanıyor)", "neden ağrıyor"),
        (r"(?:bir|iki|üç|\d+)\s+gündür\s+\w+", "süre ifadesi"),
        (r"(?:sabah|akşam|gece)\s+\w+\s+(?:ağrı|acı|şiş)", "zaman+ağrı"),
        (r"\w+(?:ım|im|um|üm)\s+(?:ağrıyor|acıyor|yanıyor|kanıyor|şişti)", "fiil kalıbı"),
    ]
    
    for pattern, name in health_patterns:
        if re.search(pattern, message_lower):
            found_patterns.append(name)
    
    return len(found_keywords), len(found_patterns), found_keywords, found_patterns


def is_health_related(message: str) -> bool:
    """
    Mesajın sağlıkla ilgili olup olmadığını keyword bazlı kontrol eder.
    Hard/soft non-health ayrımı yapar.
    
    Args:
        message: Kullanıcı mesajı
        
    Returns:
        bool: Sağlıkla ilgili ise True
    """
    message_lower = message.lower()
    
    # Sağlık sinyallerini say
    keyword_count, pattern_count, _, _ = count_health_signals(message_lower)
    health_score = keyword_count + pattern_count
    
    # Sağlık dışı sinyalleri say (hard ve soft ayrı)
    hard_count, soft_count, _, _ = count_non_health_signals(message_lower)
    
    # Sağlık sinyali varsa:
    # - Hard non-health'e rağmen sağlık sinyali >= hard ise kabul et
    # - Soft non-health sadece tie-breaker olarak kullanılır
    if health_score > 0:
        # Sağlık sinyali hard non-health'ten fazla veya eşitse → sağlık
        if health_score >= hard_count:
            return True
        # Hard non-health baskın → sağlık değil
        return False
    
    # Sağlık sinyali yoksa:
    # - Hard non-health varsa → kesin sağlık değil
    # - Sadece soft non-health varsa → belirsiz (False döner ama LLM'e gider)
    if hard_count > 0:
        return False
    
    # Hiçbir sinyal yoksa False
    return False


# Negasyon kelimeleri - acil durum false positive önleme
NEGATION_WORDS = ["yok", "değil", "olmadı", "yoktu", "geçti", "kalmadı", "bitmiş", "bitti"]


def has_negation_nearby(text: str, keyword: str, window: int = 30) -> bool:
    """
    Keyword'ün yakınında negasyon kelimesi var mı kontrol eder.
    Tüm keyword eşleşmelerini kontrol eder (sadece ilkini değil).
    
    Args:
        text: Tam metin
        keyword: Aranan anahtar kelime
        window: Karakter penceresi (önce ve sonra)
    """
    text_lower = text.lower()
    keyword_lower = keyword.lower()
    
    start = 0
    while True:
        # Keyword'ün pozisyonunu bul
        pos = text_lower.find(keyword_lower, start)
        if pos == -1:
            return False
        
        # Pencere içindeki metni al
        left = max(0, pos - window)
        right = min(len(text_lower), pos + len(keyword_lower) + window)
        context = text_lower[left:right]
        
        # Negasyon kontrolü
        if any(neg in context for neg in NEGATION_WORDS):
            return True
        
        # Sonraki eşleşmeye geç
        start = pos + len(keyword_lower)
    
    return False


def check_emergency_symptoms(message: str) -> Tuple[bool, str]:
    """
    Acil durum semptomlarını kontrol eder.
    Negasyon kontrolü ile false positive'leri önler.
    
    Args:
        message: Kullanıcı mesajı
        
    Returns:
        Tuple[bool, str]: (acil_mi, yanıt_mesajı)
    """
    message_lower = message.lower()
    
    for keyword, reason in EMERGENCY_KEYWORDS.items():
        if keyword in message_lower:
            # Negasyon kontrolü - "göğüs ağrım yok" gibi durumları filtrele
            if has_negation_nearby(message, keyword):
                print(f"[EMERGENCY] '{keyword}' bulundu ama negasyon var, atlaniyor")
                continue
            return True, EMERGENCY_RESPONSE_TEMPLATE.format(reason=reason)
    
    # Çoklu acil belirti kontrolü
    emergency_indicators = [
        "ani", "şiddetli", "dayanılmaz", "çok kötü",
        "ilk kez", "hiç olmamıştı", "aniden başladı"
    ]
    
    serious_symptoms = [
        "ağrı", "baş dönmesi", "nefes", "uyuşma", "görme", "bilinç"
    ]
    
    has_indicator = any(ind in message_lower for ind in emergency_indicators)
    has_symptom = any(sym in message_lower for sym in serious_symptoms)
    
    if has_indicator and has_symptom:
        return True, EMERGENCY_RESPONSE_TEMPLATE.format(
            reason="Belirttiğiniz semptomlar acil değerlendirme gerektirebilir!"
        )
    
    return False, ""
