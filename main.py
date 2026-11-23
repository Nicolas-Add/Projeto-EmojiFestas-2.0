import os
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path


# Arquivo do banco de dados SQLite.
# Localmente, utiliza emojifestas.db ao lado deste arquivo.
# No Render, pode utilizar um disco persistente via EMOJIFESTAS_DB_PATH.
DB_FILE = Path(os.environ.get("EMOJIFESTAS_DB_PATH", Path(__file__).parent / "emojifestas.db"))
DB_FILE.parent.mkdir(parents=True, exist_ok=True)
DURACAO_BASE = 4  # horas incluídas em toda festa
VALOR_HORA_EXTRA = 200.0


# ==========================================
# MODELOS (POO)
# ==========================================

@dataclass
class Salao:
    id: int
    nome: str
    capacidade: int
    acrescimo: float


@dataclass
class Combo:
    id: int
    nome: str
    preco: float
    descricao: str = ""


@dataclass
class Extra:
    id: int
    nome: str
    preco: float


@dataclass
class Cliente:
    id: int
    nome: str
    contato: str
    documento: str


@dataclass
class Festa:
    id: int
    salao_id: int
    cliente_id: int
    data: str
    inicio: str
    combo_id: int | None
    horas_extra: int = 0
    total: float = 0.0
    obs: str = ""
    extras: list[int] = field(default_factory=list)

    @property
    def duracao(self):
        return DURACAO_BASE + self.horas_extra

    def intervalo(self):
        ini = datetime.fromisoformat(f"{self.data}T{self.inicio}")
        return ini, ini + timedelta(hours=self.duracao)

    def conflita_com(self, outra: "Festa"):
        if self.salao_id != outra.salao_id or self.id == outra.id:
            return False
        a1, a2 = self.intervalo()
        b1, b2 = outra.intervalo()
        return a1 < b2 and b1 < a2


# ==========================================
# GERENCIADOR DE BANCO DE DADOS (SQLite + POO)
# ==========================================

class Banco:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE)
        self.conn.row_factory = sqlite3.Row
        self._criar_tabelas()
        if not self._tem_dados():
            self._dados_iniciais()

    def _criar_tabelas(self):
        cursor = self.conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS saloes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                capacidade INTEGER,
                acrescimo REAL
            );
            CREATE TABLE IF NOT EXISTS combos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                preco REAL,
                descricao TEXT
            );
            CREATE TABLE IF NOT EXISTS extras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                preco REAL
            );
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                contato TEXT,
                documento TEXT
            );
            CREATE TABLE IF NOT EXISTS festas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                salao_id INTEGER,
                cliente_id INTEGER,
                data TEXT,
                inicio TEXT,
                combo_id INTEGER,
                horas_extra INTEGER,
                total REAL,
                obs TEXT
            );
            CREATE TABLE IF NOT EXISTS festa_extras (
                festa_id INTEGER,
                extra_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS pagamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                festa_id INTEGER,
                valor REAL,
                data TEXT,
                tipo TEXT
            );
        """)
        self.conn.commit()

    def cria_saloes(self, nome, capacidade, acrescimo):
        if not nome.strip():
            raise ValueError("O nome do salão não pode ficar vazio!")
        if capacidade <= 0:
            raise ValueError("A capacidade deve ser maior que zero!")
        if acrescimo < 0:
            raise ValueError("O acréscimo não pode ser negativo!")

        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO saloes (nome, capacidade, acrescimo) VALUES (?, ?, ?)",
            (nome.strip(), capacidade, acrescimo)
        )
        self.conn.commit()
        print(f"Salão '{nome}' cadastrado com sucesso!")
        return cursor.lastrowid

    def _tem_dados(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM saloes")
        return cursor.fetchone()[0] > 0

    def _dados_iniciais(self):
        cursor = self.conn.cursor()
        cursor.executemany(
            "INSERT INTO saloes (id, nome, capacidade, acrescimo) VALUES (?, ?, ?, ?)",
            [
                (1, "Arco-Íris", 60, 0.0),
                (2, "Estrela", 100, 300.0),
                (3, "Confete", 150, 600.0)
            ]
        )
        cursor.executemany(
            "INSERT INTO combos (id, nome, preco, descricao) VALUES (?, ?, ?, ?)",
            [
                (1, "Básico", 1500.0, "Decoração simples, salgados e refrigerante"),
                (2, "Festa", 2500.0, "Decoração temática, buffet completo e bolo"),
                (3, "Mega", 3800.0, "Tudo do Festa + brinquedos e animador")
            ]
        )
        cursor.executemany(
            "INSERT INTO extras (id, nome, preco) VALUES (?, ?, ?)",
            [
                (1, "Salgados", 350.0),
                (2, "Bebidas", 250.0),
                (3, "Pula-pula", 400.0),
                (4, "Bolo", 300.0),
                (5, "Animador", 450.0)
            ]
        )
        cursor.executemany(
            "INSERT INTO clientes (id, nome, contato, documento) VALUES (?, ?, ?, ?)",
            [
                (1, "Juliana Prado", "(11) 98888-1111", "123.456.789-00"),
                (2, "Rafael Mendes", "(11) 97777-2222", "987.654.321-00")
            ]
        )
        self.conn.commit()

    # --- CONSULTAS (Mapeando tabelas para objetos POO) ---
    def listar_saloes(self):
        rows = self.conn.execute("SELECT * FROM saloes").fetchall()
        return [Salao(**dict(row)) for row in rows]

    def listar_combos(self):
        rows = self.conn.execute("SELECT * FROM combos").fetchall()
        return [Combo(**dict(row)) for row in rows]

    def listar_extras(self):
        rows = self.conn.execute("SELECT * FROM extras").fetchall()
        return [Extra(**dict(row)) for row in rows]

    def listar_clientes(self):
        rows = self.conn.execute("SELECT * FROM clientes").fetchall()
        return [Cliente(**dict(row)) for row in rows]

    def listar_festas(self):
        rows = self.conn.execute("SELECT * FROM festas").fetchall()
        festas = []
        for row in rows:
            festa_dict = dict(row)
            extras_rows = self.conn.execute(
                "SELECT extra_id FROM festa_extras WHERE festa_id = ?",
                (festa_dict["id"],)
            ).fetchall()
            festa_dict["extras"] = [extra["extra_id"] for extra in extras_rows]
            festas.append(Festa(**festa_dict))
        return festas

    def cliente(self, id_):
        row = self.conn.execute("SELECT * FROM clientes WHERE id = ?", (id_,)).fetchone()
        return Cliente(**dict(row)) if row else None

    def salao(self, id_):
        row = self.conn.execute("SELECT * FROM saloes WHERE id = ?", (id_,)).fetchone()
        return Salao(**dict(row)) if row else None

    def combo(self, id_):
        if not id_:
            return None
        row = self.conn.execute("SELECT * FROM combos WHERE id = ?", (id_,)).fetchone()
        return Combo(**dict(row)) if row else None

    def extra(self, id_):
        row = self.conn.execute("SELECT * FROM extras WHERE id = ?", (id_,)).fetchone()
        return Extra(**dict(row)) if row else None

    # --- REGRAS DE NEGÓCIO ---
    def cadastrar_cliente(self, nome, contato, documento):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO clientes (nome, contato, documento) VALUES (?, ?, ?)",
            (nome, contato, documento)
        )
        self.conn.commit()
        print(f"Cliente '{nome}' cadastrado com sucesso!")
        return cursor.lastrowid

    def calcular_total(self, salao_id, combo_id, extras_ids, horas_extra):
        salao = self.salao(salao_id)
        combo = self.combo(combo_id)
        total = (salao.acrescimo if salao else 0) + (horas_extra * VALOR_HORA_EXTRA)
        total += combo.preco if combo else 0
        for extra_id in extras_ids:
            extra = self.extra(extra_id)
            if extra:
                total += extra.preco
        return total

    def agendar_festa(self, salao_id, cliente_id, data, inicio, combo_id, extras_ids, horas_extra, obs):
        total = self.calcular_total(salao_id, combo_id, extras_ids, horas_extra)
        nova_festa = Festa(
            0, salao_id, cliente_id, data, inicio, combo_id,
            horas_extra, total, obs, extras_ids
        )

        for festa_existente in self.listar_festas():
            if nova_festa.conflita_com(festa_existente):
                return False, "O salão já está reservado nesse horário (conflito de agenda)!"

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO festas (salao_id, cliente_id, data, inicio, combo_id, horas_extra, total, obs)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (salao_id, cliente_id, data, inicio, combo_id, horas_extra, total, obs))
        festa_id = cursor.lastrowid

        for extra_id in extras_ids:
            cursor.execute(
                "INSERT INTO festa_extras (festa_id, extra_id) VALUES (?, ?)",
                (festa_id, extra_id)
            )

        self.conn.commit()
        return True, f"Festa agendada com sucesso! ID da festa: {festa_id} | Total: R$ {total:,.2f}"


# ==========================================
# INTERFACE DE TERMINAL (MENU)
# ==========================================

def menu():
    db = Banco()
    while True:
        print("\n==============================")
        print(" EMOJIFESTAS - SISTEMA SQL ")
        print("==============================")
        print("1. Listar Salões, Combos e Extras")
        print("2. Listar Clientes")
        print("3. Cadastrar Novo Cliente")
        print("4. Agendar Festa")
        print("5. Listar Agendamentos (Festas)")
        print("6. Cadastrar Novo Salão")
        print("0. Sair")

        opcao = input("\nEscolha uma opção: ").strip()

        if opcao == "1":
            print("\n--- SALÕES ---")
            for salao in db.listar_saloes():
                print(f"[{salao.id}] {salao.nome} - Capacidade: {salao.capacidade} pes. (Acréscimo: R$ {salao.acrescimo})")
            print("\n--- COMBOS ---")
            for combo in db.listar_combos():
                print(f"[{combo.id}] {combo.nome} - R$ {combo.preco} ({combo.descricao})")
            print("\n--- EXTRAS ---")
            for extra in db.listar_extras():
                print(f"[{extra.id}] {extra.nome} - R$ {extra.preco}")

        elif opcao == "2":
            print("\n--- CLIENTES CADASTRADOS ---")
            for cliente in db.listar_clientes():
                print(f"[{cliente.id}] {cliente.nome} | Contato: {cliente.contato} | Doc: {cliente.documento}")

        elif opcao == "3":
            print("\n--- NOVO CLIENTE ---")
            nome = input("Nome: ")
            contato = input("Contato/Telefone: ")
            documento = input("Documento (CPF): ")
            db.cadastrar_cliente(nome, contato, documento)

        elif opcao == "4":
            print("\n--- NOVO AGENDAMENTO ---")
            for salao in db.listar_saloes():
                print(f"[{salao.id}] {salao.nome}")
            salao_id = int(input("ID do Salão: "))

            for cliente in db.listar_clientes():
                print(f"[{cliente.id}] {cliente.nome}")
            cliente_id = int(input("ID do Cliente: "))

            data_evento = input("Data (AAAA-MM-DD): ")
            inicio = input("Horário de Início (HH:MM): ")

            for combo in db.listar_combos():
                print(f"[{combo.id}] {combo.nome} (R$ {combo.preco})")
            combo_id = input("ID do Combo (ou Enter para nenhum): ")
            combo_id = int(combo_id) if combo_id else None

            horas_extra = int(input("Horas extras (0 se não houver): ") or 0)
            print("Extras disponíveis:")
            for extra in db.listar_extras():
                print(f"[{extra.id}] {extra.nome} (R$ {extra.preco})")
            extras_input = input("IDs dos extras separados por vírgula (ex: 1,3) ou vazio: ")
            extras_ids = [int(x.strip()) for x in extras_input.split(",")] if extras_input else []
            obs = input("Observações: ")

            sucesso, mensagem = db.agendar_festa(
                salao_id, cliente_id, data_evento, inicio,
                combo_id, extras_ids, horas_extra, obs
            )
            print(mensagem)

        elif opcao == "5":
            print("\n--- LISTA DE FESTAS AGENDADAS ---")
            festas = db.listar_festas()
            if not festas:
                print("Nenhuma festa agendada.")
            for festa in festas:
                cliente = db.cliente(festa.cliente_id)
                salao = db.salao(festa.salao_id)
                print(
                    f"Festa #{festa.id} | Salão: {salao.nome if salao else 'N/A'} | "
                    f"Cliente: {cliente.nome if cliente else 'N/A'} | Data: {festa.data} às {festa.inicio} | "
                    f"Total: R$ {festa.total:,.2f}"
                )

        elif opcao == "6":
            print("\n--- CADASTRAR NOVO SALÃO ---")
            nome = input("Nome do salão: ")
            capacidade = int(input("Capacidade de pessoas: "))
            acrescimo = float(input("Acréscimo no valor (R$): "))
            db.cria_saloes(nome, capacidade, acrescimo)

        elif opcao == "0":
            print("Saindo do sistema... Até logo!")
            break
        else:
            print("Opção inválida, tente novamente.")

    db.conn.close()


if __name__ == "__main__":
    menu()
