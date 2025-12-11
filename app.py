from flask import Flask, render_template, request, send_file
import pandas as pd
import os
from io import BytesIO

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Variáveis globais (para simplificar)
estoque_df = None
pedidos_df = None
resultados = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    global estoque_df, pedidos_df

    estoque_file = request.files.get('estoque')
    pedidos_file = request.files.get('pedidos')

    if estoque_file:
        estoque_path = os.path.join(UPLOAD_FOLDER, estoque_file.filename)
        estoque_file.save(estoque_path)
        estoque_df = pd.read_excel(estoque_path)

    if pedidos_file:
        pedidos_path = os.path.join(UPLOAD_FOLDER, pedidos_file.filename)
        pedidos_file.save(pedidos_path)
        pedidos_df = pd.read_excel(pedidos_path)

    filiais = sorted(estoque_df['Filial'].unique()) if estoque_df is not None else []
    return render_template('select_filial.html', filiais=filiais)

@app.route('/processar', methods=['POST'])
def processar():
    global estoque_df, pedidos_df, resultados
    filial = request.form.get('filial')

    if estoque_df is None or pedidos_df is None:
        return "Erro: envie os arquivos primeiro."

    # Estoque da filial selecionada
    estoque_filial = estoque_df[estoque_df['Filial'] == filial]

    # Merge com pedidos
    merged = pedidos_df.merge(
        estoque_df, on='Produto', how='left', suffixes=('_pedido', '_estoque')
    )

    # Calcula disponibilidade
    merged['Disponivel'] = merged['Qtd_estoque'] - merged['Qtd_pedido']

    precisa_comprar = merged[merged['Disponivel'] < 0].copy()
    precisa_comprar['Falta'] = precisa_comprar['Disponivel'].abs()

    transferencias = estoque_df[
        (estoque_df['Filial'] != filial) & (estoque_df['Qtd_estoque'] > 0)
    ]

    resultados = {
        'estoque': estoque_filial,
        'transferencias': transferencias,
        'compras': precisa_comprar[['Produto', 'Falta']]
    }

    return render_template(
        'resultado.html',
        filial=filial,
        estoque=resultados['estoque'].to_html(classes='table table-striped', index=False),
        transferencias=resultados['transferencias'].to_html(classes='table table-striped', index=False),
        compras=resultados['compras'].to_html(classes='table table-striped', index=False)
    )

@app.route('/download/<tipo>')
def download(tipo):
    global resultados
    if tipo not in resultados:
        return "Arquivo não encontrado", 404

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        resultados[tipo].to_excel(writer, index=False, sheet_name=tipo.capitalize())

    output.seek(0)
    filename = f"{tipo}_resultados.xlsx"
    return send_file(output, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

if __name__ == '__main__':
    app.run(debug=True)
