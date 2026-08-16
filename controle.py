import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
import json
import bcrypt
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Lúcido | Finanças", page_icon="💸", layout="wide")

# ==========================================
# CONEXÃO COM O GOOGLE SHEETS
# ==========================================
escopos = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

try:
    credenciais = Credentials.from_service_account_info(
    json.loads(st.secrets["gspread"]["json_key"]),
    scopes=escopos
    )
    cliente = gspread.authorize(credenciais)
    arquivo_google = cliente.open("Banco_App_Financeiro")
    
    
    planilha_dados = arquivo_google.sheet1
    
    try:
        planilha_metas = arquivo_google.worksheet("Metas")
    except gspread.exceptions.WorksheetNotFound:
        planilha_metas = arquivo_google.add_worksheet(title="Metas", rows="1000", cols="4")
        planilha_metas.update(values=[["Email_Dono", "Meta", "Alvo", "Guardado"]], range_name='A1')

    try:
        planilha_usuarios = arquivo_google.worksheet("Usuarios")
    except gspread.exceptions.WorksheetNotFound:
        planilha_usuarios = arquivo_google.add_worksheet(
            title="Usuarios",
            rows="1000",
            cols="3"
        )
        planilha_usuarios.update(
            values=[["Nome", "Email", "Senha_Hash"]],
            range_name="A1"
        )

except Exception as e:
    st.error("⚠️ Erro ao conectar com o Google. Verifique o arquivo credenciais.json.")
    st.stop()

def carregar_dados():
    dados = planilha_dados.get_all_records()
    if dados: return pd.DataFrame(dados)
    return pd.DataFrame(columns=["Email_Dono", "Data", "Categoria", "Descrição", "Valor", "Tipo"])

def salvar_tabela(df):
    planilha_dados.clear()
    df_salvar = df.copy()
    df_salvar["Data"] = df_salvar["Data"].astype(str)
    lista_dados = [df_salvar.columns.values.tolist()] + df_salvar.values.tolist()
    planilha_dados.update(values=lista_dados, range_name='A1')

def carregar_metas():
    dados_metas = planilha_metas.get_all_records()
    if dados_metas: return pd.DataFrame(dados_metas)
    return pd.DataFrame(columns=["Email_Dono", "Meta", "Alvo", "Guardado"])

def carregar_usuarios():
    dados_usuarios = planilha_usuarios.get_all_records()

    if dados_usuarios:
        return pd.DataFrame(dados_usuarios)

    return pd.DataFrame(columns=["Nome", "Email", "Senha_Hash"])

def criar_hash_senha(senha):
    senha_bytes = senha.encode("utf-8")
    hash_bytes = bcrypt.hashpw(senha_bytes, bcrypt.gensalt())

    return hash_bytes.decode("utf-8")

def verificar_senha(senha_digitada, senha_hash):
    try:
        return bcrypt.checkpw(
            senha_digitada.encode("utf-8"),
            senha_hash.encode("utf-8")
        )
    except:
        return False

def salvar_metas_google(df):
    planilha_metas.clear()
    lista_dados = [df.columns.values.tolist()] + df.values.tolist()
    planilha_metas.update(values=lista_dados, range_name='A1')

# ==========================================
# 1. SISTEMA DE LOGIN
# ==========================================
if "logado" not in st.session_state:
    st.session_state["logado"] = False

if not st.session_state["logado"]:
    st.title("🔒 Acesso Restrito")
    usuario = st.text_input("E-mail do Cliente")
    senha = st.text_input("Senha", type="password")
    
   if st.button("Entrar"):
    usuarios = carregar_usuarios()

    usuario_encontrado = usuarios[
        usuarios["Email"].astype(str).str.lower() == usuario.strip().lower()
    ]

 if not usuario_encontrado.empty:
        senha_hash = str(usuario_encontrado.iloc[0]["Senha_Hash"])

        if verificar_senha(senha, senha_hash):
            st.session_state["logado"] = True
            st.session_state["usuario_atual"] = usuario.strip().lower()
            st.rerun()
        else:
            st.error("E-mail ou senha incorretos!")
    else:
        st.error("E-mail ou senha incorretos!")

# ==========================================
# 2. O APLICATIVO (O Cofre)
# ==========================================
else:
    usuario_logado = st.session_state["usuario_atual"]
    
    st.sidebar.write(f"👤 Bem-vindo(a), **{usuario_logado}**!")
    if st.sidebar.button("Sair da Conta"):
        st.session_state["logado"] = False
        st.rerun()
        
    st.sidebar.write("---")

    st.sidebar.title("➕ Novo Registro")
    # 1. Ajuste da data para o formato BR no menu lateral
    data = st.sidebar.date_input("Data da movimentação", format="DD/MM/YYYY")
    descricao = st.sidebar.text_input("Descrição (Ex: Padaria)")
    valor = st.sidebar.number_input("Valor (R$)", min_value=0.0, format="%.2f")
    tipo = st.sidebar.selectbox("Tipo", ["Entrada (Ganho)", "Saída (Custo/Gasto)"])

    if tipo == "Saída (Custo/Gasto)":
        categoria = st.sidebar.selectbox("Categoria", ["Alimentação", "Moradia", "Transporte", "Saúde", "Educação", "Lazer", "Reserva/Investimento", "Outros"])
    else:
        categoria = st.sidebar.selectbox("Categoria", ["Salário", "Renda Extra", "Rendimento", "Outros"])

    if st.sidebar.button("Salvar Registro"):
        if descricao != "" and valor > 0:
            novo_registro = pd.DataFrame({
                "Email_Dono": [usuario_logado], "Data": [str(data)], 
                "Categoria": [categoria], "Descrição": [descricao], 
                "Valor": [float(valor)], "Tipo": [tipo]
            })
            df_completo = carregar_dados()
            df_atualizado = pd.concat([df_completo, novo_registro], ignore_index=True)
            salvar_tabela(df_atualizado)
            st.sidebar.success("Salvo direto na nuvem! ☁️")
            st.rerun()
        else:
            st.sidebar.warning("Preencha a descrição e o valor.")

    st.title("💸 Lúcido | Finanças")

    df_completo = carregar_dados()
    
    if not df_completo.empty and "Email_Dono" in df_completo.columns:
        dados = df_completo[df_completo["Email_Dono"] == usuario_logado].copy()
    else:
        dados = pd.DataFrame()
        
    aba_dashboard, aba_metas, aba_saude, aba_editar = st.tabs(["📊 Dashboard", "🎯 Metas de Economia", "🩺 Saúde Financeira", "⚙️ Editar Registros"])

    with aba_dashboard:
        if not dados.empty:
            # Correção do erro de formatação misturada (devidamente alinhado!)
            dados["Data"] = pd.to_datetime(dados["Data"], format='mixed', errors='coerce')
            dados["Mes_Ano"] = dados["Data"].dt.strftime('%m/%Y')
            
            st.sidebar.write("---")
            st.sidebar.subheader("📅 Filtro de Mês")
            meses_disponiveis = dados["Mes_Ano"].unique().tolist()
            mes_selecionado = st.sidebar.selectbox("Analisar o mês de:", ["Todos os meses"] + meses_disponiveis)
            
            if mes_selecionado != "Todos os meses":
                dados_visuais = dados[dados["Mes_Ano"] == mes_selecionado]
            else:
                dados_visuais = dados.copy()

            entradas = dados_visuais[dados_visuais["Tipo"] == "Entrada (Ganho)"]["Valor"].sum()
            saidas = dados_visuais[dados_visuais["Tipo"] == "Saída (Custo/Gasto)"]["Valor"].sum()
            saldo = entradas - saidas
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Receitas", f"R$ {entradas:.2f}")
            col2.metric("Despesas", f"R$ {saidas:.2f}")
            col3.metric("Saldo Atual", f"R$ {saldo:.2f}")
            
            st.write("---")
            saidas_df = dados_visuais[dados_visuais["Tipo"] == "Saída (Custo/Gasto)"]
            if not saidas_df.empty:
                grafico1, grafico2 = st.columns(2)
                
                with grafico1:
                    fig_barras = px.bar(
                        saidas_df, x="Data", y="Valor", color="Categoria", text="Descrição", 
                        hover_data=["Descrição"], title="Gastos detalhados por Dia"
                    )
                    fig_barras.update_traces(textposition='inside', width=0.3)
                    fig_barras.update_layout(xaxis_type='category')
                    st.plotly_chart(fig_barras, use_container_width=True)
                    
                with grafico2:
                    fig_pizza = px.pie(
                        saidas_df, values="Valor", names="Categoria", hole=0.4, title="Total gasto por Categoria"
                    )
                    st.plotly_chart(fig_pizza, use_container_width=True)

            st.write("📋 **Histórico do Mês**")
            # 2. Ajuste da data para o formato BR na tabela do histórico
            tabela_tela = dados_visuais.drop(columns=["Mes_Ano", "Email_Dono"]).copy()
            tabela_tela["Data"] = tabela_tela["Data"].dt.strftime('%d/%m/%Y')
            st.dataframe(tabela_tela, use_container_width=True)
        else:
            st.info("Você ainda não tem registros financeiros. Adicione sua primeira entrada ou saída no menu lateral!")

    with aba_metas:
        st.subheader("🎯 Caixinhas de Objetivos")
        col_meta1, col_meta2 = st.columns(2)
        nome_meta = col_meta1.text_input("Qual o seu objetivo?")
        valor_meta = col_meta2.number_input("Valor Necessário (R$)", min_value=0.0, format="%.2f")
        
        if st.button("Criar Nova Meta"):
            if nome_meta != "" and valor_meta > 0:
                nova_meta = pd.DataFrame({"Email_Dono": [usuario_logado], "Meta": [nome_meta], "Alvo": [valor_meta], "Guardado": [0.0]})
                
                df_metas_completo = carregar_metas()
                df_metas_atualizado = pd.concat([df_metas_completo, nova_meta], ignore_index=True)
                salvar_metas_google(df_metas_atualizado)
                
                st.success("Objetivo criado com sucesso na nuvem!")
                st.rerun()
        
        st.write("---")
        df_metas_completo = carregar_metas()
        
        if not df_metas_completo.empty and "Email_Dono" in df_metas_completo.columns:
            df_minhas_metas = df_metas_completo[df_metas_completo["Email_Dono"] == usuario_logado].copy()
        else:
            df_minhas_metas = pd.DataFrame()
            
        if not df_minhas_metas.empty:
            for index, row in df_minhas_metas.iterrows():
                progresso = float(row["Guardado"]) / float(row["Alvo"])
                if progresso > 1.0: progresso = 1.0 
                
                st.write(f"**{row['Meta']}** (Você tem R$ {float(row['Guardado']):.2f} de R$ {float(row['Alvo']):.2f})")
                st.progress(progresso)
            
            st.write("---")
            st.write("💰 **Adicionar dinheiro à caixinha:**")
            col_add1, col_add2 = st.columns(2)
            meta_escolhida = col_add1.selectbox("Escolha o objetivo", df_minhas_metas["Meta"].tolist())
            valor_guardar = col_add2.number_input("Valor a adicionar (R$)", min_value=0.0, format="%.2f", key="add_dinheiro")
            
            if st.button("Guardar Dinheiro"):
                mascara_dono = df_metas_completo["Email_Dono"] == usuario_logado
                mascara_meta = df_metas_completo["Meta"] == meta_escolhida
                
                df_metas_completo.loc[mascara_dono & mascara_meta, "Guardado"] += float(valor_guardar)
                salvar_metas_google(df_metas_completo)
                
                st.success(f"R$ {valor_guardar} adicionados!")
                st.rerun()
        else:
            st.info("Você ainda não tem objetivos cadastrados. Crie sua primeira meta logo acima!")

    with aba_saude:
        st.subheader("🩺 Análise Inteligente: A Regra 50/30/20")
        if not dados.empty:
            entradas = dados[dados["Tipo"] == "Entrada (Ganho)"]["Valor"].sum()
            if entradas > 0:
                saidas_totais = dados[dados["Tipo"] == "Saída (Custo/Gasto)"]
                necessidades = saidas_totais[saidas_totais["Categoria"].isin(["Alimentação", "Moradia", "Transporte", "Saúde", "Educação"])]["Valor"].sum()
                desejos = saidas_totais[saidas_totais["Categoria"].isin(["Lazer", "Outros"])]["Valor"].sum()
                futuro = saidas_totais[saidas_totais["Categoria"] == "Reserva/Investimento"]["Valor"].sum()
                
                pct_n = (necessidades / entradas) * 100
                pct_d = (desejos / entradas) * 100
                pct_f = (futuro / entradas) * 100
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Necessidades (50%)", f"{pct_n:.1f}%", f"R$ {necessidades:.2f}", delta_color="off")
                c2.metric("Desejos (30%)", f"{pct_d:.1f}%", f"R$ {desejos:.2f}", delta_color="off")
                c3.metric("Futuro (20%)", f"{pct_f:.1f}%", f"R$ {futuro:.2f}", delta_color="off")
            else:
                st.info("Cadastre entradas (renda) primeiro para gerar a análise.")
        else:
            st.info("Cadastre entradas (renda) primeiro para gerar a análise.")

    with aba_editar:
        st.subheader("⚙️ Gerenciar Meus Registros")
        if not dados.empty:
            dados_para_editar = dados.drop(columns=["Mes_Ano"]) if "Mes_Ano" in dados.columns else dados
            
            # 3. Ajuste da data para o formato BR na tabela de edição
            dados_editados = st.data_editor(
                dados_para_editar, 
                use_container_width=True, 
                num_rows="dynamic",
                column_config={
                    "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")
                }
            )
            
            if st.button("Salvar Alterações"):
                df_sem_usuario = df_completo[df_completo["Email_Dono"] != usuario_logado]
                df_atualizado = pd.concat([df_sem_usuario, dados_editados], ignore_index=True)
                salvar_tabela(df_atualizado)
                st.success("Alterações salvas na nuvem!")
                st.rerun()
        else:
            st.info("Você ainda não tem registros para editar.")
