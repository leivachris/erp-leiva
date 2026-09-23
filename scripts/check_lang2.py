"""Auditoria completa de strings en todo el frontend."""
import re
import os

frontend_dir = r'C:\Users\leiva\Documents\ERP LEIVA\frontend'

for fname in ['index.html', r'static\css\style.css', r'static\js\app.js', r'static\js\api.js']:
    full = os.path.join(frontend_dir, fname)
    with open(full, encoding='utf-8') as f:
        content = f.read()

    print(f"\n=== {fname} ===")

    # Buscar strings visibles (entre comillas, sin acentos)
    candidates = set()

    # Comillas simples y backticks
    for pat in [r"'([^']{3,80})'", r'`([^`]{3,80})`', r'"([^"]{3,80})"']:
        for m in re.findall(pat, content):
            # Filtrar:
            # - Tiene espacios (probable mensaje)
            # - NO tiene acentos
            # - Empieza con mayuscula o tiene keyword english
            if ' ' not in m and len(m) < 15:
                continue
            if re.search(r'[áéíóúÁÉÍÓÚñÑ]', m):
                continue
            if any(w in m.lower() for w in [
                'new', 'save', 'delete', 'edit ', 'update', 'close', 'cancel',
                'open ', 'loading', 'error', 'success', 'failed', 'search',
                'refresh', 'submit', 'confirm', 'welcome', 'please', 'sorry',
                'done', 'active', 'inactive', 'yes,', 'no,', 'hello',
            ]):
                candidates.add(m)

    print(f"  Strings con keyword inglesa: {len(candidates)}")
    for c in sorted(candidates)[:30]:
        print(f"    {c!r}")

    # Buscar palabras sueltas (no en strings) que sean inglesas obvias
    print(f"  Texto visible en HTML (mayusculas):")
    for m in re.findall(r'>([A-Z][A-Za-z\s]{4,60})<', content):
        if not re.search(r'[áéíóúñ]', m) and ' ' in m:
            print(f"    {m!r}")