import sys, os
sys.path.insert(0, r'C:\Users\athar\Desktop\arvsal\wakeword')
from config.settings import ANCHOR_VARIANTS
import jellyfish

t = 'ourselves'
tn = t.replace(' ', '')
print(f"Testing: {t!r}")
for v in ANCHOR_VARIANTS:
    vn = v.replace(' ', '')
    sub = vn in tn
    jw  = jellyfish.jaro_winkler_similarity(t, vn)
    if sub or jw >= 0.82:
        print(f"  HIT  variant={v!r}  substring={sub}  jw={jw:.3f}")
