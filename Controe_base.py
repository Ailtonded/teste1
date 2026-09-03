import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import pandas as pd
import re
import os
from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter

CONFIG_FILE = "conversor_config.txt"
DEFAULT_FILENAME = "eliteserien.xlsx"

def get_saved_excel_path():
    """Lê o caminho do último Excel salvo"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None

def save_excel_path(path):
    """Salva o caminho do último Excel usado"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(path)

def converter_data_br(data_str):
    """Converte data do formato DD.MM.YYYY para DD/MM/YYYY"""
    if re.match(r'\d{2}\.\d{2}\.\d{4}', data_str):
        return data_str.replace('.', '/')
    return data_str

def extrair_jogos(texto):
    """Extrai os jogos do texto colado"""
    registros = []
    rodada_atual = None

    for linha in texto.splitlines():
        linha = re.sub(r'\s+', ' ', linha.strip())

        if not linha:
            continue

        # Detecta rodada
        rodada = re.match(r'(\d+)\.\s*Rodada', linha, re.IGNORECASE)
        if rodada:
            rodada_atual = int(rodada.group(1))
            continue

        if " - " not in linha:
            continue

        # Remove "AWA." e outros resíduos
        linha = linha.replace("AWA.", "").strip()

        # Padrão: Mandante - Visitante Placar Odd1 OddX Odd2 Data
        padrao = (
            r'^(.*?)\s-\s(.*?)\s+'
            r'(\d+):(\d+)\s+'  # Agora captura gols separados
            r'([\d\.\,]+)\s+'
            r'([\d\.\,]+)\s+'
            r'([\d\.\,]+)\s+'
            r'(\d{2}\.\d{2}\.\d{4})$'
        )

        m = re.match(padrao, linha)

        if m:
            mandante, visitante, gols_casa, gols_visitante, odd1, oddx, odd2, data = m.groups()
            
            # Converte gols para inteiro
            gols_casa = int(gols_casa)
            gols_visitante = int(gols_visitante)
            
            # Determina o resultado
            if gols_casa > gols_visitante:
                resultado = "H"  # Home win
            elif gols_casa < gols_visitante:
                resultado = "A"  # Away win
            else:
                resultado = "D"  # Draw
            
            # Converte dados para float (tratando vírgula como separador decimal)
            odd1 = float(odd1.replace(',', '.'))
            oddx = float(oddx.replace(',', '.'))
            odd2 = float(odd2.replace(',', '.'))
            
            # Converte data para formato BR
            data_br = converter_data_br(data)
            
            registros.append({
                "Mandante": mandante,
                "Gols Casa": gols_casa,
                "Gols Visitante": gols_visitante,
                "Visitante": visitante,
                "Resultado": resultado,
                "Odd Casa": odd1,
                "Odd Empate": oddx,
                "Odd Visitante": odd2,
                "Data": data_br,
                "Rodada": rodada_atual
            })

    return pd.DataFrame(registros)

def formatar_excel(caminho):
    """Aplica formatação profissional ao Excel"""
    wb = load_workbook(caminho)
    ws = wb.active
    
    # Ordem correta das colunas (Temporada agora é a primeira)
    colunas_ordem = [
        "Temporada", "Rodada", "Data", "Mandante", "Gols Casa", 
        "Gols Visitante", "Visitante", "Resultado", 
        "Odd Casa", "Odd Empate", "Odd Visitante"
    ]
    
    # Verifica se as colunas existem e reordena se necessário
    cabecalhos = [cell.value for cell in ws[1]]
    if cabecalhos and cabecalhos[0] != "Temporada":
        # Lê todos os dados
        data = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if len(row) >= len(cabecalhos):
                data.append(dict(zip(cabecalhos, row)))
        
        # Cria novo DataFrame na ordem correta
        if data:
            df_novo = pd.DataFrame(data)
            # Adiciona coluna Temporada se não existir
            if "Temporada" not in df_novo.columns:
                df_novo.insert(0, "Temporada", "")
            
            # Reordena colunas
            for col in colunas_ordem:
                if col not in df_novo.columns:
                    df_novo[col] = ""
            
            df_novo = df_novo[colunas_ordem]
            
            # Limpa a planilha e escreve novamente
            ws.delete_rows(1, ws.max_row)
            for c, col in enumerate(colunas_ordem, 1):
                ws.cell(1, c, col)
            
            for r, row in df_novo.iterrows():
                for c, col in enumerate(colunas_ordem, 1):
                    ws.cell(r+2, c, row[col])
    
    # Formatação
    for cell in ws[1]:
        cell.font = Font(bold=True, size=11)
        cell.alignment = Alignment(horizontal="center")
    
    # Congela primeira linha
    ws.freeze_panes = "A2"
    
    # Adiciona filtro automático
    ws.auto_filter.ref = ws.dimensions
    
    # Ajusta largura das colunas
    larguras = {
        "Temporada": 12,
        "Rodada": 8,
        "Data": 12,
        "Mandante": 25,
        "Gols Casa": 10,
        "Gols Visitante": 12,
        "Visitante": 25,
        "Resultado": 10,
        "Odd Casa": 10,
        "Odd Empate": 10,
        "Odd Visitante": 12
    }
    
    for coluna in ws.columns:
        col_letter = get_column_letter(coluna[0].column)
        col_name = coluna[0].value
        if col_name in larguras:
            ws.column_dimensions[col_letter].width = larguras[col_name]
        else:
            tamanho = max(len(str(c.value or "")) for c in coluna) + 2
            ws.column_dimensions[col_letter].width = min(tamanho, 50)
    
    # Centraliza algumas colunas
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for cell in row:
            if cell.column in [1, 2, 3, 5, 6, 8, 9, 10, 11]:  # Temporada, Rodada, Data, Gols, Resultado, Odds
                cell.alignment = Alignment(horizontal="center")
    
    wb.save(caminho)

def salvar_dataframe(df, temporada, caminho):
    """Salva DataFrame no Excel, adicionando ao existente"""
    # Adiciona a coluna Temporada com o valor informado
    df.insert(0, "Temporada", temporada)
    
    if os.path.exists(caminho):
        existente = pd.read_excel(caminho)
        
        # Verifica se a coluna Temporada existe no arquivo existente
        if "Temporada" not in existente.columns:
            existente.insert(0, "Temporada", "")
        
        # Concatena
        novo = pd.concat([existente, df], ignore_index=True)
        
        # Remove duplicatas baseado nas colunas principais
        antes = len(novo)
        novo.drop_duplicates(subset=["Temporada", "Rodada", "Mandante", "Visitante", "Data"], inplace=True)
        depois = len(novo)
        
        novo.to_excel(caminho, index=False)
        return antes - depois
    else:
        df.to_excel(caminho, index=False)
        return 0

class ConversorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Conversor de Jogos - Eliteserien → Excel")
        self.root.geometry("1000x750")
        
        # Carrega último Excel usado
        self.excel_path = get_saved_excel_path()
        
        self.setup_ui()
        self.atualizar_status_excel()
    
    def setup_ui(self):
        # Frame principal
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        # Título
        title_label = ttk.Label(
            main_frame, 
            text="Conversor de Jogos para Excel", 
            font=("Arial", 16, "bold")
        )
        title_label.pack(pady=10)
        
        # Frame de informações do arquivo
        info_frame = ttk.LabelFrame(main_frame, text="Arquivo Excel", padding=10)
        info_frame.pack(fill="x", pady=5)
        
        self.lbl_arquivo = ttk.Label(info_frame, text="Nenhum arquivo selecionado", foreground="gray")
        self.lbl_arquivo.pack(side="left", padx=5)
        
        btn_novo = ttk.Button(info_frame, text="Novo Arquivo", command=self.novo_arquivo)
        btn_novo.pack(side="right", padx=5)
        
        # Frame de botões principais
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=10)
        
        btn_abrir_txt = ttk.Button(btn_frame, text="Abrir TXT", command=self.abrir_txt)
        btn_abrir_txt.pack(side="left", padx=5)
        
        btn_processar = ttk.Button(
            btn_frame, 
            text="Processar e Salvar", 
            command=self.processar,
            width=20
        )
        btn_processar.pack(side="left", padx=5)
        
        btn_limpar = ttk.Button(btn_frame, text="Limpar Texto", command=self.limpar_texto)
        btn_limpar.pack(side="left", padx=5)
        
        # Label para instruções
        ttk.Label(
            main_frame,
            text="Cole os dados dos jogos abaixo:",
            font=("Arial", 10, "bold")
        ).pack(anchor="w", pady=(10, 5))
        
        # Área de texto
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill="both", expand=True, pady=5)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")
        
        self.txt_texto = tk.Text(text_frame, height=25, font=("Consolas", 10), yscrollcommand=scrollbar.set)
        self.txt_texto.pack(fill="both", expand=True)
        scrollbar.config(command=self.txt_texto.yview)
        
        # Frame de informações
        info_bottom = ttk.Frame(main_frame)
        info_bottom.pack(fill="x", pady=10)
        
        self.lbl_status = ttk.Label(info_bottom, text="✅ Pronto", foreground="green")
        self.lbl_status.pack(side="left")
        
        ttk.Label(
            info_bottom,
            text="💡 Dica: Cole os dados completos, incluindo os títulos das rodadas (ex: '30. Rodada')",
            foreground="gray"
        ).pack(side="right")
    
    def atualizar_status_excel(self):
        """Atualiza a label com o caminho do Excel atual"""
        if self.excel_path and os.path.exists(self.excel_path):
            self.lbl_arquivo.config(
                text=f"📊 {os.path.basename(self.excel_path)}", 
                foreground="green"
            )
        elif self.excel_path:
            self.lbl_arquivo.config(text="⚠️ Arquivo não encontrado", foreground="orange")
        else:
            self.lbl_arquivo.config(text="📁 Nenhum arquivo selecionado", foreground="gray")
    
    def novo_arquivo(self):
        """Seleciona um novo arquivo Excel"""
        caminho = filedialog.asksaveasfilename(
            title="Criar/Salvar Excel",
            initialfile=DEFAULT_FILENAME,
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        
        if caminho:
            self.excel_path = caminho
            save_excel_path(caminho)
            self.atualizar_status_excel()
            self.lbl_status.config(text="✅ Novo arquivo selecionado", foreground="green")
            self.root.after(3000, lambda: self.lbl_status.config(text="✅ Pronto", foreground="green"))
    
    def abrir_txt(self):
        """Abre um arquivo TXT e cola no texto"""
        arquivo = filedialog.askopenfilename(
            title="Selecionar arquivo TXT",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if arquivo:
            try:
                with open(arquivo, "r", encoding="utf-8") as f:
                    conteudo = f.read()
                self.txt_texto.delete("1.0", tk.END)
                self.txt_texto.insert("1.0", conteudo)
                self.lbl_status.config(text=f"✅ Arquivo carregado: {os.path.basename(arquivo)}", foreground="green")
                self.root.after(3000, lambda: self.lbl_status.config(text="✅ Pronto", foreground="green"))
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao ler arquivo:\n{str(e)}")
    
    def limpar_texto(self):
        """Limpa a área de texto"""
        if messagebox.askyesno("Confirmar", "Limpar todo o texto?"):
            self.txt_texto.delete("1.0", tk.END)
            self.lbl_status.config(text="✅ Texto limpo", foreground="green")
            self.root.after(2000, lambda: self.lbl_status.config(text="✅ Pronto", foreground="green"))
    
    def processar(self):
        """Processa o texto e salva no Excel"""
        texto = self.txt_texto.get("1.0", tk.END)
        
        if not texto.strip():
            messagebox.showwarning("Aviso", "Por favor, cole algum texto com os jogos.")
            return
        
        # Verifica se tem arquivo Excel selecionado
        if not self.excel_path:
            resposta = messagebox.askyesno(
                "Arquivo não selecionado",
                "Nenhum arquivo Excel foi selecionado.\n\nDeseja selecionar/criar um agora?"
            )
            if resposta:
                self.novo_arquivo()
                if not self.excel_path:
                    return
            else:
                return
        
        # Solicita a temporada ao usuário
        temporada = simpledialog.askstring(
            "Temporada", 
            "Informe a temporada (exemplo: 2024, 2025, 2024/2025):\n\n"
            "Esta informação será adicionada na coluna 'Temporada'",
            parent=self.root
        )
        
        if not temporada:
            messagebox.showwarning("Aviso", "Temporada não informada. Operação cancelada.")
            return
        
        # Extrai os jogos
        df = extrair_jogos(texto)
        
        if df.empty:
            messagebox.showerror(
                "Erro", 
                "Nenhum jogo encontrado no texto.\n\n"
                "Verifique se o texto está no formato correto:\n"
                "- Inclui os títulos das rodadas (ex: '30. Rodada')\n"
                "- Cada linha tem: Time - Time Placar Odd1 OddX Odd2 Data"
            )
            return
        
        # Mostra preview
        preview_msg = f"📊 Encontrados {len(df)} jogos:\n\n"
        preview_msg += f"🏆 Temporada: {temporada}\n"
        preview_msg += f"📅 Rodadas: {df['Rodada'].min()} a {df['Rodada'].max()}\n"
        preview_msg += f"⚽ Times distintos: {len(pd.concat([df['Mandante'], df['Visitante']]).unique())}\n\n"
        preview_msg += "Os dados serão salvos com:\n"
        preview_msg += "• Temporada na primeira coluna\n"
        preview_msg += "• Data no formato BR (DD/MM/AAAA)\n"
        preview_msg += "• Placar separado em Gols Casa e Gols Visitante\n"
        preview_msg += "• Resultado (H = Casa, D = Empate, A = Fora)\n\n"
        preview_msg += "Deseja continuar?"
        
        if not messagebox.askyesno("Confirmar", preview_msg):
            return
        
        # Salva no Excel
        try:
            removidos = salvar_dataframe(df, temporada, self.excel_path)
            formatar_excel(self.excel_path)
            
            # Mensagem de sucesso
            mensagem = f"✅ {len(df)} jogos da temporada {temporada} adicionados com sucesso!"
            if removidos > 0:
                mensagem += f"\n⚠️ {removidos} jogos duplicados foram ignorados."
            
            self.lbl_status.config(text=mensagem, foreground="green")
            messagebox.showinfo("Concluído", mensagem + "\n\nArquivo atualizado com a nova coluna 'Temporada'!")
            
            # Limpa o texto após salvar (opcional)
            if messagebox.askyesno("Limpar texto", "Limpar o texto colado?"):
                self.txt_texto.delete("1.0", tk.END)
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao salvar arquivo:\n{str(e)}")
            self.lbl_status.config(text="❌ Erro ao salvar", foreground="red")

def main():
    root = tk.Tk()
    app = ConversorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()