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
        self.cell(20, 7, 'Pedido', 1, 0, 'C', 1)
        self.cell(15, 7, 'Loja', 1, 0, 'C', 1)
        self.cell(60, 7, 'Cliente', 1, 0, 'L', 1)
        self.cell(25, 7, 'Previsão', 1, 0, 'C', 1)
        self.cell(25, 7, 'Situação', 1, 0, 'C', 1)
        self.cell(45, 7, 'Lote/OF', 1, 1, 'C', 1)

def gerar_pdf_pedidos(output_path, dias=180):
    pg = DatabasePostgreSQL()
    
    # Busca os pedidos com a mesma lógica do sistema
    sql = f"""
        SELECT 
            p.pedido, 
            TRIM(CAST(e.empnome AS TEXT)) as cliente, 
            p.pedprevi as previsao, 
            TRIM(CAST(p.pedsitsit AS TEXT)) as status, 
            TRIM(CAST(p.pedsitua AS TEXT)) as situacao,
            TRIM(CAST(p.pedoflote AS TEXT)) as lote,
            CAST(p.peddep AS TEXT) as deposito
        FROM public.pedido p
        LEFT JOIN public.empresa e ON p.pedcliente::text = e.empresa::text
        WHERE p.peddata >= CURRENT_DATE - INTERVAL '{dias} days'
        AND CAST(p.pedsitua AS TEXT) NOT IN ('C')
        AND CAST(p.pedsitsit AS TEXT) NOT IN ('007', '008', '009', '010', '004')
        ORDER BY p.pedprevi ASC
    """
    pedidos = pg.query(sql)
    
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', '', 8)
    
    for p in pedidos:
        previsao = p['previsao'].strftime('%d/%m/%Y') if p['previsao'] and hasattr(p['previsao'], 'strftime') else '-'
        cliente = (p['cliente'][:35] + '..') if p['cliente'] and len(p['cliente']) > 35 else (p['cliente'] or '-')
        deposito = str(p['deposito']) if p['deposito'] else '-'
        
        # Destaque para lojas 2, 3, 4 e 7 (fundo cinza claro para destacar)
        destaque = p['deposito'] in ['2', '3', '4', '7']
        if destaque:
            pdf.set_fill_color(240, 230, 255) # Roxo bem clarinho para o PDF
            fill = True
        else:
            fill = False
            
        pdf.cell(20, 6, str(p['pedido']), 1, 0, 'C', fill)
        
        # Se for loja de destaque, coloca um asterisco ou algo para marcar no PDF
        dep_text = f"* {deposito}" if destaque else deposito
        pdf.cell(15, 6, dep_text, 1, 0, 'C', fill)
        
        pdf.cell(60, 6, cliente, 1, 0, 'L', fill)
        pdf.cell(25, 6, previsao, 1, 0, 'C', fill)
        pdf.cell(25, 6, p['situacao'] or '-', 1, 0, 'C', fill)
        pdf.cell(45, 6, p['lote'] or '-', 1, 1, 'C', fill)
        
    pdf.output(output_path)
    return len(pedidos)

if __name__ == "__main__":
    count = gerar_pdf_pedidos('relatorio_pedidos_comparacao.pdf')
    print(f"Relatório gerado com {count} pedidos.")
