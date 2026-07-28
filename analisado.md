# Análise dos Problemas

## Erros 404 encontrados:
1. **`templates/admin/base.html`** (linha 95,98) - Links para `admin_acessos` e `admin_logs` que não existem no app.py
2. **`templates/base_admin.html`** (linha 39,41) - Links para `admin_estoque` e `admin_logs` que não existem
3. **`templates/diretor/relatorios.html`** - Existe mas NÃO tem link no menu lateral `base.html`

## Problema principal da diretoria:
- O menu lateral (`base.html`) na seção "Diretoria" só mostra: Logs e Acessos
- Falta link para `/diretor/relatorios` (que já existe como rota)
- A rota `/diretor/relatorios` renderiza `diretor/relatorios.html` com dados incompletos

## Solução planejada:
1. Adicionar link para `diretor_relatorios` no menu lateral `base.html`
2. Reescrever `diretor/relatorios.html` como página principal da diretoria com:
   - Pedidos em aberto (do ERP e local)
   - OPs atrasadas
   - OPs próximas da data de entrega (próximos 7 dias)
   - Produção por setor
   - KPIs gerais
   - Gráficos funcionais (usando dados reais do dashboard_gerente)
3. Corrigir `admin/base.html` e `base_admin.html` para remover/ajustar links quebrados
