"""Busca strings en ingles en el JS del frontend."""
import re

with open(r'C:\Users\leiva\Documents\ERP LEIVA\frontend\static\js\app.js', encoding='utf-8') as f:
    js = f.read()

# Strings entre comillas simples
single = re.findall(r"'([A-Za-z\s\.\-\:\?\!]{3,80})'", js)
# Strings entre backticks (templates)
backticks = re.findall(r"`([A-Za-z\s\.\-\:\?\!]{3,80})`", js)

print("=== STRINGS SOSPECHOSOS (sin acentos) ===")
candidates = set()
for s in single + backticks:
    # filtrar solo las que NO tienen acentos (posible ingles)
    if not re.search(r'[áéíóúÁÉÍÓÚñÑ]', s):
        if any(w in s.lower() for w in ['new', 'save', 'delete', 'edit', 'update',
                                          'close', 'cancel', 'open', 'loading',
                                          'error', 'success', 'failed', 'search',
                                          'refresh', 'submit', 'confirm', 'welcome',
                                          'please', 'sorry', 'done', 'active',
                                          'inactive', 'yes', 'no,', 'hello', 'loading']):
            candidates.add(s)

print(f"\nEncontrados: {len(candidates)}\n")
for c in sorted(candidates)[:60]:
    print(f"  '{c}'")