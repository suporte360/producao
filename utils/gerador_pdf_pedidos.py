import os
import sys
from fpdf import FPDF
from datetime import datetime

# Adiciona a raiz do projeto ao path para importar o banco
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.postgresql_db import DatabasePostgreSQL

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Relatório de Comparação de Pedidos - ERP vs Sistema', 0, 1, 'C')
        self.set_font('Arial', 'I', 8)
        self.cell(0, 5, f'Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}', 0, 1, 'R')
        self.ln(5)
        
        # Cabeçalho da tabela
        self.set_fill_color(200, 220, 255)
        self.set_font('Arial', 'B', 8)
        self.cell(15, 7, 'Pedido', 1, 0, 'C', 1)
        self.cell(10, 7, 'Loja', 1, 0, 'C', 1)
        self.cell(55, 7, 'Cliente', 1, 0, 'L', 1)
        self.cell(20, 7, 'Previsão', 1, 0, 'C', 1)
        self.cell(50, 7, 'Status', 1, 0, 'C', 1)
        self.cell(40, 7, 'Lote/OF', 1, 1, 'C', 1)

# Mapeamento de Status baseado na tabela pestatus do ERP
STATUS_MAP = {
    "01": "Pedido Não Aprovado",
    "02": "Pedido em Aberto",
    "03": "Vínculo com OF Estática",
    "04": "Vínculo com OF em Processo",
    "05": "Vínculo com OF Encerrada",
    "06": "Vínculo com OF Com Problema",
    "07": "Atendido Parcial",
    "08": "Atendido Total",
    "09": "Vínculo com Expedição",
    "10": "Pedido Cancelado",
}

def gerar_pdf_pedidos(output_path, dias=180, status_filtro='Todos'):
    pg = DatabasePostgreSQL()

    # Construção do filtro SQL
    filtro_status = ""
    if status_filtro and status_filtro != 'Todos':
        # Filtra pela tabela pestatus usando o código de status
        filtro_status = f"AND ps.pesstatus = '{status_filtro}'"

    # Busca os pedidos com JOIN na tabela pestatus para obter o status correto
    sql = f"""
        SELECT 
            p.pedido, 
            TRIM(CAST(e.empnome AS TEXT)) as cliente, 
            p.pedprevi as previsao, 
            TRIM(CAST(ps.pesstatus AS TEXT)) as status_codigo,
            TRIM(CAST(p.pedoflote AS TEXT)) as lote,
            CAST(p.deposito AS TEXT) as deposito
        FROM public.pedido p
        LEFT JOIN public.empresa e ON p.pedcliente::text = e.empresa::text
        LEFT JOIN public.pestatus ps ON p.pedido::text = ps.pespedido::text
        WHERE p.peddata >= CURRENT_DATE - INTERVAL '{dias} days'
        {filtro_status}
        ORDER BY p.pedprevi ASC, p.pedido DESC
    """
    pedidos = pg.query(sql)
    
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', '', 8)
    
    # Se houver filtro, adicionar informação no topo
    if status_filtro and status_filtro != 'Todos':
        status_nome = STATUS_MAP.get(status_filtro, status_filtro)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 10, f'Filtro: {status_nome}', 0, 1, 'L')
        pdf.set_font('Arial', '', 8)
        pdf.ln(2)

    for p in pedidos:
        previsao = p['previsao'].strftime('%d/%m/%Y') if p['previsao'] and hasattr(p['previsao'], 'strftime') else '-'
        cliente = (p['cliente'][:32] + '..') if p['cliente'] and len(p['cliente']) > 32 else (p['cliente'] or '-')
        deposito = str(p['deposito']) if p['deposito'] else '-'
        
        # Tradução baseada no código de status
        cod_status = str(p['status_codigo']).strip() if p['status_codigo'] else ""
        status_extenso = STATUS_MAP.get(cod_status, "Desconhecido")
            
        # Destaque para lojas 2, 3, 4 e 7
        destaque = p['deposito'] in ['2', '3', '4', '7']
        if destaque:
            pdf.set_fill_color(240, 230, 255)
            fill = True
        else:
            fill = False
            
        pdf.cell(15, 6, str(p['pedido']), 1, 0, 'C', fill)
        pdf.cell(10, 6, deposito, 1, 0, 'C', fill)
        pdf.cell(55, 6, cliente, 1, 0, 'L', fill)
        pdf.cell(20, 6, previsao, 1, 0, 'C', fill)
        pdf.cell(50, 6, status_extenso.upper(), 1, 0, 'C', fill)
        pdf.cell(40, 6, p['lote'] or '-', 1, 1, 'C', fill)
        
    pdf.output(output_path)
    return len(pedidos)

if __name__ == "__main__":
    count = gerar_pdf_pedidos('relatorio_pedidos_comparacao.pdf')
    print(f"Relatório gerado com {count} pedidos.")
