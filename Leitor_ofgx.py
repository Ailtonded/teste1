import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import re

class OFXViewerApp:

    def __init__(self, root):

        self.root = root
        self.root.title("Leitor OFX Itaú")
        self.root.geometry("1400x750")

        self.df = pd.DataFrame()

        # =====================================
        # TOPO
        # =====================================
        frame_topo = tk.Frame(root)
        frame_topo.pack(fill="x", padx=10, pady=10)

        btn_abrir = tk.Button(
            frame_topo,
            text="Abrir OFX",
            command=self.abrir_ofx,
            bg="#1976D2",
            fg="white",
            font=("Arial", 10, "bold"),
            width=20,
            height=2
        )
        btn_abrir.pack(side="left", padx=5)

        btn_exportar = tk.Button(
            frame_topo,
            text="Exportar Excel",
            command=self.exportar_excel,
            bg="#2E7D32",
            fg="white",
            font=("Arial", 10, "bold"),
            width=20,
            height=2
        )
        btn_exportar.pack(side="left", padx=5)

        # =====================================
        # GRID
        # =====================================
        frame_grid = tk.Frame(root)
        frame_grid.pack(fill="both", expand=True, padx=10, pady=10)

        colunas = (
            "Data",
            "Movimento",
            "Valor Débito",
            "Valor Crédito",
            "Saldo",
            "Documento",
            "Histórico"
        )

        self.tree = ttk.Treeview(
            frame_grid,
            columns=colunas,
            show="headings"
        )

        for col in colunas:
            self.tree.heading(col, text=col)

        self.tree.column("Data", width=100)
        self.tree.column("Movimento", width=120)
        self.tree.column("Valor Débito", width=120)
        self.tree.column("Valor Crédito", width=120)
        self.tree.column("Saldo", width=120)
        self.tree.column("Documento", width=150)
        self.tree.column("Histórico", width=700)

        # Scroll Vertical
        scroll_y = ttk.Scrollbar(
            frame_grid,
            orient="vertical",
            command=self.tree.yview
        )

        # Scroll Horizontal
        scroll_x = ttk.Scrollbar(
            frame_grid,
            orient="horizontal",
            command=self.tree.xview
        )

        self.tree.configure(
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set
        )

        self.tree.pack(side="left", fill="both", expand=True)

        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")

        # =====================================
        # RODAPÉ
        # =====================================
        self.label_total = tk.Label(
            root,
            text="",
            font=("Arial", 10, "bold"),
            anchor="w"
        )

        self.label_total.pack(
            fill="x",
            padx=10,
            pady=5
        )

    # =====================================
    # ABRIR OFX
    # =====================================
    def abrir_ofx(self):

        caminho = filedialog.askopenfilename(
            title="Selecione o OFX",
            filetypes=[("Arquivos OFX", "*.ofx")]
        )

        if not caminho:
            return

        try:

            with open(caminho, "r", encoding="latin-1") as arquivo:
                conteudo = arquivo.read()

            transacoes = re.findall(
                r"<STMTTRN>(.*?)</STMTTRN>",
                conteudo,
                re.S
            )

            dados = []

            saldo = 0

            for t in transacoes:

                def pegar(tag):

                    resultado = re.search(
                        f"<{tag}>(.*)",
                        t
                    )

                    return resultado.group(1).strip() if resultado else ""

                # ==========================
                # DATA
                # ==========================
                data = pegar("DTPOSTED")[:8]

                data = f"{data[6:8]}/{data[4:6]}/{data[:4]}"

                # ==========================
                # VALOR
                # ==========================
                valor = float(pegar("TRNAMT"))

                # ==========================
                # MOVIMENTO
                # ==========================
                if valor < 0:
                    movimento = "DÉBITO"
                else:
                    movimento = "CRÉDITO"

                # ==========================
                # DÉBITO / CRÉDITO
                # ==========================
                valor_debito = abs(valor) if valor < 0 else 0

                valor_credito = valor if valor > 0 else 0

                # ==========================
                # SALDO
                # saldo anterior + credito - debito
                # ==========================
                saldo = saldo + valor_credito - valor_debito

                documento = pegar("CHECKNUM")

                historico = pegar("MEMO")

                dados.append({
                    "Data": data,
                    "Movimento": movimento,
                    "Valor Débito": valor_debito,
                    "Valor Crédito": valor_credito,
                    "Saldo": saldo,
                    "Documento": documento,
                    "Histórico": historico
                })

            self.df = pd.DataFrame(dados)

            self.carregar_grid()

            self.atualizar_totais()

            messagebox.showinfo(
                "Sucesso",
                f"{len(self.df)} movimentações carregadas."
            )

        except Exception as erro:

            messagebox.showerror(
                "Erro",
                str(erro)
            )

    # =====================================
    # CARREGAR GRID
    # =====================================
    def carregar_grid(self):

        for item in self.tree.get_children():
            self.tree.delete(item)

        for _, row in self.df.iterrows():

            tag = "credito" if row["Movimento"] == "CRÉDITO" else "debito"

            self.tree.insert(
                "",
                "end",
                values=(
                    row["Data"],
                    row["Movimento"],
                    f"{row['Valor Débito']:,.2f}" if row["Valor Débito"] > 0 else "",
                    f"{row['Valor Crédito']:,.2f}" if row["Valor Crédito"] > 0 else "",
                    f"{row['Saldo']:,.2f}",
                    row["Documento"],
                    row["Histórico"]
                ),
                tags=(tag,)
            )

        # ==========================
        # CORES
        # ==========================
        self.tree.tag_configure(
            "credito",
            foreground="green"
        )

        self.tree.tag_configure(
            "debito",
            foreground="red"
        )

    # =====================================
    # TOTALIZADORES
    # =====================================
    def atualizar_totais(self):

        total_debito = self.df["Valor Débito"].sum()

        total_credito = self.df["Valor Crédito"].sum()

        saldo_final = self.df["Saldo"].iloc[-1]

        texto = (
            f"Total Débito: {total_debito:,.2f}    |    "
            f"Total Crédito: {total_credito:,.2f}    |    "
            f"Saldo Final: {saldo_final:,.2f}"
        )

        self.label_total.config(text=texto)

    # =====================================
    # EXPORTAR EXCEL
    # =====================================
    def exportar_excel(self):

        if self.df.empty:

            messagebox.showwarning(
                "Aviso",
                "Nenhum dado carregado."
            )

            return

        caminho = filedialog.asksaveasfilename(
            title="Salvar Excel",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")]
        )

        if not caminho:
            return

        try:

            self.df.to_excel(
                caminho,
                index=False
            )

            messagebox.showinfo(
                "Sucesso",
                "Excel exportado com sucesso."
            )

        except Exception as erro:

            messagebox.showerror(
                "Erro",
                str(erro)
            )

# =====================================
# EXECUÇÃO
# =====================================
if __name__ == "__main__":

    root = tk.Tk()

    app = OFXViewerApp(root)

    root.mainloop()