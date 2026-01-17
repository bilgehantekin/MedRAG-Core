"""
Mini Domain Test Suite
- check_health_domain_simple() için hızlı smoke test
- deterministic olmayan (LLM) durumlar için esnek assertion içerir

Çalıştır:
  python -m tests.domain_cases
"""

from dataclasses import dataclass
from typing import List, Set

from app.domain import check_health_domain_simple


@dataclass
class Case:
    id: str
    text: str
    expected: Set[str]  # {"YES"}, {"NO"}, {"UNCERTAIN"}, veya {"YES","UNCERTAIN"} gibi


CASES: List[Case] = [
    # -------------------------
    # CLEAR HEALTH (YES)
    # -------------------------
    Case("H01", "3 gündür başım ağrıyor, ne yapmalıyım?", {"YES"}),
    Case("H02", "Boğazım ağrıyor ve ateşim var.", {"YES"}),
    Case("H03", "Midem bulanıyor ve kusuyorum.", {"YES"}),
    Case("H04", "Kalbim hızlı atıyor gibi hissediyorum.", {"YES"}),
    Case("H05", "Dizimde şişlik var, yürürken ağrıyor.", {"YES"}),
    Case("H06", "Uyuyamıyorum, anksiyete gibi hissediyorum.", {"YES"}),
    Case("H07", "Kan tahlili sonucumda hemoglobin düşük çıktı, ne demek?", {"YES"}),
    Case("H08", "Amoksisilin kullandım, ishal yaptı. Normal mi?", {"YES"}),  # ilaç adı -> YES
    Case("H09", "Antibiyotik sonrası kaşıntı başladı.", {"YES"}),
    Case("H10", "Tansiyonum 16/10 çıktı, tehlikeli mi?", {"YES"}),

    # -------------------------
    # CLEAR NON-HEALTH (NO)
    # -------------------------
    Case("N01", "Galatasaray maç sonucu ne oldu?", {"NO"}),
    Case("N02", "React'te state yönetimini anlatır mısın?", {"NO"}),
    Case("N03", "Bugün İstanbul'da hava nasıl?", {"NO"}),
    Case("N04", "En iyi laptop önerin nedir?", {"NO"}),
    Case("N05", "Kredi kartı borcumu nasıl yapılandırırım?", {"NO"}),
    Case("N06", "Bana makarna tarifi verir misin?", {"NO"}),  # sağlık diyeti değilse

    # -------------------------
    # AMBIGUOUS / SHORT (UNCERTAIN ya da YES)
    # Burada model + heuristics farklı dönebilir. Bu yüzden esnek.
    # -------------------------
    Case("A01", "Kötüyüm.", {"UNCERTAIN", "YES"}),
    Case("A02", "İyi değilim.", {"UNCERTAIN", "YES"}),
    Case("A03", "Garip hissediyorum.", {"UNCERTAIN", "YES"}),
    Case("A04", "Başım var.", {"UNCERTAIN", "YES"}),  # eksik cümle ama body part geçiyor
    Case("A05", "Ne yapmalıyım?", {"UNCERTAIN", "YES"}),

    # -------------------------
    # EDGE CASES
    # -------------------------
    Case("E01", "", {"UNCERTAIN", "NO", "YES"}),  # boş input genelde endpoint'te zaten engelleniyor
    Case("E02", "  ", {"UNCERTAIN", "NO", "YES"}),
    Case("E03", "Parol", {"YES"}),  # ilaç tespiti -> YES (medicine_utils sözlüğüne bağlı)
    Case("E04", "D vitamini ne işe yarar?", {"YES"}),  # suplement/health
]


def run():
    ok = 0
    fail = 0

    print("=== Domain Smoke Test: check_health_domain_simple ===\n")

    for c in CASES:
        out = check_health_domain_simple(c.text)
        passed = out in c.expected

        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}  {c.id}  out={out:10s}  expected={sorted(list(c.expected))}  text='{c.text}'")

        if passed:
            ok += 1
        else:
            fail += 1

    print("\n=== Summary ===")
    print(f"PASS: {ok}")
    print(f"FAIL: {fail}")

    # CI gibi kullanmak istersen:
    # if fail > 0:
    #     raise SystemExit(1)


if __name__ == "__main__":
    run()
