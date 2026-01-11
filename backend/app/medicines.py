"""
Türkçe İlaç Sözlüğü
Tek kaynak - hem health_filter hem main.py tarafından kullanılır
"""

# Türkçe ilaç isimleri → İngilizce karşılıkları sözlüğü
# Bu sözlük çeviriden ÖNCE uygulanır, böylece LLM ilaç isimlerini doğru anlar
TURKISH_MEDICINE_DICTIONARY = {
    # Ağrı kesiciler / Ateş düşürücüler (Parasetamol bazlı)
    "parol": "paracetamol (Turkish brand: Parol)",
    "tylol": "paracetamol (Turkish brand: Tylol)",
    "minoset": "paracetamol (Turkish brand: Minoset)",
    "vermidon": "paracetamol (Turkish brand: Vermidon)",
    "calpol": "paracetamol (Turkish brand: Calpol)",
    "aferin": "paracetamol with caffeine (Turkish brand: Aferin) - pain reliever and fever reducer",
    "aferin forte": "paracetamol with caffeine high dose (Turkish brand: Aferin Forte)",
    "parasedamol": "paracetamol",
    "parasetamol": "paracetamol",
    
    # NSAIDs - İbuprofen bazlı
    "nurofen": "ibuprofen (brand: Nurofen)",
    "pedifen": "ibuprofen (Turkish brand: Pedifen)",
    "brufen": "ibuprofen (brand: Brufen)",
    
    # NSAIDs - Naproksen bazlı
    "apranax": "naproxen sodium (Turkish brand: Apranax)",
    "naprosyn": "naproxen (brand: Naprosyn)",
    "opraks": "naproxen (Turkish brand: Opraks)",
    
    # NSAIDs - Diklofenak bazlı
    "voltaren": "diclofenac (brand: Voltaren)",
    "dikloron": "diclofenac (Turkish brand: Dikloron)",
    "diclomec": "diclofenac (Turkish brand: Diclomec)",
    
    # NSAIDs - Diğer
    "majezik": "flurbiprofen (Turkish brand: Majezik)",
    "arveles": "dexketoprofen (Turkish brand: Arveles)",
    "dexofen": "dexketoprofen (Turkish brand: Dexofen)",
    
    # Aspirin
    "aspirin": "aspirin (acetylsalicylic acid)",
    "disprin": "aspirin (brand: Disprin)",
    "ecopirin": "aspirin (Turkish brand: Ecopirin)",
    "coraspin": "low-dose aspirin (Turkish brand: Coraspin)",
    
    # Antibiyotikler - Penisilin grubu
    "augmentin": "amoxicillin-clavulanate (brand: Augmentin)",
    "amoklavin": "amoxicillin-clavulanate (Turkish brand: Amoklavin)",
    "klamoks": "amoxicillin-clavulanate (Turkish brand: Klamoks)",
    "amoksisilin": "amoxicillin",
    "duocid": "ampicillin-sulbactam (Turkish brand: Duocid)",
    
    # Antibiyotikler - Florokinolon grubu
    "cipro": "ciprofloxacin (brand: Cipro)",
    "ciproxin": "ciprofloxacin (brand: Ciproxin)",
    "siprofloksasin": "ciprofloxacin",
    
    # Antibiyotikler - Makrolid grubu
    "klacid": "clarithromycin (brand: Klacid)",
    "macrol": "clarithromycin (Turkish brand: Macrol)",
    "azitromisin": "azithromycin",
    "zitromax": "azithromycin (brand: Zithromax)",
    "azro": "azithromycin (Turkish brand: Azro)",
    
    # Antibiyotikler - Sefalosporin grubu
    "iesef": "cefixime (Turkish brand: İesef)",
    "cefaks": "cefuroxime (Turkish brand: Cefaks)",
    "cefixime": "cefixime",
    "sefuroksim": "cefuroxime",
    "suprax": "cefixime (brand: Suprax)",
    
    # Mide ilaçları - PPI
    "nexium": "esomeprazole (brand: Nexium)",
    "lansor": "lansoprazole (Turkish brand: Lansor)",
    "controloc": "pantoprazole (brand: Controloc)",
    "pantpas": "pantoprazole (Turkish brand: Pantpas)",
    "losec": "omeprazole (brand: Losec)",
    
    # Mide ilaçları - Antasitler
    "gaviscon": "alginate antacid (brand: Gaviscon)",
    "rennie": "calcium carbonate antacid (brand: Rennie)",
    "talcid": "hydrotalcite antacid (brand: Talcid)",
    "maalox": "aluminum-magnesium antacid (brand: Maalox)",
    
    # Mide ilaçları - Antiemetik
    "motilium": "domperidone (brand: Motilium)",
    "metpamid": "metoclopramide (Turkish brand: Metpamid)",
    
    # Spazmolitikler
    "buscopan": "hyoscine butylbromide (brand: Buscopan)",
    "spazmol": "hyoscine (Turkish brand: Spazmol)",
    
    # Alerji ilaçları
    "zyrtec": "cetirizine (brand: Zyrtec)",
    "aerius": "desloratadine (brand: Aerius)",
    "xyzal": "levocetirizine (brand: Xyzal)",
    "cetrin": "cetirizine (brand: Cetrin)",
    "allerset": "cetirizine (Turkish brand: Allerset)",
    "setrizin": "cetirizine",
    "loratadin": "loratadine",
    "desloratadin": "desloratadine",
    "histazin": "cetirizine (Turkish brand: Histazin)",
    "avil": "pheniramine (brand: Avil)",
    
    # Grip / Soğuk algınlığı kombinasyonları
    "gripin": "paracetamol-phenylephrine-chlorpheniramine (Turkish brand: Gripin)",
    "tylol hot": "paracetamol combination for cold (Turkish brand: Tylol Hot)",
    "theraflu": "paracetamol combination for cold (brand: Theraflu)",
    "fervex": "paracetamol combination for cold (brand: Fervex)",
    "coldrex": "paracetamol combination for cold (brand: Coldrex)",
    "deflu": "paracetamol-pseudoephedrine (Turkish brand: Deflu)",
    
    # Burun sprayleri
    "otrivin": "xylometazoline nasal spray (brand: Otrivin)",
    "iliadin": "oxymetazoline nasal spray (Turkish brand: İliadin)",
    
    # Öksürük ilaçları
    "prospan": "ivy leaf extract cough syrup (brand: Prospan)",
    "mucosolvan": "ambroxol (brand: Mucosolvan)",
    "bromeks": "bromhexine (Turkish brand: Bromeks)",
    "tusso": "dextromethorphan cough syrup (Turkish brand: Tusso)",
    "sudafed": "pseudoephedrine (brand: Sudafed)",
    "sinecod": "butamirate cough suppressant (brand: Sinecod)",
    
    # Kas gevşeticiler
    "muscoril": "thiocolchicoside muscle relaxant (brand: Muscoril)",
    "myoril": "thiocolchicoside (Turkish brand: Myoril)",
    "sirdalud": "tizanidine muscle relaxant (brand: Sirdalud)",
    "tizanidin": "tizanidine",
    
    # Vitaminler
    "supradyn": "multivitamin (brand: Supradyn)",
    "centrum": "multivitamin (brand: Centrum)",
    "pharmaton": "multivitamin with ginseng (brand: Pharmaton)",
    "berocca": "B vitamins and vitamin C (brand: Berocca)",
    "elevit": "prenatal vitamins (brand: Elevit)",
    "bemiks": "B complex vitamins (Turkish brand: Bemiks)",
    "benexol": "B vitamins (Turkish brand: Benexol)",
    
    # Astım ilaçları
    "ventolin": "salbutamol inhaler (brand: Ventolin)",
    "seretide": "fluticasone-salmeterol inhaler (brand: Seretide)",
    "symbicort": "budesonide-formoterol inhaler (brand: Symbicort)",
    
    # Tansiyon ilaçları
    "beloc": "metoprolol (Turkish brand: Beloc)",
    "concor": "bisoprolol (brand: Concor)",
    "norvasc": "amlodipine (brand: Norvasc)",
    "amlodipin": "amlodipine",
    
    # Kolesterol ilaçları
    "lipitor": "atorvastatin (brand: Lipitor)",
    "crestor": "rosuvastatin (brand: Crestor)",
    "atorvastatin": "atorvastatin",
    
    # Diyabet ilaçları
    "metformin": "metformin (for diabetes)",
    "glucophage": "metformin (brand: Glucophage)",
    "diamicron": "gliclazide (brand: Diamicron)",
    
    # Kan sulandırıcılar
    "coumadin": "warfarin blood thinner (brand: Coumadin)",
    "plavix": "clopidogrel blood thinner (brand: Plavix)",
    "kardegic": "low-dose aspirin (brand: Kardegic)",
    
    # Psikiyatrik ilaçlar
    "xanax": "alprazolam anti-anxiety (brand: Xanax)",
    "lexapro": "escitalopram antidepressant (brand: Lexapro)",
    "cipralex": "escitalopram antidepressant (brand: Cipralex)",
    "prozac": "fluoxetine antidepressant (brand: Prozac)",
    "lustral": "sertraline antidepressant (brand: Lustral)",
    
    # Cilt kremleri
    "fucidin": "fusidic acid antibiotic cream (brand: Fucidin)",
    "bactroban": "mupirocin antibiotic cream (brand: Bactroban)",
    "triderm": "betamethasone-clotrimazole cream (brand: Triderm)",
    "advantan": "methylprednisolone cream (brand: Advantan)",
    "bepanthen": "dexpanthenol healing cream (brand: Bepanthen)",
}

# Yaygın yanlış yazımlar → doğru ilaç ismi
MEDICINE_TYPOS = {
    # Parol varyasyonları
    "paroll": "parol", "parool": "parol", "paral": "parol", "parole": "parol",
    "porol": "parol", "prol": "parol",
    
    # Aferin varyasyonları
    "afeirin": "aferin", "afferin": "aferin", "afren": "aferin", "aferın": "aferin",
    "afirin": "aferin", "eferın": "aferin", "aferrin": "aferin",
    
    # Tylol varyasyonları
    "tilol": "tylol", "tyloll": "tylol", "tyloL": "tylol", "taylol": "tylol",
    "tılol": "tylol", "tiloll": "tylol",
    
    # Apranax varyasyonları
    "apranaks": "apranax", "apranaksi": "apranax", "apranx": "apranax",
    "apranak": "apranax", "aprenax": "apranax", "apranex": "apranax",
    
    # Nurofen varyasyonları
    "norofen": "nurofen", "nurafen": "nurofen", "nurofен": "nurofen",
    "nuroffen": "nurofen", "neurofen": "nurofen",
    
    # Majezik varyasyonları
    "majezik": "majezik", "macezik": "majezik", "majezık": "majezik",
    "mecezik": "majezik", "majezic": "majezik",
    
    # Augmentin varyasyonları
    "ogmentin": "augmentin", "agmentin": "augmentin", "augmantin": "augmentin",
    "augmanten": "augmentin", "ogmanten": "augmentin",
    
    # Gripin varyasyonları
    "giripin": "gripin", "gриpin": "gripin", "gribin": "gripin",
    
    # Arveles varyasyonları
    "arvales": "arveles", "arvelez": "arveles", "arweles": "arveles",
    
    # Voltaren varyasyonları
    "woltaren": "voltaren", "voltaran": "voltaren", "valtaren": "voltaren",
    
    # Aspirin varyasyonları
    "asprın": "aspirin", "asprin": "aspirin", "asprin": "aspirin",
    
    # Panadol → Parol eşleştirmesi (farklı ülkelerde farklı isim)
    "panadol": "parol",
}

# İlaç marka isimleri seti (health_filter için)
MEDICINE_BRANDS = set(TURKISH_MEDICINE_DICTIONARY.keys())
