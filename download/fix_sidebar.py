#!/usr/bin/env python3
"""
Fix sidebar da porta 5002 - garante largura correta via CSS
 independente do Tailwind CDN carregar ou nao.
Rode este script no servidor: python3 fix_sidebar.py
"""
import os

BASE = '/home/suporte/producao_muito/producao'

# ── 1. Fix prodsys.css ──────────────────────────────────────────
css_path = os.path.join(BASE, 'static', 'css', 'prodsys.css')
with open(css_path, 'r') as f:
    css = f.read()

# 1a. Atualizar variaveis de largura
css = css.replace(
    '--sidebar-w:           240px;\n  --sidebar-w-tablet:    260px;',
    '--sidebar-w:           250px;\n  --sidebar-w-tablet:    270px;'
)

# 1b. Adicionar fallback de largura ANTES da media query mobile
old_sidebar_section = """/* ─────────────────────────────────────────────────────────────
   7. SIDEBAR (drawer em tablet)
   ───────────────────────────────────────────────────────────── */
@media (max-width: 1023px) {"""

new_sidebar_section = """/* ─────────────────────────────────────────────────────────────
   7. SIDEBAR (drawer em tablet)
   ───────────────────────────────────────────────────────────── */

/* Fallback: garante largura mesmo se Tailwind w-60 nao carregar */
.prodsys-sidebar {
  width: var(--sidebar-w) !important;
  min-width: var(--sidebar-w) !important;
}

/* Fallback: garante padding-left do conteudo */
@media (min-width: 768px) {
  .prodsys-main-wrap {
    padding-left: var(--sidebar-w) !important;
  }
}

@media (max-width: 1023px) {"""

if old_sidebar_section in css:
    css = css.replace(old_sidebar_section, new_sidebar_section)
    print('[OK] CSS: fallback de largura adicionado')
else:
    print('[WARN] CSS: trecho original nao encontrado, tentando append...')

# 1c. Melhorar nav-item (gap, padding, white-space, icon)
old_nav = """.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 0.875rem;
  font-weight: 600;
  color: #cbd5e1;
  transition: all 0.15s;
  text-decoration: none;
}
.nav-item:hover { background: #1e293b; color: #fff; }
.nav-item.active { background: var(--prodsys-blue-light); color: #fff; }
.nav-item i { width: 20px; text-align: center; font-size: 0.95rem; }"""

new_nav = """.nav-item {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 0.875rem;
  font-weight: 600;
  color: #cbd5e1;
  transition: all 0.15s;
  text-decoration: none;
  white-space: nowrap;
}
.nav-item:hover { background: #1e293b; color: #fff; }
.nav-item.active { background: var(--prodsys-blue-light); color: #fff; }
.nav-item i:first-child { width: 22px; text-align: center; font-size: 0.95rem; flex-shrink: 0; }"""

if old_nav in css:
    css = css.replace(old_nav, new_nav)
    print('[OK] CSS: nav-item melhorado')
else:
    print('[WARN] CSS: nav-item original nao encontrado')

# 1d. Adicionar min-width no media query mobile
old_mobile = """.prodsys-sidebar {
    position: fixed !important;
    inset: 0 auto 0 0;
    z-index: 50;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
    width: var(--sidebar-w-tablet) !important;
    box-shadow: 0 0 40px rgba(0,0,0,0.4);
  }"""

new_mobile = """.prodsys-sidebar {
    position: fixed !important;
    inset: 0 auto 0 0;
    z-index: 50;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
    width: var(--sidebar-w-tablet) !important;
    min-width: var(--sidebar-w-tablet) !important;
    box-shadow: 0 0 40px rgba(0,0,0,0.4);
  }"""

if old_mobile in css:
    css = css.replace(old_mobile, new_mobile)
    print('[OK] CSS: min-width adicionado no mobile')

with open(css_path, 'w') as f:
    f.write(css)
print('[OK] CSS salvo: ' + css_path)

# ── 2. Fix base.html ───────────────────────────────────────────
html_path = os.path.join(BASE, 'templates', 'base.html')
with open(html_path, 'r') as f:
    html = f.read()

# Trocar md:pl-60 por classe CSS que garante o padding
old_wrap = 'class="flex-1 flex flex-col md:pl-60 transition-all duration-300 min-w-0"'
new_wrap = 'class="prodsys-main-wrap flex-1 flex flex-col transition-all duration-300 min-w-0"'

if old_wrap in html:
    html = html.replace(old_wrap, new_wrap)
    print('[OK] HTML: classe prodsys-main-wrap adicionada no content wrapper')
else:
    print('[WARN] HTML: trecho original do content wrapper nao encontrado')

with open(html_path, 'w') as f:
    f.write(html)
print('[OK] HTML salvo: ' + html_path)

print('\n[DONE] Sidebar fix aplicado. Reinicie o app na porta 5002.')