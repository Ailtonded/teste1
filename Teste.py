import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import json
import os
import base64
from datetime import datetime, date
from typing import Optional, List, Dict, Any

# --- BIBLIOTECAS DE SEGURANÇA ---
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

# --- CONFIGURAÇÃO DE TEMA (ERP MODERNO) ---
CONFIG_THEME = {
    "bg_dark": "#1e1e1e",
    "bg_sidebar": "#252526",
    "bg_main": "#1e1e1e",
    "bg_panel": "#2d2d2d",
    "accent": "#007acc",
    "accent_hover": "#005a9e",
    "text_light": "#ffffff",
    "text_gray": "#cccccc",
    "danger": "#d9534f",
    "success": "#5cb85c",
    "warning": "#f0ad4e",
    "font_normal": ("Segoe UI", 10),
    "font_header": ("Segoe UI", 12, "bold"),
    "font_title": ("Segoe UI", 16, "bold"),
    "font_logo": ("Segoe UI", 20, "bold"),
    "tree_bg": "#1e1e1e",
    "tree_field_bg": "#333333",
    "data_file": "dados_contabeis.enc"
}

# --- CAMADA DE SEGURANÇA (CRYPTO ENGINE) ---

class SecurityService:
    """
    Gerencia criptografia robusta usando Fernet (AES-128) com derivação de chave PBKDF2HMAC.
    Garante que os dados jamais sejam salvos em texto puro.
    """
    ITERATIONS = 100_000

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        """Deriva uma chave segura de 32 bytes a partir da senha do usuário."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=SecurityService.ITERATIONS,
            backend=default_backend()
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))

    @staticmethod
    def encrypt_data(data: dict, password: str) -> dict:
        """
        Criptografa o dicionário de dados.
        Retorna um dicionário contendo o salt e o conteúdo criptografado.
        """
        salt = os.urandom(16)
        key = SecurityService._derive_key(password, salt)
        f = Fernet(key)
        
        json_data = json.dumps(data, indent=4, default=str).encode('utf-8')
        encrypted_token = f.encrypt(json_data)
        
        return {
            "salt": base64.urlsafe_b64encode(salt).decode('utf-8'),
            "dados": encrypted_token.decode('utf-8')
        }

    @staticmethod
    def decrypt_data(encrypted_package: dict, password: str) -> Optional[dict]:
        """
        Descriptografa o pacote de dados.
        Levanta InvalidToken se a senha estiver incorreta.
        """
        try:
            salt = base64.urlsafe_b64decode(encrypted_package['salt'].encode('utf-8'))
            token = encrypted_package['dados'].encode('utf-8')
            
            key = SecurityService._derive_key(password, salt)
            f = Fernet(key)
            
            decrypted_data = f.decrypt(token)
            return json.loads(decrypted_data.decode('utf-8'))
        except InvalidToken:
            return None
        except Exception as e:
            print(f"Erro crítico de descriptografia: {e}")
            return None

# --- CAMADA DE DADOS E NEGÓCIO ---

class PlanoContasService:
    def __init__(self):
        self.df = pd.DataFrame(columns=["Código", "Descrição", "Tipo", "Categoria"])
    
    def to_list(self):
        return self.df.to_dict(orient='records')
    
    def from_list(self, data):
        self.df = pd.DataFrame(data) if data else pd.DataFrame(columns=["Código", "Descrição", "Tipo", "Categoria"])

    def adicionar(self, codigo, descricao, tipo, categoria):
        if codigo in self.df["Código"].values:
            raise ValueError("Código já existente no Plano de Contas.")
        nova = {"Código": codigo, "Descrição": descricao, "Tipo": tipo, "Categoria": categoria}
        self.df = pd.concat([self.df, pd.DataFrame([nova])], ignore_index=True)

    def atualizar(self, idx, codigo, descricao, tipo, categoria):
        # Verifica duplicidade ignorando o registro atual
        if (self.df["Código"] == codigo).sum() > 1 if idx in self.df.index else (self.df["Código"] == codigo).any():
             raise ValueError("Código duplicado.")
        self.df.loc[idx] = {"Código": codigo, "Descrição": descricao, "Tipo": tipo, "Categoria": categoria}

    def deletar(self, idx):
        self.df.drop(idx, inplace=True)
        self.df.reset_index(drop=True, inplace=True)

class LancamentoService:
    def __init__(self):
        self.lancamentos: List[Dict] = []
        self.next_id = 1

    def to_list(self):
        return self.lancamentos

    def from_list(self, data):
        self.lancamentos = data if data else []
        if self.lancamentos:
            # Converte strings de data para date objects
            for l in self.lancamentos:
                if isinstance(l.get('data'), str):
                    l['data'] = datetime.strptime(l['data'], "%Y-%m-%d").date()
            self.next_id = max(l['id'] for l in self.lancamentos) + 1

    def validar_partida_dobrada(self, itens):
        total_debito = sum(i['Valor'] for i in itens if i['Tipo'] == 'Débito')
        total_credito = sum(i['Valor'] for i in itens if i['Tipo'] == 'Crédito')
        
        if total_debito == 0 or total_credito == 0:
            raise ValueError("O lançamento deve conter pelo menos um débito e um crédito.")
        
        if abs(total_debito - total_credito) > 0.001: # Tolerância para ponto flutuante
            raise ValueError(f"Partida dobrada inválida! Diferença de R$ {abs(total_debito - total_credito):.2f}")

    def adicionar(self, data, historico, itens):
        self.validar_partida_dobrada(itens)
        novo = {
            "id": self.next_id,
            "data": data,
            "historico": historico,
            "itens": itens
        }
        self.lancamentos.append(novo)
        self.next_id += 1

    def atualizar(self, id_lanc, data, historico, itens):
        self.validar_partida_dobrada(itens)
        for i, l in enumerate(self.lancamentos):
            if l['id'] == id_lanc:
                self.lancamentos[i] = {"id": id_lanc, "data": data, "historico": historico, "itens": itens}
                return

    def deletar(self, id_lanc):
        self.lancamentos = [l for l in self.lancamentos if l['id'] != id_lanc]

# --- COMPONENTES DE INTERFACE ---

class ModernStyle:
    @staticmethod
    def configure():
        style = ttk.Style()
        style.theme_use('clam')
        
        # Treeview (Tabelas)
        style.configure("Treeview", 
                        background=CONFIG_THEME['tree_bg'],
                        foreground=CONFIG_THEME['text_light'],
                        fieldbackground=CONFIG_THEME['tree_field_bg'],
                        borderwidth=0, rowheight=25)
        style.map("Treeview", background=[('selected', CONFIG_THEME['accent'])])
        
        style.configure("Treeview.Heading", 
                        background=CONFIG_THEME['bg_panel'], 
                        foreground=CONFIG_THEME['text_light'], 
                        relief="flat", font=CONFIG_THEME['font_normal'])
        style.map("Treeview.Heading", background=[('active', CONFIG_THEME['accent_hover'])])

        # Botões
        style.configure("TButton", padding=6, background=CONFIG_THEME['bg_panel'], foreground=CONFIG_THEME['text_light'])
        style.configure("Accent.TButton", background=CONFIG_THEME['accent'], foreground="white", font=CONFIG_THEME['font_normal'], padding=8)
        style.map("Accent.TButton", background=[('active', CONFIG_THEME['accent_hover'])])
        
        # Entradas
        style.configure("TEntry", fieldbackground=CONFIG_THEME['tree_field_bg'], foreground="white", padding=5)
        style.configure("TCombobox", fieldbackground=CONFIG_THEME['tree_field_bg'], foreground="black", padding=5)

        # Labels
        style.configure("TLabel", background=CONFIG_THEME['bg_main'], foreground=CONFIG_THEME['text_light'])
        style.configure("Dark.TLabel", background=CONFIG_THEME['bg_dark'], foreground=CONFIG_THEME['text_light'])

class BaseFrame(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=CONFIG_THEME['bg_main'])
        self.controller = controller

# --- TELAS DO SISTEMA ---

class TelaLogin(tk.Toplevel):
    def __init__(self, parent, on_success_callback):
        super().__init__(parent)
        self.title("Login - Sistema Contábil ERP")
        self.geometry("400x300")
        self.configure(bg=CONFIG_THEME['bg_dark'])
        self.resizable(False, False)
        
        self.on_success = on_success_callback
        self.protocol("WM_DELETE_WINDOW", self.destroy_app) # Impede fechar sem logar
        
        # Layout
        container = tk.Frame(self, bg=CONFIG_THEME['bg_dark'])
        container.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(container, text="🔐 ACESSO SEGURO", font=CONFIG_THEME['font_logo'], 
                 bg=CONFIG_THEME['bg_dark'], fg=CONFIG_THEME['accent']).pack(pady=20)
        
        tk.Label(container, text="Senha Mestra:", bg=CONFIG_THEME['bg_dark'], fg="white").pack(pady=5)
        self.txt_senha = ttk.Entry(container, show="●", width=30, font=('Segoe UI', 11))
        self.txt_senha.pack(pady=5, ipady=5)
        self.txt_senha.bind("<Return>", self.verificar)
        
        ttk.Button(container, text="Entrar", command=self.verificar, style="Accent.TButton").pack(pady=20)
        
        self.status_label = tk.Label(container, text="", bg=CONFIG_THEME['bg_dark'], fg=CONFIG_THEME['danger'])
        self.status_label.pack()

    def verificar(self, event=None):
        senha = self.txt_senha.get()
        if not senha:
            self.status_label.config(text="Informe a senha.")
            return
            
        # Tenta carregar dados existentes
        if os.path.exists(CONFIG_THEME['data_file']):
            self._login_existente(senha)
        else:
            # Novo sistema
            self._novo_sistema(senha)

    def _login_existente(self, senha):
        try:
            with open(CONFIG_THEME['data_file'], 'r') as f:
                file_content = json.load(f)
            
            dados = SecurityService.decrypt_data(file_content, senha)
            if dados:
                self.destroy()
                self.on_success(senha, dados)
            else:
                self.status_label.config(text="Senha incorreta ou arquivo corrompido.")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao ler arquivo de dados: {e}")

    def _novo_sistema(self, senha):
        # Cria estrutura inicial vazia
        dados_iniciais = {
            "contas": [],
            "lancamentos": [],
            "next_id": 1
        }
        try:
            encrypted_pkg = SecurityService.encrypt_data(dados_iniciais, senha)
            with open(CONFIG_THEME['data_file'], 'w') as f:
                json.dump(encrypted_pkg, f)
            
            self.destroy()
            self.on_success(senha, dados_iniciais)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao criar arquivo seguro: {e}")

    def destroy_app(self):
        self.master.destroy()

class TelaContas(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.service = controller.conta_service
        
        # Título
        tk.Label(self, text="📒 Plano de Contas", font=CONFIG_THEME['font_title'], 
                 bg=CONFIG_THEME['bg_main'], fg=CONFIG_THEME['text_light']).pack(pady=20, padx=20, anchor="w")

        # Toolbar
        toolbar = tk.Frame(self, bg=CONFIG_THEME['bg_main'])
        toolbar.pack(fill="x", padx=20, pady=5)
        
        ttk.Button(toolbar, text="➕ Nova Conta", command=lambda: self.abrir_modal(), style="Accent.TButton").pack(side="left", padx=5)
        ttk.Button(toolbar, text="✏️ Editar", command=self.editar_selecionado).pack(side="left", padx=5)
        ttk.Button(toolbar, text="🗑️ Excluir", command=self.deletar_selecionado).pack(side="left", padx=5)

        # Tabela
        cols = ["Código", "Descrição", "Tipo", "Categoria"]
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        
        self.tree.heading("Código", text="Código")
        self.tree.heading("Descrição", text="Descrição")
        self.tree.heading("Tipo", text="Tipo")
        self.tree.heading("Categoria", text="Categoria")
        
        self.tree.column("Código", width=120)
        self.tree.column("Descrição", width=300)
        self.tree.column("Tipo", width=100, anchor="center")
        self.tree.column("Categoria", width=100, anchor="center")
        
        self.tree.pack(fill="both", expand=True, padx=20, pady=10)

    def atualizar_tabela(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for _, row in self.service.df.iterrows():
            self.tree.insert("", "end", values=(row['Código'], row['Descrição'], row['Tipo'], row['Categoria']))

    def editar_selecionado(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecione uma conta para editar.")
            return
        idx = self.tree.index(selected[0])
        valores = self.tree.item(selected[0])['values']
        self.abrir_modal(idx, valores)

    def deletar_selecionado(self):
        selected = self.tree.selection()
        if not selected:
            return
        if messagebox.askyesno("Confirmação", "Deseja excluir esta conta?"):
            idx = self.tree.index(selected[0])
            try:
                self.service.deletar(idx)
                self.controller.salvar_dados()
                self.atualizar_tabela()
                messagebox.showinfo("Sucesso", "Conta removida.")
            except Exception as e:
                messagebox.showerror("Erro", str(e))

    def abrir_modal(self, idx=None, valores=None):
        ModalConta(self, idx, valores)

class ModalConta(tk.Toplevel):
    def __init__(self, parent, idx, valores):
        super().__init__(parent)
        self.parent = parent
        self.idx = idx
        
        self.title("Editar Conta" if idx is not None else "Nova Conta")
        self.geometry("400x300")
        self.configure(bg=CONFIG_THEME['bg_panel'])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        frame = tk.Frame(self, bg=CONFIG_THEME['bg_panel'], padx=20, pady=20)
        frame.pack(fill="both", expand=True)

        # Campos
        tk.Label(frame, text="Código:", bg=CONFIG_THEME['bg_panel'], fg="white").grid(row=0, column=0, sticky="w", pady=5)
        self.txt_codigo = ttk.Entry(frame, width=30)
        self.txt_codigo.grid(row=0, column=1, pady=5)

        tk.Label(frame, text="Descrição:", bg=CONFIG_THEME['bg_panel'], fg="white").grid(row=1, column=0, sticky="w", pady=5)
        self.txt_desc = ttk.Entry(frame, width=30)
        self.txt_desc.grid(row=1, column=1, pady=5)

        tk.Label(frame, text="Tipo:", bg=CONFIG_THEME['bg_panel'], fg="white").grid(row=2, column=0, sticky="w", pady=5)
        self.cmb_tipo = ttk.Combobox(frame, values=["Sintética", "Analítica"], state="readonly", width=27)
        self.cmb_tipo.grid(row=2, column=1, pady=5)

        tk.Label(frame, text="Categoria:", bg=CONFIG_THEME['bg_panel'], fg="white").grid(row=3, column=0, sticky="w", pady=5)
        self.cmb_cat = ttk.Combobox(frame, values=["Ativo", "Passivo", "Receita", "Despesa"], state="readonly", width=27)
        self.cmb_cat.grid(row=3, column=1, pady=5)

        if valores:
            self.txt_codigo.insert(0, valores[0])
            self.txt_desc.insert(0, valores[1])
            self.cmb_tipo.set(valores[2])
            self.cmb_cat.set(valores[3])

        ttk.Button(frame, text="Salvar", command=self.salvar, style="Accent.TButton").grid(row=4, column=1, pady=20, sticky="e")

    def salvar(self):
        dados = {
            "codigo": self.txt_codigo.get().strip(),
            "descricao": self.txt_desc.get().strip(),
            "tipo": self.cmb_tipo.get(),
            "categoria": self.cmb_cat.get()
        }
        
        if not dados["codigo"] or not dados["descricao"]:
            messagebox.showerror("Erro", "Preencha todos os campos.")
            return

        try:
            if self.idx is None:
                self.parent.service.adicionar(**dados)
            else:
                self.parent.service.atualizar(self.idx, **dados)
            
            self.parent.controller.salvar_dados()
            self.parent.atualizar_tabela()
            self.destroy()
            messagebox.showinfo("Sucesso", "Operação realizada!")
        except ValueError as e:
            messagebox.showerror("Erro", str(e))

class TelaLancamentos(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.service = controller.lancamento_service
        
        tk.Label(self, text="💰 Lançamentos Contábeis", font=CONFIG_THEME['font_title'], 
                 bg=CONFIG_THEME['bg_main'], fg=CONFIG_THEME['text_light']).pack(pady=20, padx=20, anchor="w")

        toolbar = tk.Frame(self, bg=CONFIG_THEME['bg_main'])
        toolbar.pack(fill="x", padx=20, pady=5)
        
        ttk.Button(toolbar, text="➕ Novo Lançamento", command=lambda: self.abrir_modal(), style="Accent.TButton").pack(side="left", padx=5)
        ttk.Button(toolbar, text="✏️ Editar", command=self.editar_selecionado).pack(side="left", padx=5)
        ttk.Button(toolbar, text="🗑️ Excluir", command=self.deletar_selecionado).pack(side="left", padx=5)

        cols = ["ID", "Data", "Histórico", "Débitos", "Créditos", "Valor Total"]
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        
        self.tree.heading("ID", text="ID")
        self.tree.heading("Data", text="Data")
        self.tree.heading("Histórico", text="Histórico")
        self.tree.heading("Débitos", text="Débitos")
        self.tree.heading("Créditos", text="Créditos")
        self.tree.heading("Valor Total", text="Valor (R$)")
        
        self.tree.column("ID", width=50, anchor="center")
        self.tree.column("Data", width=100, anchor="center")
        self.tree.column("Histórico", width=250)
        self.tree.column("Débitos", width=150)
        self.tree.column("Créditos", width=150)
        self.tree.column("Valor Total", width=120, anchor="e")

        self.tree.pack(fill="both", expand=True, padx=20, pady=10)

    def atualizar_tabela(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        for l in self.service.lancamentos:
            debitos = ", ".join([x['Conta'] for x in l['itens'] if x['Tipo'] == 'Débito'])
            creditos = ", ".join([x['Conta'] for x in l['itens'] if x['Tipo'] == 'Crédito'])
            valor = sum([x['Valor'] for x in l['itens'] if x['Tipo'] == 'Débito'])
            
            self.tree.insert("", "end", values=(
                l['id'], 
                l['data'].strftime("%d/%m/%Y"), 
                l['historico'], 
                debitos, 
                creditos, 
                f"{valor:,.2f}"
            ))

    def editar_selecionado(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecione um lançamento.")
            return
        id_lanc = int(self.tree.item(selected[0])['values'][0])
        dados = next((l for l in self.service.lancamentos if l['id'] == id_lanc), None)
        if dados:
            self.abrir_modal(dados)

    def deletar_selecionado(self):
        selected = self.tree.selection()
        if not selected: return
        id_lanc = int(self.tree.item(selected[0])['values'][0])
        if messagebox.askyesno("Confirmação", "Excluir lançamento?"):
            self.service.deletar(id_lanc)
            self.controller.salvar_dados()
            self.atualizar_tabela()

    def abrir_modal(self, dados=None):
        ModalLancamento(self, dados)

class ModalLancamento(tk.Toplevel):
    def __init__(self, parent, dados):
        super().__init__(parent)
        self.parent = parent
        self.dados = dados # Para edição
        self.itens_temp = []
        
        self.title("Editar Lançamento" if dados else "Novo Lançamento")
        self.geometry("900x600")
        self.configure(bg=CONFIG_THEME['bg_panel'])
        self.transient(parent)
        self.grab_set()

        # Cabeçalho
        header = tk.Frame(self, bg=CONFIG_THEME['bg_panel'], pady=15)
        header.pack(fill="x")
        
        tk.Label(header, text="Data:", bg=CONFIG_THEME['bg_panel'], fg="white", font=CONFIG_THEME['font_normal']).pack(side="left", padx=5)
        self.txt_data = ttk.Entry(header, width=15)
        self.txt_data.pack(side="left", padx=5)
        
        tk.Label(header, text="Histórico:", bg=CONFIG_THEME['bg_panel'], fg="white", font=CONFIG_THEME['font_normal']).pack(side="left", padx=5)
        self.txt_hist = ttk.Entry(header, width=60)
        self.txt_hist.pack(side="left", padx=5)

        # Área de Itens
        tree_frame = tk.Frame(self, bg=CONFIG_THEME['bg_panel'])
        tree_frame.pack(fill="both", expand=True, padx=20, pady=10)

        cols = ("Tipo", "Conta", "Valor")
        self.tree_itens = ttk.Treeview(tree_frame, columns=cols, show="headings", height=15)
        self.tree_itens.heading("Tipo", text="Tipo")
        self.tree_itens.heading("Conta", text="Conta")
        self.tree_itens.heading("Valor", text="Valor R$")
        
        self.tree_itens.column("Tipo", width=100, anchor="center")
        self.tree_itens.column("Conta", width=200)
        self.tree_itens.column("Valor", width=150, anchor="e")
        self.tree_itens.pack(side="left", fill="both", expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_itens.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree_itens.configure(yscrollcommand=scrollbar.set)

        # Controles de Item
        ctrl_item_frame = tk.Frame(self, bg=CONFIG_THEME['bg_panel'])
        ctrl_item_frame.pack(fill="x", padx=20, pady=5)
        
        # Inputs para adicionar item
        tk.Label(ctrl_item_frame, text="Tipo:", bg=CONFIG_THEME['bg_panel'], fg="white").pack(side="left", padx=2)
        self.cmb_tipo_item = ttk.Combobox(ctrl_item_frame, values=["Débito", "Crédito"], state="readonly", width=10)
        self.cmb_tipo_item.set("Débito")
        self.cmb_tipo_item.pack(side="left", padx=2)
        
        tk.Label(ctrl_item_frame, text="Conta:", bg=CONFIG_THEME['bg_panel'], fg="white").pack(side="left", padx=2)
        self.cmb_conta_item = ttk.Combobox(ctrl_item_frame, values=sorted(self.parent.controller.conta_service.df["Código"].tolist()), state="readonly", width=15)
        if self.cmb_conta_item['values']: self.cmb_conta_item.current(0)
        self.cmb_conta_item.pack(side="left", padx=2)

        tk.Label(ctrl_item_frame, text="Valor:", bg=CONFIG_THEME['bg_panel'], fg="white").pack(side="left", padx=2)
        self.txt_valor_item = ttk.Entry(ctrl_item_frame, width=15)
        self.txt_valor_item.pack(side="left", padx=2)

        ttk.Button(ctrl_item_frame, text="➕ Add", command=self.adicionar_item).pack(side="left", padx=10)
        ttk.Button(ctrl_item_frame, text="➖ Rem", command=self.remover_item).pack(side="left")

        # Totais
        footer = tk.Frame(self, bg=CONFIG_THEME['bg_dark'], pady=10)
        footer.pack(fill="x", padx=20, pady=10)
        
        self.lbl_tot_deb = tk.Label(footer, text="Total Débito: R$ 0.00", bg=CONFIG_THEME['bg_dark'], fg=CONFIG_THEME['success'], font=CONFIG_THEME['font_header'])
        self.lbl_tot_deb.pack(side="left", padx=20)
        
        self.lbl_tot_cred = tk.Label(footer, text="Total Crédito: R$ 0.00", bg=CONFIG_THEME['bg_dark'], fg=CONFIG_THEME['accent'], font=CONFIG_THEME['font_header'])
        self.lbl_tot_cred.pack(side="left", padx=20)
        
        self.lbl_diff = tk.Label(footer, text="Diferença: R$ 0.00", bg=CONFIG_THEME['bg_dark'], fg=CONFIG_THEME['danger'], font=CONFIG_THEME['font_header'])
        self.lbl_diff.pack(side="right", padx=20)

        # Botões Salvar/Cancelar
        b_frame = tk.Frame(self, bg=CONFIG_THEME['bg_panel'])
        b_frame.pack(pady=10)
        ttk.Button(b_frame, text="Salvar Lançamento", command=self.salvar, style="Accent.TButton").pack(side="left", padx=10)
        ttk.Button(b_frame, text="Cancelar", command=self.destroy).pack(side="left", padx=10)

        # Carregar dados se edição
        if dados:
            self.txt_data.insert(0, dados['data'].strftime("%d/%m/%Y"))
            self.txt_hist.insert(0, dados['historico'])
            self.itens_temp = dados['itens'].copy()
            self.atualizar_lista_itens()
        else:
            self.txt_data.insert(0, date.today().strftime("%d/%m/%Y"))

    def adicionar_item(self):
        try:
            valor_str = self.txt_valor_item.get().replace(",", ".")
            valor = float(valor_str)
            if valor <= 0: raise ValueError
            
            item = {
                "Tipo": self.cmb_tipo_item.get(),
                "Conta": self.cmb_conta_item.get(),
                "Valor": valor
            }
            self.itens_temp.append(item)
            self.atualizar_lista_itens()
            self.txt_valor_item.delete(0, tk.END)
        except ValueError:
            messagebox.showerror("Erro", "Valor inválido.")

    def remover_item(self):
        sel = self.tree_itens.selection()
        if sel:
            idx = self.tree_itens.index(sel[0])
            del self.itens_temp[idx]
            self.atualizar_lista_itens()

    def atualizar_lista_itens(self):
        for i in self.tree_itens.get_children():
            self.tree_itens.delete(i)
        
        total_d, total_c = 0.0, 0.0
        for item in self.itens_temp:
            self.tree_itens.insert("", "end", values=(item['Tipo'], item['Conta'], f"{item['Valor']:,.2f}"))
            if item['Tipo'] == 'Débito': total_d += item['Valor']
            else: total_c += item['Valor']
            
        self.lbl_tot_deb.config(text=f"Total Débito: R$ {total_d:,.2f}")
        self.lbl_tot_cred.config(text=f"Total Crédito: R$ {total_c:,.2f}")
        diff = total_d - total_c
        self.lbl_diff.config(text=f"Diferença: R$ {diff:,.2f}")

    def salvar(self):
        try:
            data_obj = datetime.strptime(self.txt_data.get(), "%d/%m/%Y").date()
            hist = self.txt_hist.get()
            
            if self.dados:
                self.parent.service.atualizar(self.dados['id'], data_obj, hist, self.itens_temp)
            else:
                self.parent.service.adicionar(data_obj, hist, self.itens_temp)
            
            self.parent.controller.salvar_dados()
            self.parent.atualizar_tabela()
            self.destroy()
            messagebox.showinfo("Sucesso", "Lançamento salvo!")
        except ValueError as e:
            messagebox.showerror("Erro de Validação", str(e))

class TelaBalancete(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        
        tk.Label(self, text="📊 Balancete de Verificação", font=CONFIG_THEME['font_title'], 
                 bg=CONFIG_THEME['bg_main'], fg=CONFIG_THEME['text_light']).pack(pady=20, padx=20, anchor="w")
        
        toolbar = tk.Frame(self, bg=CONFIG_THEME['bg_main'])
        toolbar.pack(fill="x", padx=20, pady=5)
        ttk.Button(toolbar, text="🔄 Calcular", command=self.calcular, style="Accent.TButton").pack(side="left")
        
        cols = ("Código", "Descrição", "Débito", "Crédito", "Saldo")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        
        self.tree.heading("Código", text="Código")
        self.tree.heading("Descrição", text="Descrição")
        self.tree.heading("Débito", text="Débito")
        self.tree.heading("Crédito", text="Crédito")
        self.tree.heading("Saldo", text="Saldo")
        
        self.tree.column("Código", width=100)
        self.tree.column("Descrição", width=300)
        self.tree.column("Débito", width=120, anchor="e")
        self.tree.column("Crédito", width=120, anchor="e")
        self.tree.column("Saldo", width=120, anchor="e")
        
        self.tree.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.footer = tk.Frame(self, bg=CONFIG_THEME['bg_dark'])
        self.footer.pack(fill="x", padx=20, pady=10)
        self.lbl_status = tk.Label(self.footer, text="Aguardando cálculo...", bg=CONFIG_THEME['bg_dark'], fg="white", font=CONFIG_THEME['font_header'])
        self.lbl_status.pack(pady=5)

    def calcular(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        
        saldos = {}
        # Inicializa com contas
        for _, row in self.controller.conta_service.df.iterrows():
            saldos[row['Código']] = {'Debito': 0.0, 'Credito': 0.0, 'Desc': row['Descrição']}
            
        # Soma lançamentos
        for l in self.controller.lancamento_service.lancamentos:
            for item in l['itens']:
                conta = item['Conta']
                if conta in saldos:
                    if item['Tipo'] == 'Débito': saldos[conta]['Debito'] += item['Valor']
                    else: saldos[conta]['Credito'] += item['Valor']
        
        total_d, total_c = 0.0, 0.0
        
        for cod in sorted(saldos.keys()):
            d = saldos[cod]['Debito']
            c = saldos[cod]['Credito']
            saldo = d - c
            total_d += d
            total_c += c
            
            self.tree.insert("", "end", values=(
                cod, saldos[cod]['Desc'], 
                f"{d:,.2f}", f"{c:,.2f}", f"{saldo:,.2f}"
            ))
        
        diff = abs(total_d - total_c)
        if diff < 0.01:
            self.lbl_status.config(text=f"✅ Validado! Total D: {total_d:,.2f} | Total C: {total_c:,.2f}", fg=CONFIG_THEME['success'])
        else:
            self.lbl_status.config(text=f"❌ Diferença: {diff:,.2f}", fg=CONFIG_THEME['danger'])

class TelaDRE(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        
        tk.Label(self, text="📈 Demonstração do Resultado (DRE)", font=CONFIG_THEME['font_title'], 
                 bg=CONFIG_THEME['bg_main'], fg=CONFIG_THEME['text_light']).pack(pady=20, padx=20, anchor="w")
        
        container = tk.Frame(self, bg=CONFIG_THEME['bg_main'])
        container.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Coluna Receitas
        col_rec = tk.Frame(container, bg=CONFIG_THEME['bg_panel'])
        col_rec.pack(side="left", fill="both", expand=True, padx=5)
        
        tk.Label(col_rec, text="RECEITAS", font=CONFIG_THEME['font_header'], bg=CONFIG_THEME['bg_panel'], fg=CONFIG_THEME['success']).pack(pady=10)
        self.tree_rec = ttk.Treeview(col_rec, columns=("Desc", "Valor"), show="headings", height=15)
        self.tree_rec.heading("Desc", text="Descrição")
        self.tree_rec.heading("Valor", text="Valor")
        self.tree_rec.column("Desc", width=200)
        self.tree_rec.column("Valor", width=100, anchor="e")
        self.tree_rec.pack(fill="both", expand=True, padx=5, pady=5)
        self.lbl_total_rec = tk.Label(col_rec, text="Total: R$ 0.00", font=CONFIG_THEME['font_header'], bg=CONFIG_THEME['bg_panel'], fg="white")
        self.lbl_total_rec.pack(pady=10)

        # Coluna Despesas
        col_desp = tk.Frame(container, bg=CONFIG_THEME['bg_panel'])
        col_desp.pack(side="left", fill="both", expand=True, padx=5)
        
        tk.Label(col_desp, text="DESPESAS", font=CONFIG_THEME['font_header'], bg=CONFIG_THEME['bg_panel'], fg=CONFIG_THEME['danger']).pack(pady=10)
        self.tree_desp = ttk.Treeview(col_desp, columns=("Desc", "Valor"), show="headings", height=15)
        self.tree_desp.heading("Desc", text="Descrição")
        self.tree_desp.heading("Valor", text="Valor")
        self.tree_desp.column("Desc", width=200)
        self.tree_desp.column("Valor", width=100, anchor="e")
        self.tree_desp.pack(fill="both", expand=True, padx=5, pady=5)
        self.lbl_total_desp = tk.Label(col_desp, text="Total: R$ 0.00", font=CONFIG_THEME['font_header'], bg=CONFIG_THEME['bg_panel'], fg="white")
        self.lbl_total_desp.pack(pady=10)

        # Footer
        footer = tk.Frame(self, bg=CONFIG_THEME['bg_dark'])
        footer.pack(fill="x", padx=20, pady=10)
        ttk.Button(footer, text="Calcular DRE", command=self.calcular, style="Accent.TButton").pack(side="left", padx=10)
        self.lbl_resultado = tk.Label(footer, text="Resultado Líquido: R$ 0.00", font=CONFIG_THEME['font_title'], bg=CONFIG_THEME['bg_dark'], fg="white")
        self.lbl_resultado.pack(side="right", padx=10)

    def calcular(self):
        for t in [self.tree_rec, self.tree_desp]:
            for i in t.get_children(): t.delete(i)
            
        receitas = {}
        despesas = {}
        
        for l in self.controller.lancamento_service.lancamentos:
            for item in l['itens']:
                conta = item['Conta']
                info = self.controller.conta_service.df[self.controller.conta_service.df['Código'] == conta]
                if not info.empty:
                    cat = info.iloc[0]['Categoria']
                    desc = info.iloc[0]['Descrição']
                    valor = item['Valor']
                    
                    key = (conta, desc)
                    if cat == "Receita":
                        if item['Tipo'] == "Crédito": receitas[key] = receitas.get(key, 0) + valor
                        else: receitas[key] = receitas.get(key, 0) - valor
                    elif cat == "Despesa":
                        if item['Tipo'] == "Débito": despesas[key] = despesas.get(key, 0) + valor
                        else: despesas[key] = despesas.get(key, 0) - valor

        total_rec = sum(receitas.values())
        total_desp = sum(despesas.values())
        
        for (cod, desc), val in receitas.items():
            if val > 0: self.tree_rec.insert("", "end", values=(f"{cod} - {desc}", f"{val:,.2f}"))
            
        for (cod, desc), val in despesas.items():
            if val > 0: self.tree_desp.insert("", "end", values=(f"{cod} - {desc}", f"{val:,.2f}"))
            
        self.lbl_total_rec.config(text=f"Total: R$ {total_rec:,.2f}")
        self.lbl_total_desp.config(text=f"Total: R$ {total_desp:,.2f}")
        
        res = total_rec - total_desp
        cor = CONFIG_THEME['success'] if res >= 0 else CONFIG_THEME['danger']
        self.lbl_resultado.config(text=f"Resultado Líquido: R$ {res:,.2f}", fg=cor)

class TelaBackup(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        
        tk.Label(self, text="💾 Backup e Segurança", font=CONFIG_THEME['font_title'], 
                 bg=CONFIG_THEME['bg_main'], fg=CONFIG_THEME['text_light']).pack(pady=20, padx=20, anchor="w")
        
        container = tk.Frame(self, bg=CONFIG_THEME['bg_panel'], padx=40, pady=40)
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Exportar
        exp_frame = tk.LabelFrame(container, text="Exportar Backup", bg=CONFIG_THEME['bg_panel'], fg="white", font=CONFIG_THEME['font_header'])
        exp_frame.pack(fill="x", pady=10)
        
        tk.Label(exp_frame, text="Crie uma cópia segura dos seus dados criptografados.", bg=CONFIG_THEME['bg_panel'], fg=CONFIG_THEME['text_gray']).pack(pady=5)
        ttk.Button(exp_frame, text="📥 Exportar para Arquivo .enc", command=self.exportar, style="Accent.TButton").pack(pady=10)
        
        # Importar
        imp_frame = tk.LabelFrame(container, text="Restaurar Backup", bg=CONFIG_THEME['bg_panel'], fg="white", font=CONFIG_THEME['font_header'])
        imp_frame.pack(fill="x", pady=10)
        
        tk.Label(imp_frame, text="Restaura os dados de um arquivo. Requer a senha usada na exportação.", bg=CONFIG_THEME['bg_panel'], fg=CONFIG_THEME['text_gray']).pack(pady=5)
        ttk.Button(imp_frame, text="📤 Selecionar Arquivo e Restaurar", command=self.importar).pack(pady=10)

    def exportar(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".enc", filetypes=[("Encrypted Files", "*.enc")])
        if not file_path: return
        
        # Coleta dados atuais em memória para exportar
        dados = {
            "contas": self.controller.conta_service.to_list(),
            "lancamentos": self.controller.lancamento_service.to_list(),
            "next_id": self.controller.lancamento_service.next_id
        }
        
        # Pede senha específica para o backup (opcional, mas recomendado para portabilidade)
        # Para simplificar, usaremos a senha mestra atual (ou poderíamos pedir uma nova)
        # Aqui pedimos uma senha para o arquivo de backup.
        senha = tk.simpledialog.askstring("Senha do Backup", "Defina uma senha para este arquivo:", show='●')
        if not senha: return

        try:
            encrypted_pkg = SecurityService.encrypt_data(dados, senha)
            with open(file_path, 'w') as f:
                json.dump(encrypted_pkg, f)
            messagebox.showinfo("Sucesso", "Backup exportado com segurança!")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao exportar: {e}")

    def importar(self):
        file_path = filedialog.askopenfilename(filetypes=[("Encrypted Files", "*.enc")])
        if not file_path: return
        
        senha = tk.simpledialog.askstring("Senha", "Digite a senha deste arquivo:", show='●')
        if not senha: return

        try:
            with open(file_path, 'r') as f:
                file_content = json.load(f)
            
            dados = SecurityService.decrypt_data(file_content, senha)
            if not dados:
                messagebox.showerror("Erro", "Senha incorreta ou arquivo corrompido.")
                return
                
            if messagebox.askyesno("Confirmação", "Isso substituirá TODOS os dados atuais. Continuar?"):
                self.controller.conta_service.from_list(dados.get('contas', []))
                self.controller.lancamento_service.from_list(dados.get('lancamentos', []))
                # Salva imediatamente os dados restaurados com a senha mestra atual
                self.controller.salvar_dados()
                messagebox.showinfo("Sucesso", "Dados restaurados com sucesso!")
                self.controller.mostrar_tela("contas")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao restaurar: {e}")

# --- CONTROLADOR PRINCIPAL ---

class SistemaContabilApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sistema Contábil ERP Pro")
        self.geometry("1200x700")
        self.minsize(1200, 700)
        self.configure(bg=CONFIG_THEME['bg_dark'])
        
        self.senha_mestra = None
        self.conta_service = PlanoContasService()
        self.lancamento_service = LancamentoService()
        
        # Configurar Estilos
        ModernStyle.configure()
        
        # Estrutura Principal
        self.main_container = tk.Frame(self, bg=CONFIG_THEME['bg_dark'])
        self.main_container.pack(fill="both", expand=True)
        
        # Sidebar
        self.sidebar = tk.Frame(self.main_container, bg=CONFIG_THEME['bg_sidebar'], width=220)
        self.sidebar.pack(side="left", fill="y")
        
        self._criar_menu_lateral()
        
        # Área Principal
        self.main_area = tk.Frame(self.main_container, bg=CONFIG_THEME['bg_main'])
        self.main_area.pack(side="right", fill="both", expand=True)
        
        # Status Bar
        self.status_bar = tk.Label(self, text="Status: Sistema Seguro | Data: " + datetime.now().strftime("%d/%m/%Y"), 
                                   bg=CONFIG_THEME['bg_panel'], fg=CONFIG_THEME['text_gray'], anchor="w", padx=10)
        self.status_bar.pack(side="bottom", fill="x")
        
        # Telas
        self.frames = {}
        self._criar_telas()
        
        # Iniciar fluxo de login
        self.after(100, self.iniciar_login)

    def _criar_menu_lateral(self):
        tk.Label(self.sidebar, text="CONTABIL\nERP", font=CONFIG_THEME['font_logo'], 
                 bg=CONFIG_THEME['bg_sidebar'], fg=CONFIG_THEME['accent']).pack(pady=30)
        
        menus = [
            ("📒 Plano de Contas", "contas"),
            ("💰 Lançamentos", "lancamentos"),
            ("📊 Balancete", "balancete"),
            ("📈 DRE", "dre"),
            ("💾 Backup", "backup")
        ]
        
        self.menu_buttons = {}
        for text, key in menus:
            btn = tk.Button(self.sidebar, text=text, font=CONFIG_THEME['font_normal'],
                           bg=CONFIG_THEME['bg_sidebar'], fg=CONFIG_THEME['text_gray'],
                           bd=0, activebackground=CONFIG_THEME['accent'], 
                           activeforeground="white", cursor="hand2",
                           command=lambda k=key: self.mostrar_tela(k))
            btn.pack(fill="x", pady=2, padx=10)
            self.menu_buttons[key] = btn

    def _criar_telas(self):
        self.frames["contas"] = TelaContas(self.main_area, self)
        self.frames["lancamentos"] = TelaLancamentos(self.main_area, self)
        self.frames["balancete"] = TelaBalancete(self.main_area, self)
        self.frames["dre"] = TelaDRE(self.main_area, self)
        self.frames["backup"] = TelaBackup(self.main_area, self)

    def iniciar_login(self):
        # Esconde a janela principal até logar
        self.withdraw()
        TelaLogin(self, self.carregar_dados)

    def carregar_dados(self, senha, dados_json):
        self.senha_mestra = senha
        self.deiconify() # Mostra janela principal
        
        # Carrega serviços
        self.conta_service.from_list(dados_json.get("contas", []))
        self.lancamento_service.from_list(dados_json.get("lancamentos", []))
        
        self.mostrar_tela("contas")

    def salvar_dados(self):
        if not self.senha_mestra:
            messagebox.showerror("Erro", "Sessão inválida.")
            return

        dados = {
            "contas": self.conta_service.to_list(),
            "lancamentos": self.lancamento_service.to_list(),
            "next_id": self.lancamento_service.next_id
        }
        
        try:
            encrypted_pkg = SecurityService.encrypt_data(dados, self.senha_mestra)
            with open(CONFIG_THEME['data_file'], 'w') as f:
                json.dump(encrypted_pkg, f)
            self.status_bar.config(text=f"Status: Dados salvos com segurança às {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            messagebox.showerror("Erro Crítico", f"Não foi possível salvar os dados: {e}")

    def mostrar_tela(self, tela_key):
        for frame in self.frames.values():
            frame.pack_forget()
        
        self.frames[tela_key].pack(fill="both", expand=True)
        
        # Atualiza tabela ao mostrar
        if tela_key == "contas": self.frames[tela_key].atualizar_tabela()
        if tela_key == "lancamentos": self.frames[tela_key].atualizar_tabela()
        
        # Visual do menu
        for key, btn in self.menu_buttons.items():
            if key == tela_key:
                btn.configure(bg=CONFIG_THEME['accent'], fg="white")
            else:
                btn.configure(bg=CONFIG_THEME['bg_sidebar'], fg=CONFIG_THEME['text_gray'])

# --- PONTO DE ENTRADA ---
if __name__ == "__main__":
    # Necessário para o simpledialog no backup
    import tkinter.simpledialog
    
    app = SistemaContabilApp()
    app.mainloop()