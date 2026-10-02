"""High-frequency Hinglish (Roman Hindi) words and their standard Devanagari spelling.

Rule-based transliteration cannot know that "nahi" is नहीं or that "kitab" is किताब, because
Roman Hindi spelling is not standardized. This lexicon covers the most common words and
spelling variants; everything else falls through to the rules in hinglish.py.
"""

LEXICON: dict[str, str] = {
    # pronouns
    "main": "मैं", "mai": "मैं", "mein": "में", "mujhe": "मुझे", "mujhko": "मुझको", "mera": "मेरा",
    "meri": "मेरी", "mere": "मेरे", "hum": "हम", "humein": "हमें", "hume": "हमें", "hamara": "हमारा",
    "hamari": "हमारी", "hamare": "हमारे", "tum": "तुम", "tumhe": "तुम्हें", "tumhara": "तुम्हारा",
    "tumhari": "तुम्हारी", "tumhare": "तुम्हारे", "tu": "तू", "tera": "तेरा", "teri": "तेरी",
    "aap": "आप", "aapka": "आपका", "aapki": "आपकी", "aapke": "आपके", "aapko": "आपको",
    "woh": "वो", "wo": "वो", "vo": "वो", "voh": "वो", "yeh": "यह", "ye": "ये", "yah": "यह",
    "unka": "उनका", "unki": "उनकी", "unke": "उनके", "usne": "उसने", "usko": "उसको", "use": "उसे",
    "isko": "इसको", "iska": "इसका", "iski": "इसकी", "iske": "इसके", "unhe": "उन्हें",
    "inhe": "इन्हें", "kaun": "कौन", "kya": "क्या", "kyun": "क्यों", "kyon": "क्यों",
    "kyu": "क्यों", "kaise": "कैसे", "kese": "कैसे", "kaisa": "कैसा", "kaisi": "कैसी",
    "kahan": "कहाँ", "kaha": "कहाँ", "kab": "कब", "kitna": "कितना", "kitni": "कितनी",
    "kitne": "कितने", "kisne": "किसने", "kisko": "किसको", "kiska": "किसका", "konsa": "कौनसा",
    # verbs "to be" / auxiliaries
    "hai": "है", "he": "है", "hain": "हैं", "hun": "हूँ", "hoon": "हूँ", "ho": "हो",
    "tha": "था", "thi": "थी", "the": "थे", "hoga": "होगा", "hogi": "होगी", "honge": "होंगे",
    "raha": "रहा", "rahi": "रही", "rahe": "रहे", "gaya": "गया", "gayi": "गयी", "gaye": "गए",
    "gya": "गया", "hua": "हुआ", "hui": "हुई", "hue": "हुए", "sakta": "सकता", "sakti": "सकती",
    "sakte": "सकते", "chahiye": "चाहिए", "chahie": "चाहिए", "chahta": "चाहता", "chahti": "चाहती",
    # common verbs
    "karna": "करना", "karta": "करता", "karti": "करती", "karte": "करते", "kiya": "किया",
    "kar": "कर", "karo": "करो", "karen": "करें", "kare": "करे", "karunga": "करूँगा",
    "karungi": "करूँगी", "jana": "जाना", "jaata": "जाता", "jata": "जाता", "jaati": "जाती",
    "jati": "जाती", "jao": "जाओ", "jaa": "जा", "ja": "जा", "jayega": "जाएगा", "jaayega": "जाएगा",
    "jayegi": "जाएगी", "aana": "आना", "aata": "आता", "aati": "आती", "aao": "आओ", "aa": "आ",
    "aaya": "आया", "aayi": "आई", "aaye": "आए", "dena": "देना", "diya": "दिया", "do": "दो",
    "lena": "लेना", "liya": "लिया", "lo": "लो", "khana": "खाना", "khaata": "खाता",
    "khata": "खाता", "peena": "पीना", "peeta": "पीता", "pita": "पीता", "dekhna": "देखना",
    "dekha": "देखा", "dekho": "देखो", "sunna": "सुनना", "suno": "सुनो", "bolna": "बोलना",
    "bolta": "बोलता", "bolo": "बोलो", "batana": "बताना", "batao": "बताओ", "samajh": "समझ",
    "samajhna": "समझना", "samjha": "समझा", "pata": "पता", "milna": "मिलना", "mila": "मिला",
    "padhna": "पढ़ना", "padhta": "पढ़ता", "padhti": "पढ़ती", "likhna": "लिखना", "likhta": "लिखता",
    "rehna": "रहना", "rehta": "रहता", "rahta": "रहता", "rehti": "रहती", "lagta": "लगता",
    "lagti": "लगती", "lagta hai": "लगता है", "pasand": "पसंद", "chalo": "चलो", "chalna": "चलना",
    "baitho": "बैठो", "ruko": "रुको", "ruk": "रुक", "bhejna": "भेजना", "bhej": "भेज",
    # negation / particles
    "nahi": "नहीं", "nahin": "नहीं", "nhi": "नहीं", "na": "ना", "mat": "मत", "bhi": "भी",
    "hi": "ही", "to": "तो", "toh": "तो", "ki": "की", "ke": "के", "ka": "का", "ko": "को",
    "se": "से", "par": "पर", "pe": "पे", "me": "में", "tak": "तक", "aur": "और", "ya": "या",
    "lekin": "लेकिन", "magar": "मगर", "par bhi": "पर भी", "agar": "अगर", "toh bhi": "तो भी",
    "kyunki": "क्योंकि", "isliye": "इसलिए", "phir": "फिर", "fir": "फिर", "abhi": "अभी",
    "ab": "अब", "jab": "जब", "tab": "तब", "yahan": "यहाँ", "yaha": "यहाँ", "wahan": "वहाँ",
    "waha": "वहाँ", "idhar": "इधर", "udhar": "उधर", "bahut": "बहुत", "bohot": "बहुत",
    "zyada": "ज़्यादा", "jyada": "ज्यादा", "kam": "कम", "thoda": "थोड़ा", "thodi": "थोड़ी",
    "sab": "सब", "sabhi": "सभी", "kuch": "कुछ", "koi": "कोई", "har": "हर", "sirf": "सिर्फ",
    "bas": "बस", "bilkul": "बिल्कुल", "shayad": "शायद", "zaroor": "ज़रूर", "jaroor": "जरूर",
    "sach": "सच", "jhooth": "झूठ", "haan": "हाँ", "han": "हाँ", "ji": "जी", "accha": "अच्छा",
    "acha": "अच्छा", "achha": "अच्छा", "achchha": "अच्छा", "theek": "ठीक", "thik": "ठीक",
    "bura": "बुरा", "naya": "नया", "nayi": "नई", "purana": "पुराना", "bada": "बड़ा",
    "badi": "बड़ी", "bade": "बड़े", "chhota": "छोटा", "chhoti": "छोटी", "sundar": "सुंदर",
    "khush": "खुश", "dukhi": "दुखी", "sahi": "सही", "galat": "गलत", "mushkil": "मुश्किल",
    "aasan": "आसान", "asan": "आसान",
    # nouns
    "naam": "नाम", "nam": "नाम", "ghar": "घर", "log": "लोग", "logon": "लोगों", "kaam": "काम",
    "kam karna": "काम करना", "paani": "पानी", "pani": "पानी", "chai": "चाय", "chay": "चाय",
    "khaana": "खाना", "roti": "रोटी", "doodh": "दूध", "dudh": "दूध", "kitab": "किताब",
    "kitaab": "किताब", "dost": "दोस्त", "dosti": "दोस्ती", "pyaar": "प्यार", "pyar": "प्यार",
    "zindagi": "ज़िंदगी", "jindagi": "जिंदगी", "duniya": "दुनिया", "desh": "देश",
    "shehar": "शहर", "sheher": "शहर", "gaon": "गाँव", "gaav": "गाँव", "school": "स्कूल",
    "college": "कॉलेज", "office": "ऑफिस", "paisa": "पैसा", "paise": "पैसे", "din": "दिन",
    "raat": "रात", "subah": "सुबह", "shaam": "शाम", "kal": "कल", "aaj": "आज", "parso": "परसों",
    "saal": "साल", "mahina": "महीना", "hafta": "हफ्ता", "samay": "समय", "waqt": "वक़्त",
    "vakt": "वक्त", "baat": "बात", "baatein": "बातें", "sawal": "सवाल", "jawab": "जवाब",
    "madad": "मदद", "bhai": "भाई", "behen": "बहन", "bahan": "बहन", "maa": "माँ", "papa": "पापा",
    "pita ji": "पिता जी", "beta": "बेटा", "beti": "बेटी", "ladka": "लड़का", "ladki": "लड़की",
    "aadmi": "आदमी", "aurat": "औरत", "insaan": "इंसान", "bhagwan": "भगवान", "namaste": "नमस्ते",
    "shukriya": "शुक्रिया", "dhanyavad": "धन्यवाद", "maaf": "माफ़", "kripya": "कृपया",
    "swagat": "स्वागत", "hindi": "हिंदी", "english": "अंग्रेज़ी", "bharat": "भारत",
    "india": "इंडिया", "delhi": "दिल्ली", "dilli": "दिल्ली", "mumbai": "मुंबई", "tum kaise ho": "तुम कैसे हो",
    # extra common words and variants
    "jaunga": "जाऊँगा", "jaungi": "जाऊँगी", "aunga": "आऊँगा", "aungi": "आऊँगी", "achi": "अच्छी",
    "achhi": "अच्छी", "achchi": "अच्छी", "achhe": "अच्छे", "ache": "अच्छे", "bhasha": "भाषा",
    "bhaasha": "भाषा", "mausam": "मौसम", "kaisa hai": "कैसा है", "aasman": "आसमान", "suraj": "सूरज",
    "chand": "चाँद", "tara": "तारा", "phool": "फूल", "ped": "पेड़", "nadi": "नदी", "pahad": "पहाड़",
    "khelna": "खेलना", "khel": "खेल", "gana": "गाना", "gaana": "गाना", "film": "फ़िल्म",
    "movie": "मूवी", "phone": "फ़ोन", "computer": "कंप्यूटर", "train": "ट्रेन", "bus": "बस",
    "kharab": "खराब", "mazaa": "मज़ा", "maza": "मज़ा", "mazedar": "मज़ेदार", "tez": "तेज़",
    "dheere": "धीरे", "jaldi": "जल्दी", "der": "देर", "pehle": "पहले", "baad": "बाद",
    "saath": "साथ", "liye": "लिए", "wala": "वाला", "wali": "वाली", "wale": "वाले",
    "vaise": "वैसे", "jaise": "जैसे", "waise": "वैसे", "aise": "ऐसे",
    "pyara": "प्यारा", "pyari": "प्यारी", "bhasha ": "भाषा",
    # numbers
    "ek": "एक", "do ": "दो", "teen": "तीन", "char": "चार", "paanch": "पाँच", "panch": "पाँच",
    "chhe": "छह", "saat": "सात", "aath": "आठ", "nau": "नौ", "das": "दस", "sau": "सौ",
    "hazaar": "हज़ार", "hazar": "हज़ार", "lakh": "लाख", "pehla": "पहला", "doosra": "दूसरा",
}  # fmt: skip

# Drop keys that are really multi-word or padded by accident: the lexicon is word-level.
LEXICON = {k: v for k, v in LEXICON.items() if k == k.strip() and " " not in k}

# Words that, when frequent in Latin text, suggest Hinglish rather than English.
# Excludes words that are also common English ("to", "me", "do", "he", "the", "hi", "main", ...).
_AMBIGUOUS_WITH_ENGLISH = {
    "to", "me", "do", "he", "the", "hi", "main", "ho", "ha", "na", "ka", "ki", "ko", "se", "pe",
    "par", "ab", "use", "so", "no", "kar", "tab", "bas", "hum", "ja", "aa", "ye", "tu", "yeh",
    "phir", "fir", "tha", "thi", "han", "kam", "din", "tak", "mat", "is", "us", "in",
}  # fmt: skip
HINGLISH_MARKERS = {w for w in LEXICON if w not in _AMBIGUOUS_WITH_ENGLISH and len(w) > 2}
