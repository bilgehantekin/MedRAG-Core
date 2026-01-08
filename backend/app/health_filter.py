"""
Sağlık Filtresi Modülü
- Keyword bazlı sağlık kontrolü
- Acil durum tespiti
"""

import re
from typing import Tuple

# Sağlık DIŞI anahtar kelimeler - bunlar varsa direkt reddet
NON_HEALTH_KEYWORDS = {
    # Yemek/Tarif
    "tarif", "tarifi", "yemek tarifi", "nasıl yapılır yemek", "malzemeler",
    "pişir", "pişirme", "fırın", "tencere", "tava", "ocak",
    "makarna", "pilav", "çorba tarifi", "kek", "pasta", "kurabiye",
    "yemek yap", "aşçı", "mutfak", "restoran önerisi",
    
    # Spor/Fitness (sağlık dışı bağlam)
    "maç skoru", "maç sonucu", "lig", "şampiyon", "futbol", "basketbol",
    "transfer", "teknik direktör", "gol", "penaltı",
    
    # Teknoloji
    "telefon önerisi", "bilgisayar önerisi", "laptop", "tablet",
    "uygulama önerisi", "oyun önerisi", "yazılım", "programlama",
    "kod yaz", "python", "javascript",
    
    # Genel
    "hava durumu", "hava nasıl", "sıcaklık kaç derece",
    "film önerisi", "dizi önerisi", "kitap önerisi", "müzik önerisi",
    "şarkı sözleri", "çeviri yap", "tercüme",
    "fiyat", "ne kadar", "kaç para", "ucuz", "pahalı",
    "tatil", "otel", "uçak bileti", "seyahat",
    "araba", "otomobil", "motor", "benzin",
    "politika", "seçim", "parti", "cumhurbaşkanı", "başbakan",
    "borsa", "dolar", "euro", "kripto", "bitcoin",
    "astroloji", "burç", "fal", "rüya tabiri",
    
    # Astronomi/Uzay/Bilim
    "kara delik", "yıldız nasıl", "gezegen", "uzay", "galaksi",
    "büyük patlama", "big bang", "mars", "ay'a", "nasa",
    "evren nasıl", "güneş sistemi", "asteroid", "kuyruklu yıldız",
    
    # Matematik/Fizik
    "denklem", "integral", "türev", "fizik formül",
    
    # Tarih/Coğrafya
    "dünya savaşı", "osmanlı", "tarihte", "hangi yılda",
    "başkenti", "nüfusu kaç", "hangi kıtada",
}

# Selamlaşma kelimeleri - kategorilere ayrıldı
GREETING_HELLO = {
    "selam", "merhaba", "günaydın", "iyi günler", "iyi akşamlar",
    "hey", "sa", "slm", "mrb", "selamlar",
}

GREETING_HOWRU = {
    "nasılsın", "naber", "nasıl gidiyor", "ne haber", "nabır",
    "ne var ne yok", "naptın", "nasıl hissediyorsun",
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
    # Semptomlar
    "ağrı", "ağrısı", "acı", "sızı", "sancı", "yanma", "batma",
    "baş ağrısı", "karın ağrısı", "göğüs ağrısı", "bel ağrısı", "sırt ağrısı",
    "ateş", "yüksek ateş", "titreme", "üşüme",
    "öksürük", "öksürme", "hapşırma", "burun akıntısı", "burun tıkanıklığı",
    "bulantı", "kusma", "mide bulantısı", "ishal", "kabızlık",
    "baş dönmesi", "sersemlik", "bayılma", "halsizlik", "yorgunluk",
    "kaşıntı", "döküntü", "kızarıklık", "şişlik", "morarma",
    "nefes darlığı", "nefes almak", "soluk", "ödem",
    "çarpıntı", "kalp çarpıntısı", "tansiyon",
    "uyku problemi", "uykusuzluk", "uyku bozukluğu",
    "kilo", "zayıflama", "kilo kaybı", "iştahsızlık",
    "kanama", "kan", "yara",
    
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
}

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


def is_greeting(message: str) -> bool:
    """
    Mesajın selamlaşma olup olmadığını kontrol eder.
    
    Args:
        message: Kullanıcı mesajı
        
    Returns:
        bool: Selamlaşma ise True
    """
    message_lower = message.lower().strip()
    
    # Kısa selamlaşma kontrolü
    for keyword in GREETING_KEYWORDS:
        if keyword in message_lower:
            return True
    
    return False


def get_greeting_type(message: str) -> str:
    """
    Selamlaşma türünü döndürür: 'hello', 'howru', 'thanks', 'bye', 'trust', None
    """
    message_lower = message.lower().strip()
    
    # Önce trust kontrolü (daha uzun ifadeler)
    for keyword in GREETING_TRUST:
        if keyword in message_lower:
            return 'trust'
    
    for keyword in GREETING_HOWRU:
        if keyword in message_lower:
            return 'howru'
    
    for keyword in GREETING_THANKS:
        if keyword in message_lower:
            return 'thanks'
    
    for keyword in GREETING_BYE:
        if keyword in message_lower:
            return 'bye'
    
    for keyword in GREETING_HELLO:
        if keyword in message_lower:
            return 'hello'
    
    return None


def is_non_health_topic(message: str) -> bool:
    """
    Mesajın kesinlikle sağlık DIŞI olup olmadığını kontrol eder.
    
    Args:
        message: Kullanıcı mesajı
        
    Returns:
        bool: Sağlık dışı ise True
    """
    message_lower = message.lower()
    
    for keyword in NON_HEALTH_KEYWORDS:
        if keyword in message_lower:
            return True
    
    return False


def is_health_related(message: str) -> bool:
    """
    Mesajın sağlıkla ilgili olup olmadığını keyword bazlı kontrol eder.
    
    Args:
        message: Kullanıcı mesajı
        
    Returns:
        bool: Sağlıkla ilgili ise True
    """
    message_lower = message.lower()
    
    # Önce sağlık dışı mı kontrol et
    if is_non_health_topic(message_lower):
        return False
    
    # Anahtar kelimeleri kontrol et
    for keyword in HEALTH_KEYWORDS:
        if keyword in message_lower:
            return True
    
    # Soru kalıplarını kontrol et
    health_patterns = [
        r"ne\s+yapmalı",
        r"doktora\s+git",
        r"tedavi\s+(?:ne|nasıl)",
        r"ilaç\s+(?:öner|kullan)",
        r"(?:bu|şu)\s+normal\s+mi",
        r"endişelen(?:meli|iyorum)",
        r"(?:ne|hangi)\s+(?:hastalık|rahatsızlık)",
    ]
    
    for pattern in health_patterns:
        if re.search(pattern, message_lower):
            return True
    
    return False


def check_emergency_symptoms(message: str) -> Tuple[bool, str]:
    """
    Acil durum semptomlarını kontrol eder.
    
    Args:
        message: Kullanıcı mesajı
        
    Returns:
        Tuple[bool, str]: (acil_mi, yanıt_mesajı)
    """
    message_lower = message.lower()
    
    for keyword, reason in EMERGENCY_KEYWORDS.items():
        if keyword in message_lower:
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
