# app.py
# -*- coding: utf-8 -*-
import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import re
import zipfile
import os
import io

# ===============================================
# Função de extração das informações do PDF
# ===============================================
def extrair_informacoes(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        texto_completo = ""
        for page in doc:
            texto_completo += page.get_text("text")
        doc.close()

        # --- LIMPEZA DE CABEÇALHOS E RUÍDOS ---
        padroes_para_remover = [
            re.compile(r'^\s*https://www.reclameaqui.com.br/.*$'),
            re.compile(r'^\s*\d+/\d+\s*$'),
            re.compile(r'^\s*\d{2}/\d{2}/\d{4},\s*\d{2}:\d{2}\s*$'),
            re.compile(r'^\s*Reclame Aqui - Pesquise antes de comprar\. Reclame\. Resolva\s*$'),
            re.compile(r'^\s*Gere relatórios personalizados.*$'),
            re.compile(r'^\s*Responder\s*$'),
            re.compile(r'^\s*Sem avaliação\s*$'),
            re.compile(r'^\s*Não respondida\s*$')
        ]

        linhas_originais = texto_completo.split('\n')
        linhas_limpas = []
        for linha in linhas_originais:
            if not any(pattern.match(linha.strip()) for pattern in padroes_para_remover):
                linhas_limpas.append(linha)

        texto_limpo = "\n".join(linhas_limpas)

        # --- REGEX ---
        id_regex = re.compile(r'ID:\s*(\d{9})')
        data_regex = re.compile(r'(\d{2}/\d{2}/\d{2}\s*-\s*\d{2}:\d{2})')
        via_regex = re.compile(r'(Via\s*(?:site|mobile|app))')
        local_regex = re.compile(r'([A-Za-z\u00C0-\u017F\s\']+,\s*[A-Z]{2})')

        reclamacoes_texto = re.split(r'\n(?=ID:)', texto_limpo)
        dados_extraidos = []

        for bloco_str in reclamacoes_texto:
            if not id_regex.search(bloco_str):
                continue

            id_match = id_regex.search(bloco_str)
            data_match = data_regex.search(bloco_str)
            via_match = via_regex.search(bloco_str)
            local_match = local_regex.search(bloco_str)

            id_val = id_match.group(1) if id_match else None
            data_val = data_match.group(1) if data_match else None
            via_val = via_match.group(1) if via_match else None
            local_val = local_match.group(1) if local_match else None

            nome_val = None
            descricao_val = ""

            linhas_bloco = [l.strip() for l in bloco_str.strip().split('\n') if l.strip()]

            if data_val:
                try:
                    indice_data = next(i for i, linha in enumerate(linhas_bloco) if data_val in linha)
                    if indice_data > 0:
                        nome_val = linhas_bloco[indice_data - 1]
                        linha_inicial_desc = 1 if id_regex.match(linhas_bloco[0]) else 0
                        descricao_linhas = linhas_bloco[linha_inicial_desc:indice_data - 1]
                        descricao_val = " ".join(descricao_linhas).strip()
                except StopIteration:
                    pass

            dados_extraidos.append({
                'ID': id_val,
                'Arquivo': os.path.basename(pdf_path),
                'Nome': nome_val,
                'DataHora': data_val,
                'Via': via_val,
                'Local': local_val,
                'Descricao': descricao_val
            })

        return dados_extraidos

    except Exception as e:
        st.error(f"Erro ao processar o arquivo {pdf_path}: {e}")
        return []


# ===============================================
# Streamlit App
# ===============================================
st.set_page_config(page_title="Extração Reclame Aqui", layout="wide")
st.title("📑 Extração de Informações de PDFs")

st.write("Faça upload de um arquivo **ZIP** contendo PDFs exportados do Reclame Aqui.")

uploaded_zip = st.file_uploader("Upload do arquivo ZIP", type=["zip"])

if uploaded_zip is not None:
    extract_folder = "pdfs_extraidos"
    os.makedirs(extract_folder, exist_ok=True)

    with zipfile.ZipFile(uploaded_zip, "r") as zip_ref:
        zip_ref.extractall(extract_folder)

    pdf_files = [os.path.join(extract_folder, f) for f in os.listdir(extract_folder) if f.lower().endswith(".pdf")]
    st.success(f"✅ Total de PDFs encontrados: {len(pdf_files)}")

    dados_totais = []
    for pdf in pdf_files:
        info = extrair_informacoes(pdf)
        dados_totais.extend(info)

    if dados_totais:
        df = pd.DataFrame(dados_totais)
        st.dataframe(df)

        # Exportar para Excel
        output = io.BytesIO()
        df.to_excel(output, index=False, engine="openpyxl")
        st.download_button(
            label="📥 Baixar Excel",
            data=output.getvalue(),
            file_name="extracao_reclame_aqui.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("⚠️ Nenhuma informação extraída dos PDFs.")
