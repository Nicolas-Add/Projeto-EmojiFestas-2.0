from datetime import datetime
import os
from decimal import Decimal, InvalidOperation
from flask import Flask, jsonify, request, send_from_directory
import logging
import sqlite3
from main import Banco

app = Flask(__name__, static_folder=".", static_url_path="")
app.logger.setLevel(logging.INFO)
db = Banco()


def row_dict(row):
    return dict(row) if row is not None else None


def listar_festas_com_detalhes():
    resultado = []
    for festa in db.listar_festas():
        cliente = db.cliente(festa.cliente_id)
        salao = db.salao(festa.salao_id)
        combo = db.combo(festa.combo_id)
        resultado.append({
            "id": festa.id,
            "salao_id": festa.salao_id,
            "cliente_id": festa.cliente_id,
            "cliente_nome": cliente.nome if cliente else "Cliente não encontrado",
            "salao_nome": salao.nome if salao else "Salão não encontrado",
            "titulo": f"Festa {combo.nome}" if combo else "Festa agendada",
            "data": festa.data,
            "inicio": festa.inicio,
            "combo_id": festa.combo_id,
            "combo_nome": combo.nome if combo else None,
            "horas_extra": festa.horas_extra,
            "total": festa.total,
            "obs": festa.obs,
            "extras": festa.extras
        })
    return resultado


@app.get("/")
def index():
    return send_from_directory(".", "index.html")


@app.get("/api/dashboard")
def dashboard():
    festas = listar_festas_com_detalhes()
    clientes = db.listar_clientes()
    return jsonify({
        "total_festas": len(festas),
        "total_clientes": len(clientes),
        "valor_contratado": sum(float(f["total"] or 0) for f in festas)
    })


@app.get("/api/saloes")
def saloes():
    return jsonify([{"id":s.id,"nome":s.nome,"capacidade":s.capacidade,"acrescimo":s.acrescimo} for s in db.listar_saloes()])


@app.post("/api/saloes")
def criar_salao():
    """Cadastra um salão usando a classe Banco do main.py."""
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify(error="Os dados do formulário não chegaram em JSON válido."), 400

    nome = str(dados.get("nome") or "").strip()
    try:
        capacidade = int(dados.get("capacidade"))
        acrescimo = float(dados.get("acrescimo", 0))
    except (TypeError, ValueError):
        return jsonify(error="Informe uma capacidade inteira e um acréscimo numérico válido."), 400

    if not nome:
        return jsonify(error="Informe o nome do salão."), 400
    if capacidade <= 0:
        return jsonify(error="A capacidade deve ser maior que zero."), 400
    if acrescimo < 0:
        return jsonify(error="O acréscimo não pode ser negativo."), 400

    try:
        # Prioriza o método já existente na classe Banco do main.py.
        metodo = getattr(db, "cria_saloes", None)
        if callable(metodo):
            metodo(nome, capacidade, acrescimo)
        else:
            # Compatibilidade com a mesma estrutura física da tabela saloes.
            db.conn.execute(
                "INSERT INTO saloes (nome, capacidade, acrescimo) VALUES (?, ?, ?)",
                (nome, capacidade, acrescimo)
            )
            db.conn.commit()

        registro = db.conn.execute(
            "SELECT id, nome, capacidade, acrescimo FROM saloes WHERE nome = ? ORDER BY id DESC LIMIT 1",
            (nome,)
        ).fetchone()
        if registro is None:
            raise RuntimeError("O banco não confirmou a gravação do salão.")

        return jsonify(
            message="Salão cadastrado com sucesso.",
            salao={"id": registro[0], "nome": registro[1], "capacidade": registro[2], "acrescimo": registro[3]}
        ), 201
    except sqlite3.Error as erro:
        db.conn.rollback()
        app.logger.exception("Erro SQLite ao cadastrar salão")
        return jsonify(error=f"Erro no banco de dados ao cadastrar salão: {erro}"), 500
    except Exception as erro:
        try:
            db.conn.rollback()
        except Exception:
            pass
        app.logger.exception("Erro inesperado ao cadastrar salão")
        return jsonify(error=f"Não foi possível cadastrar o salão: {type(erro).__name__}: {erro}"), 500


@app.get("/api/combos")
def combos():
    return jsonify([{"id":c.id,"nome":c.nome,"preco":c.preco,"descricao":c.descricao} for c in db.listar_combos()])


@app.get("/api/extras")
def extras():
    return jsonify([{"id":e.id,"nome":e.nome,"preco":e.preco} for e in db.listar_extras()])


@app.get("/api/clientes")
def clientes():
    return jsonify([{"id":c.id,"nome":c.nome,"contato":c.contato,"documento":c.documento} for c in db.listar_clientes()])


@app.post("/api/clientes")
def criar_cliente():
    dados = request.get_json(silent=True) or {}
    nome = str(dados.get("nome", "")).strip()
    contato = str(dados.get("contato", "")).strip()
    documento = str(dados.get("documento", "")).strip()
    if not nome or not contato or not documento:
        return jsonify(error="Preencha nome, contato e documento."), 400
    db.cadastrar_cliente(nome, contato, documento)
    return jsonify(message="Cliente cadastrado com sucesso."), 201


@app.get("/api/festas")
def festas():
    return jsonify(listar_festas_com_detalhes())


@app.post("/api/festas")
def criar_festa():
    dados = request.get_json(silent=True) or {}
    try:
        salao_id = int(dados["salao_id"])
        cliente_id = int(dados["cliente_id"])
        data_evento = str(dados["data"])
        inicio = str(dados["inicio"])
        combo_id = int(dados["combo_id"]) if dados.get("combo_id") not in (None, "") else None
        horas_extra = int(dados.get("horas_extra", 0))
        extras_ids = [int(x) for x in dados.get("extras_ids", [])]
        obs = str(dados.get("obs", ""))
        datetime.strptime(data_evento, "%Y-%m-%d")
        datetime.strptime(inicio, "%H:%M")
    except (KeyError, TypeError, ValueError):
        return jsonify(error="Confira os dados do agendamento, a data e o horário."), 400
    if not db.salao(salao_id):
        return jsonify(error="Salão não encontrado."), 404
    if not db.cliente(cliente_id):
        return jsonify(error="Cliente não encontrado."), 404
    if combo_id is not None and not db.combo(combo_id):
        return jsonify(error="Combo não encontrado."), 404
    if horas_extra < 0:
        return jsonify(error="Horas extras não podem ser negativas."), 400
    if any(not db.extra(eid) for eid in extras_ids):
        return jsonify(error="Um ou mais serviços adicionais não foram encontrados."), 404
    sucesso, mensagem = db.agendar_festa(salao_id, cliente_id, data_evento, inicio, combo_id, extras_ids, horas_extra, obs)
    if not sucesso:
        return jsonify(error=mensagem), 409
    return jsonify(message=mensagem), 201


@app.get("/api/pagamentos")
def pagamentos():
    rows = db.conn.execute("""
        SELECT p.id, p.festa_id, p.valor, p.data, p.tipo,
               c.nome AS cliente_nome, f.data AS data_festa
        FROM pagamentos p
        LEFT JOIN festas f ON f.id = p.festa_id
        LEFT JOIN clientes c ON c.id = f.cliente_id
        ORDER BY p.data DESC, p.id DESC
    """).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/pagamentos")
def criar_pagamento():
    dados = request.get_json(silent=True) or {}
    try:
        festa_id = int(dados["festa_id"])
        # O servidor também aceita ponto ou vírgula como separador decimal.
        valor_texto = str(dados["valor"]).strip().replace("R$", "").replace(" ", "")
        if "." in valor_texto and "," in valor_texto:
            if valor_texto.rfind(",") > valor_texto.rfind("."):
                valor_texto = valor_texto.replace(".", "").replace(",", ".")
            else:
                valor_texto = valor_texto.replace(",", "")
        elif "," in valor_texto:
            valor_texto = valor_texto.replace(",", ".")
        valor_decimal = Decimal(valor_texto).quantize(Decimal("0.01"))
        valor = float(valor_decimal)
        data_pagamento = str(dados["data"])
        tipo = str(dados.get("tipo", "Parcela")).strip()
        datetime.strptime(data_pagamento, "%Y-%m-%d")
        if not valor_decimal.is_finite():
            raise InvalidOperation
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return jsonify(error="Informe evento, valor válido (ex.: 150.50) e data válidos."), 400
    festa = db.conn.execute("SELECT total FROM festas WHERE id = ?", (festa_id,)).fetchone()
    if not festa:
        return jsonify(error="Festa não encontrada."), 404
    if valor <= 0:
        return jsonify(error="O valor do pagamento deve ser maior que zero."), 400
    ja_pago = db.conn.execute("SELECT COALESCE(SUM(valor),0) FROM pagamentos WHERE festa_id = ?", (festa_id,)).fetchone()[0]
    if ja_pago + valor > float(festa["total"]) + 0.001:
        return jsonify(error="O pagamento ultrapassa o valor restante da festa."), 400
    db.conn.execute("INSERT INTO pagamentos (festa_id, valor, data, tipo) VALUES (?, ?, ?, ?)",
                    (festa_id, valor, data_pagamento, tipo))
    db.conn.commit()
    return jsonify(message="Pagamento registrado com sucesso."), 201


@app.errorhandler(404)
def not_found(_):
    return jsonify(error="Endereço não encontrado."), 404


@app.errorhandler(Exception)
def tratar_erro_inesperado(erro):
    app.logger.exception("Erro não tratado na aplicação")
    return jsonify(error=f"Erro interno: {type(erro).__name__}: {erro}"), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False,
        use_reloader=False,
        threaded=False
    )
