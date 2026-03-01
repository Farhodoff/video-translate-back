import re

def normalize_text(text: str) -> str:
    """
    O'zbek tili uchun matnni normallashtirish.
    Asosan raqamlar va sanalarni to'g'ri o'qilishi uchun so'zga aylantiradi.
    """
    if not text:
        return ""

    # 1. Katta sonlarni birlashtirish (50 000 -> 50000)
    # 3 ta xonali guruhlarga ajratilgan sonlarni topish
    text = re.sub(r'\b(\d{1,3})( \d{3})+\b', lambda m: m.group(0).replace(" ", ""), text)
    
    # 2. Qisqartmalar (Abbreviations)
    abbreviations = {
        r"\bAQSh\b": "Amerika Qo'shma Shtatlari",
        r"\bAQSH\b": "Amerika Qo'shma Shtatlari",
        r"\bBMT\b": "Birlashgan Millatlar Tashkiloti",
        r"\bIIV\b": "Ichki Ishlar Vazirligi",
        r"\bIIB\b": "Ichki Ishlar Boshqarmasi",
        r"\bO'zR\b": "O'zbekiston Respublikasi",
        r"\bMDH\b": "Mustaqil Davlatlar Hamdo'stligi",
        r"\bRF\b": "Rossiya Federatsiyasi",
        r"\bXXR\b": "Xitoy Xalq Respublikasi",
        r"\bOAV\b": "Ommaviy Axborot Vositalari",
        r"\bOTM\b": "Oliy Ta'lim Muassasasi",
        r"\bYPX\b": "Yo'l Patrul Xizmati",
        r"\bFVV\b": "Favqulodda Vaziyatlar Vazirligi",
        r"\bDSQ\b": "Davlat Soliq Qo'mitasi",
        r"\bDTM\b": "Davlat Test Markazi",
        r"\bXTB\b": "Xalq Ta'limi Boshqarmasi",
        r"\bmln\b": "million",
        r"\bmlrd\b": "milliard",
        r"\btrln\b": "trillion",
    }
    
    for pattern, replacement in abbreviations.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # 2. Foiz va Valyuta
    text = re.sub(r'(\d+)%', lambda m: number_to_uzbek(int(m.group(1))) + " foiz", text)
    text = re.sub(r'\$(\d+)', lambda m: number_to_uzbek(int(m.group(1))) + " dollar", text)

    # 3. Yillar va tartib raqamlar (90-yillar, 5-sinf, 1991-yil)
    def replace_ordinal(match):
        number = match.group(1)
        suffix = match.group(2)
        word = number_to_uzbek(int(number), ordinal=True)
        return f"{word} {suffix}"

    text = re.sub(r'(\d+)-(yillar|yil|asr|sinf|oy|kun|qism|mavsum|mikrorayon|maktab|uy|xonadon|kanal)', replace_ordinal, text, flags=re.IGNORECASE)

    # 4. Oddiy tartib raqamlar (1-chi, 2-chi -> Birinchi, Ikkinchi)
    text = re.sub(r'(\d+)-(chi|nchi)', lambda m: number_to_uzbek(int(m.group(1)), ordinal=True), text)
    
    return text

def number_to_uzbek(n: int, ordinal: bool = False) -> str:
    """
    Raqamni o'zbekcha so'zga aylantirish.
    ordinal=True bo'lsa "birinchi", "ikkinchi" kabi qaytaradi.
    """
    if n == 0: return "nolinchi" if ordinal else "nol"

    units = ["", "bir", "ikki", "uch", "to'rt", "besh", "olti", "yetti", "sakkiz", "to'qqiz"]
    tens = ["", "o'n", "yigirma", "o'ttiz", "qirq", "ellik", "oltmish", "yetmish", "sakson", "to'qson"]
    
    words = []
    
    if n >= 1000000000:
        words.append(number_to_uzbek(n // 1000000000) + " milliard")
        n %= 1000000000
    if n >= 1000000:
        words.append(number_to_uzbek(n // 1000000) + " million")
        n %= 1000000
    if n >= 1000:
        words.append(number_to_uzbek(n // 1000) + " ming")
        n %= 1000
    if n >= 100:
        words.append(units[n // 100] + " yuz")
        n %= 100
    if n >= 10:
        words.append(tens[n // 10])
        n %= 10
    if n > 0:
        words.append(units[n])

    result = " ".join(words).strip()
    
    if ordinal:
        # Sonning oxiriga qarab qo'shimcha qo'shish
        # Agar unli bilan tugasa -nchi, undosh bilan tugasa -inchi
        # Oddiy qoida:
        last_word = result.split()[-1]
        if last_word.endswith(('i', 'a', 'o', 'u', "o'", 'e')):
            return result + "nchi"
        else:
            return result + "inchi"
            
    return result
