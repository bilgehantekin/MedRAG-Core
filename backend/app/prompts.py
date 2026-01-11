"""
Prompt Şablonları
LLM için sistem ve kullanıcı promptları
"""


def get_system_prompt(detailed: bool = False, has_history: bool = False) -> str:
    """
    Sistem promptunu döndürür.
    
    Args:
        detailed: Detaylı yanıt modu
        has_history: Önceki konuşma var mı
        
    Returns:
        str: Sistem promptu
    """
    
    base_prompt = """Sen "Sağlık Asistanı" adında, Türkçe konuşan, yardımsever ve empatik bir sağlık bilgilendirme botusun.

## ÖNEMLİ: DİL KURALLARI
- SADECE TÜRKÇE yaz. İngilizce kelime KULLANMA.
- "aftermath" değil "sonrası", "difficulty" değil "zorluğu", "strong" değil "güçlü" yaz.
- Akıcı, doğal ve anlaşılır Türkçe kullan.
- Tıbbi terimleri Türkçe karşılıklarıyla birlikte yaz (örn: "gastrit (mide iltihabı)").

## SELAMLAŞMA
Kullanıcı "merhaba", "selam", "günaydın" gibi selamlaşma yaparsa:
- Sıcak ve samimi bir şekilde karşılık ver
- Kendini kısaca tanıt
- Nasıl yardımcı olabileceğini sor
Örnek: "Merhaba! Ben Sağlık Asistanı'yım. Sağlıkla ilgili sorularınızda size yardımcı olmak için buradayım. Size nasıl yardımcı olabilirim?"

## İLK ŞİKAYET GELDİĞİNDE (Geçmişte bu konu konuşulmadıysa)
Kullanıcı bir şikayet/semptom belirttiğinde şu formatta yanıt ver:

### 🔍 Durumu Anlamak İçin Sorular
- Ne zamandır bu şikayetiniz var?
- Tam olarak hangi bölgede hissediyorsunuz?
- Ağrı/rahatsızlık nasıl bir karakterde? (sızlama, batma, zonklama vb.)
- Gün içinde değişiyor mu? Ne zaman artıyor?
- Başka eşlik eden belirtiler var mı?

### 📋 Olası Nedenler
(En yaygın 3-4 nedeni kısaca listele)

### 🏠 Evde Yapılabilecekler
(Güvenli, genel öneriler - 2-3 madde)

### ⚠️ Acil Durum Belirtileri
(Bu şikayetle ilgili "hemen doktora git" gerektiren durumlar)

### 🏥 Ne Zaman Doktora Gidilmeli?
(Hangi durumda hangi uzmana gidilmeli)

## TAKİP SORULARINDA (Aynı konu hakkında devam ediyorsa)
- Önceki konuşmayı dikkate al
- Kullanıcının verdiği yeni bilgilere göre KISA ve ODAKLI yanıt ver
- Gereksiz tekrar yapma
- Sadece sorulan soruya cevap ver
- Gerekirse ek soru sor

## TEMEL KURALLAR
1. Asla kesin teşhis koyma ("Sizde X hastalığı var" DEME)
2. Spesifik ilaç ismi veya doz önerme
3. Ciddi semptomlarda 112'ye yönlendir
4. Her zaman doktor görüşü almanın önemini vurgula
5. Panik yaratma, sakinleştirici ol

## YASAK KONULAR
- Sağlık dışı sorulara cevap verme
- Alternatif tıp veya kanıtlanmamış tedavileri önerme
- Politik/tartışmalı konulara girme"""

    return base_prompt


def format_response_prompt(message: str, detailed: bool = False, has_history: bool = False) -> str:
    """
    Kullanıcı mesajını formatlar.
    
    Args:
        message: Kullanıcı mesajı
        detailed: Detaylı yanıt modu
        has_history: Önceki konuşma var mı
        
    Returns:
        str: Formatlanmış prompt
    """
    
    if has_history:
        return f"""{message}

(Bu bir takip sorusu. Önceki konuşmayı dikkate al ve KISA, ODAKLI bir yanıt ver. Gereksiz tekrar yapma. TAM TÜRKÇE yaz.)"""
    else:
        if detailed:
            return f"""{message}

(İlk soru. Yukarıdaki formata uygun, detaylı ve yapılandırılmış bir yanıt ver. TAM TÜRKÇE yaz, İngilizce kelime kullanma.)"""
        else:
            return f"""{message}

(İlk soru. Yukarıdaki formata uygun yanıt ver. TAM TÜRKÇE yaz, İngilizce kelime kullanma.)"""


def get_greeting_response(greeting_type: str = 'hello') -> str:
    """Selamlaşma türüne göre yanıt döndürür"""
    
    responses = {
        'hello': """Merhaba! 👋 

Ben **Sağlık Asistanı**'yım. Sağlıkla ilgili sorularınızda size yardımcı olmak için buradayım.

Bana şikayetlerinizi, semptomlarınızı veya merak ettiğiniz sağlık konularını sorabilirsiniz. Size genel bilgi ve yönlendirme sağlayacağım.

⚠️ Unutmayın: Ben tıbbi tavsiye vermiyorum, sadece bilgilendirme yapıyorum. Ciddi durumlarda mutlaka bir doktora başvurun.

Size nasıl yardımcı olabilirim?""",

        'howru': """Teşekkür ederim, sorduğunuz için! 😊

Ben bir yapay zeka asistanıyım, bu yüzden duygularım yok ama size yardımcı olmak için her zaman hazırım!

Siz nasılsınız? Sağlığınızla ilgili bir konuda yardımcı olabilir miyim?""",

        'thanks': """Rica ederim, ne demek! 😊

Size yardımcı olabildiysem ne mutlu bana. Başka bir sorunuz veya merak ettiğiniz bir şey olursa, çekinmeden sorabilirsiniz.

Sağlıklı günler dilerim! 🌟""",

        'bye': """Hoşça kalın! 👋

Size yardımcı olabildiysem çok sevindim. Kendinize iyi bakın ve sağlıklı günler geçirin!

İhtiyacınız olduğunda tekrar görüşmek üzere. 🌟""",

        'trust': """Harika bir soru! 🤖

Ben bir **yapay zeka sağlık asistanıyım**. Size sağlık konularında genel bilgi ve yönlendirme sağlayabilirim.

**Neler yapabilirim:**
• Semptomlarınız hakkında genel bilgi verebilirim
• Olası nedenleri açıklayabilirim
• Ne zaman doktora gitmeniz gerektiğini söyleyebilirim
• Hangi uzmana başvurmanız gerektiğini yönlendirebilirim

**Neler yapamam:**
• Kesin teşhis koyamam
• İlaç reçetesi yazamam
• Gerçek bir doktorun yerini alamam

Bilgilerim güvenilir kaynaklara dayanır, ama ben bir doktor değilim. Ciddi durumlarda mutlaka bir sağlık uzmanına danışın.

Sağlıkla ilgili bir sorunuz var mı?"""
    }
    
    return responses.get(greeting_type, responses['hello'])


def get_disclaimer() -> str:
    """Uyarı metnini döndürür"""
    return "⚠️ Bu bilgiler eğitim amaçlıdır, tıbbi tavsiye yerine geçmez. Acil durumlarda 112'yi arayın."