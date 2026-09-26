from before_you_pay.services.ocr_quality import COMMON_VOCABULARY
import re

EXTRA_VOCAB = {"offer", "offers", "extra", "insurance", "registration", "showroom", "cng", "tcs", "rc", "hsrp"}
FULL_VOCAB = COMMON_VOCABULARY.union(EXTRA_VOCAB)

text = 'VictoRis Lxi CNG. Exshorum = 1149900 T.C.S = 11499 InSorage = 34500 R.C = 76250 Warranty = 24000 Tem+HSRP = 2250 TOTAL => 1298399 Offer - 20,000 Extra Offer - 50,000 1228399'
tokens = [tok.strip('.,:;()[]"\'') for tok in text.split() if tok.strip('.,:;()[]"\'')]
recognized = []
unrecognized = []
for tok in tokens:
    cleaned = tok.lower().replace(".", "").replace("+", "")
    if tok.lower() in FULL_VOCAB or cleaned in FULL_VOCAB or re.match(r"^[\$€£₹¥]?\d+(?:[.,]\d+)*$", tok):
        recognized.append(tok)
    else:
        unrecognized.append(tok)

print("Tokens count:", len(tokens))
print("Recognized count:", len(recognized))
print("Unrecognized count:", len(unrecognized), unrecognized)
ratio = len(recognized) / len(tokens)
print("Vocab ratio:", ratio)
if ratio < 0.70:
    print("STATUS: MODERATE (Handwritten/Informal terms require normalization)")
else:
    print("STATUS: GOOD (High standard vocabulary)")
