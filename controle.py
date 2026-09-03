import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
import json
import bcrypt
import resend
import secrets
import time
import uuid
from google.oauth2.service_account import Credentials

resend.api_key = st.secrets["resend"]["api_key"]

st.set_page_config(
    page_title="Lúcido — Seu dinheiro, mais claro.",
    page_icon="✨",
    layout="wide"
)

def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #0B0F1A 0%, #111827 100%);
    }

    section[data-testid="stSidebar"] {
        background: #111827;
        border-right: 1px solid rgba(139, 92, 246, 0.18);
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }

    h1, h2, h3 {
        letter-spacing: -0.02em;
    }
    
    div[data-testid="stMetric"] {
    background: rgba(17, 24, 39, 0.72);
    border: 1px solid rgba(139, 92, 246, 0.18);
    border-radius: 18px;
    padding: 22px 24px;
    min-height: 135px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.16);
}

div[data-testid="stMetric"] label {
    font-size: 0.95rem;
    color: #AEB7C8;
}

div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-size: 2rem;
    font-weight: 700;
}

.card-financeiro {
    border-radius: 18px;
    padding: 22px 24px;
    min-height: 135px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.16);
}

.card-receitas {
    background: rgba(16, 185, 129, 0.10);
    border: 1px solid rgba(16, 185, 129, 0.28);
}

.card-titulo {
    font-size: 0.95rem;
    color: #AEB7C8;
    margin-bottom: 4px;
}

.card-subtitulo {
    font-size: 0.78rem;
    color: #10B981;
    margin-bottom: 10px;
}

.card-valor {
    font-size: 2rem;
    font-weight: 700;
    line-height: 1.1;
}
    
</style>
""", unsafe_allow_html=True)

# ==========================================
# CONEXÃO COM O GOOGLE SHEETS
# ==========================================
escopos = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
@st.cache_resource
def conectar_google():
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
        planilha_metas = arquivo_google.add_worksheet(
            title="Metas",
            rows="1000",
            cols="5"
        )
        planilha_metas.update(
            values=[["ID", "Email_Dono", "Meta", "Alvo", "Guardado"]],
            range_name="A1"
        )

    try:
        planilha_usuarios = arquivo_google.worksheet("Usuarios")
    except gspread.exceptions.WorksheetNotFound:
        planilha_usuarios = arquivo_google.add_worksheet(
            title="Usuarios",
            rows="1000",
            cols="5"
        )
        planilha_usuarios.update(
            values=[["Nome", "Email", "Senha_Hash", "Tentativas_Login", "Bloqueado_Ate"]],
            range_name="A1"
        )

    return planilha_dados, planilha_metas, planilha_usuarios


try:
    planilha_dados, planilha_metas, planilha_usuarios = conectar_google()
except Exception as e:
    st.error("⚠️ Erro ao conectar com o Google.")
    st.stop()

def carregar_dados():
    dados = planilha_dados.get_all_records()
    if dados: return pd.DataFrame(dados)
    return pd.DataFrame(columns=["Email_Dono", "Data", "Categoria", "Descrição", "Valor", "Tipo"])


def carregar_metas():
    dados_metas = planilha_metas.get_all_records()
    if dados_metas: return pd.DataFrame(dados_metas)
    return pd.DataFrame(columns=["ID", "Email_Dono", "Meta", "Alvo", "Guardado"])

def carregar_usuarios():
    dados_usuarios = planilha_usuarios.get_all_records()

    if dados_usuarios:
        return pd.DataFrame(dados_usuarios)

    return pd.DataFrame(columns=["Nome", "Email", "Senha_Hash", "Tentativas_Login", "Bloqueado_Ate"])

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
        
def enviar_codigo_recuperacao(email, codigo):
    try:
        resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": email,
            "subject": "Código de recuperação - Lúcido",
            "html": f"""
                <h2>Recuperação de senha</h2>
                <p>Seu código de recuperação é:</p>
                <h1>{codigo}</h1>
                <p>Use esse código no Lúcido para criar uma nova senha.</p>
            """
        })

        return True

    except Exception:
        return False


# ==========================================
# 1. SISTEMA DE LOGIN
# ==========================================
if "logado" not in st.session_state:
    st.session_state["logado"] = False

if not st.session_state["logado"]:
    st.title("🔒 Acesso Restrito")

    aba_login, aba_cadastro, aba_recuperar = st.tabs(["🔐 Entrar", "📝 Criar conta", "🔑 Esqueci minha senha"])

    with aba_login:
        usuario = st.text_input("E-mail do Cliente")
        senha = st.text_input("Senha", type="password")

        if st.button("Entrar"):
            usuarios = carregar_usuarios()

            usuario_encontrado = usuarios[
                usuarios["Email"].astype(str).str.lower() == usuario.strip().lower()
            ]

            if not usuario_encontrado.empty:
                registro_usuario = usuario_encontrado.iloc[0]
                senha_hash = str(registro_usuario["Senha_Hash"])

                tentativas_valor = registro_usuario.get("Tentativas_Login", 0)

                try:
                    tentativas_login = int(float(tentativas_valor or 0))
                except (ValueError, TypeError):
                    tentativas_login = 0

                bloqueado_ate_valor = registro_usuario.get("Bloqueado_Ate", "")

                try:
                    bloqueado_ate = float(bloqueado_ate_valor) if bloqueado_ate_valor not in ("", None) else 0
                except (ValueError, TypeError):
                    bloqueado_ate = 0

                linha_usuario_planilha = usuario_encontrado.index[0] + 2
                
                if bloqueado_ate > 0 and bloqueado_ate <= time.time():
                    tentativas_login = 0
                    bloqueado_ate = 0
                    planilha_usuarios.update(
                        f"D{linha_usuario_planilha}:E{linha_usuario_planilha}",
                        [[0, ""]]
                )

                if bloqueado_ate > time.time():
                    minutos_restantes = max(1, int((bloqueado_ate - time.time()) / 60) + 1)
                    st.error(f"Muitas tentativas incorretas. Tente novamente em aproximadamente {minutos_restantes} minuto(s).")
                    
                elif verificar_senha(senha, senha_hash):

                    planilha_usuarios.update(
                        f"D{linha_usuario_planilha}:E{linha_usuario_planilha}",
                        [[0, ""]]
                    )
                
                    st.session_state["logado"] = True
                    st.session_state["usuario_atual"] = usuario.strip().lower()
                    st.session_state["nome_usuario"] = str(registro_usuario["Nome"]).strip()
                    st.rerun()
                
                else:
                    tentativas_login += 1

                    if tentativas_login >= 3:
                        bloqueado_ate = time.time() + 300
                        planilha_usuarios.update(
                            f"D{linha_usuario_planilha}:E{linha_usuario_planilha}",
                            [[tentativas_login, bloqueado_ate]]
                        )
                    else:
                         planilha_usuarios.update_cell(
                             linha_usuario_planilha,
                             4,
                             tentativas_login
                         )
                    
                    if tentativas_login >= 3:
                        st.error("Muitas tentativas incorretas. Sua conta foi bloqueada por 5 minutos.")
                    else:
                        tentativas_restantes = 3 - tentativas_login
                        st.error(f"E-mail ou senha incorretos! Você ainda tem {tentativas_restantes} tentativa(s).")
                        
            else:
                st.error("E-mail ou senha incorretos!")

    with aba_cadastro:
        st.subheader("Criar uma conta")

        nome_cadastro = st.text_input(
            "Seu nome",
            key="nome_cadastro"
        )

        email_cadastro = st.text_input(
            "Seu e-mail",
            key="email_cadastro"
        )

        senha_cadastro = st.text_input(
            "Crie uma senha",
            type="password",
            key="senha_cadastro"
        )

        confirmar_senha = st.text_input(
            "Confirme sua senha",
            type="password",
            key="confirmar_senha"
        )

        if st.button("Criar minha conta"):
            if nome_cadastro.strip() == "" or email_cadastro.strip() == "" or senha_cadastro == "" or confirmar_senha == "":
                st.warning("Preencha todos os campos.")
                
            elif email_cadastro.count("@") != 1 or "." not in email_cadastro.split("@")[-1] or email_cadastro.startswith("@") or email_cadastro.endswith("@"):
                st.warning("Digite um e-mail válido.")   
                
            elif len(senha_cadastro) < 10:
                st.warning("A senha precisa ter pelo menos 10 caracteres.")
                
            elif senha_cadastro != confirmar_senha:
                st.warning("As senhas não coincidem.")
                
            else:
                usuarios = carregar_usuarios()

                email_normalizado = email_cadastro.strip().lower()

                if (
                    not usuarios.empty
                    and email_normalizado in usuarios["Email"].astype(str).str.lower().values
                ):
                    st.warning("Já existe uma conta com esse e-mail.")
                else:
                    senha_hash = criar_hash_senha(senha_cadastro)

                    planilha_usuarios.append_row([
                        nome_cadastro.strip(),
                        email_normalizado,
                        senha_hash,
                        0,
                        ""
                    ])

                    st.success("Conta criada com sucesso!")

    with aba_recuperar:
        st.subheader("🔑 Recuperar senha")
        email_recuperacao = st.text_input("Digite seu e-mail", key="email_recuperacao")

        if st.button("Enviar código de recuperação"):
            ultimo_envio = st.session_state.get("ultimo_envio_codigo", 0)
            segundos_desde_envio = time.time() - ultimo_envio
            
            if segundos_desde_envio < 60:
                segundos_restantes = int(60 - segundos_desde_envio)
                st.warning(f"Aguarde {segundos_restantes} segundos antes de solicitar outro código.")
                st.stop()
            
            email_digitado = email_recuperacao.strip().lower()
            usuarios = carregar_usuarios()

            usuario_encontrado = usuarios[
                usuarios["Email"].astype(str).str.lower() == email_digitado
            ]

            if usuario_encontrado.empty:
                st.success("Se este e-mail estiver cadastrado, você receberá um código de recuperação.")
            else:
                codigo = str(secrets.randbelow(900000) + 100000)

                if enviar_codigo_recuperacao(email_digitado, codigo):
                    st.session_state["codigo_recuperacao"] = codigo
                    st.session_state["email_recuperacao_confirmado"] = email_digitado
                    st.session_state["tempo_codigo_recuperacao"] = time.time()
                    st.session_state["tentativas_codigo"] = 0
                    st.session_state["ultimo_envio_codigo"] = time.time()
                    st.success("Se este e-mail estiver cadastrado, você receberá um código de recuperação.")
                else:
                    st.success("Se este e-mail estiver cadastrado, você receberá um código de recuperação.")

    if "codigo_recuperacao" in st.session_state:
           st.divider()
           st.write("Digite o código recebido no seu e-mail e escolha uma nova senha.")

           codigo_digitado = st.text_input(
               "Código de recuperação",
               key="codigo_digitado"
           )

           nova_senha = st.text_input(
               "Nova senha",
               type="password",
               key="nova_senha"
           )

           confirmar_nova_senha = st.text_input(
               "Confirme a nova senha",
               type="password",
               key="confirmar_nova_senha"
           )

           if st.button("Alterar senha"):
               codigo_expirado = (
                   time.time() - st.session_state["tempo_codigo_recuperacao"] > 600
               )

               if codigo_expirado:
                   st.error("Este código expirou. Solicite um novo código.")
                   
               elif not secrets.compare_digest(
                   codigo_digitado.strip(),
                   st.session_state["codigo_recuperacao"]
               ):
                           st.session_state["tentativas_codigo"] += 1

                           tentativas_restantes = 5 - st.session_state["tentativas_codigo"]

                           if st.session_state["tentativas_codigo"] >= 5:
                               del st.session_state["codigo_recuperacao"]
                               del st.session_state["email_recuperacao_confirmado"]
                               del st.session_state["tempo_codigo_recuperacao"]
                               del st.session_state["tentativas_codigo"]
                               

                               st.error(
                                   "Você excedeu o limite de tentativas. Solicite um novo código."
                               )
                           else:
                               st.error(
                                   f"Código inválido. Você ainda tem {tentativas_restantes} tentativa(s)."
                               )

               elif len(nova_senha) < 10:
                   st.error("A nova senha deve ter pelo menos 10 caracteres.")

               elif nova_senha != confirmar_nova_senha:
                   st.error("As senhas não coincidem.")

               else:
                   email_confirmado = st.session_state["email_recuperacao_confirmado"]
                   usuarios = carregar_usuarios()

                   usuario_encontrado = usuarios[
                       usuarios["Email"].astype(str).str.lower() == email_confirmado
                   ]

                   if usuario_encontrado.empty:
                       st.error("Não foi possível concluir a alteração de senha. Solicite um novo código.")

                   else:
                       indice_usuario = usuario_encontrado.index[0]
                       linha_planilha = indice_usuario + 2

                       nova_senha_hash = criar_hash_senha(nova_senha)

                       planilha_usuarios.update(
                           f"C{linha_planilha}:E{linha_planilha}",
                           [[nova_senha_hash, 0, ""]]
                       )

                       del st.session_state["codigo_recuperacao"]
                       del st.session_state["email_recuperacao_confirmado"]
                       del st.session_state["tempo_codigo_recuperacao"]
                       del st.session_state["tentativas_codigo"]

                       st.success(
                           "Senha alterada com sucesso! Agora você já pode entrar."
                       )
    
# ==========================================
# 2. O APLICATIVO (O Cofre)
# ==========================================
else:
    usuario_logado = st.session_state["usuario_atual"]

    st.sidebar.markdown("## ✨ Lúcido")
    st.sidebar.caption("Seu dinheiro, mais claro.")
    
    nome_usuario = st.session_state.get("nome_usuario", usuario_logado)
    st.sidebar.markdown(f"**Olá, {nome_usuario}! 👋**")
    st.sidebar.caption("Que bom ter você por aqui.")
    
    if st.sidebar.button("Sair da Conta"):
        st.session_state["logado"] = False
        st.session_state.pop("usuario_atual", None)
        st.rerun()
        
    st.sidebar.write("---")

    st.sidebar.title("➕ Novo Registro")
    # 1. Ajuste da data para o formato BR no menu lateral
    data = st.sidebar.date_input("Data da movimentação", format="DD/MM/YYYY")
    descricao = st.sidebar.text_input("Descrição (Ex: Padaria)")
    valor = st.sidebar.number_input("Valor (R$)", min_value=0.0, format="%.2f")
    tipo = st.sidebar.selectbox("Tipo", ["Entrada (Ganho)", "Saída (Custo/Gasto)"])

    if tipo == "Saída (Custo/Gasto)":
        categoria = st.sidebar.selectbox(
            "Categoria",
            ["Alimentação", "Moradia", "Transporte", "Saúde", "Educação", "Lazer", "Reserva/Investimento", "Outros"]
        )
    else:
        categoria = st.sidebar.selectbox(
            "Categoria",
            ["Salário", "Renda Extra", "Rendimento", "Outros"]
        )

    if st.sidebar.button("Salvar Registro"):
        if descricao.strip() != "" and valor > 0:
            novo_id = str(uuid.uuid4())
            
            planilha_dados.append_row([
                novo_id,
                usuario_logado,
                str(data),
                categoria,
                descricao.strip(),
                float(valor),
                tipo
            ])

            st.sidebar.success("Salvo direto na nuvem! ☁️")
            st.rerun()
        else:
            st.sidebar.warning("Preencha a descrição e o valor.")


    df_completo = carregar_dados()
    
    if not df_completo.empty and "Email_Dono" in df_completo.columns:
        dados = df_completo[df_completo["Email_Dono"] == usuario_logado].copy()
    else:
        dados = pd.DataFrame()
        
    aba_dashboard, aba_metas, aba_saude, aba_editar = st.tabs(["⌂ Visão Geral", "◎ Metas", "♡ Saúde Financeira", "↔ Movimentações"])

    with aba_dashboard:
        st.subheader("Visão Geral")
        st.caption("Aqui está o resumo das suas finanças.")
        
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
            with col1:
                st.markdown(
                    f"""
                    <div class="card-financeiro card-receitas">
                        <div class="card-titulo">Receitas</div>
                        <div class="card-subtitulo">Entradas</div>
                        <div class="card-valor">{formatar_moeda(entradas)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
            col2.metric("Despesas", formatar_moeda(saidas))
            col3.metric("Saldo Atual", formatar_moeda(saldo))
            
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
            if nome_meta.strip() != "" and valor_meta > 0:

                novo_id_meta = str(uuid.uuid4())
                   
                planilha_metas.append_row([
                    novo_id_meta,
                    usuario_logado,
                    nome_meta.strip(),
                    float(valor_meta),
                    0.0
                ])
                
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
                progresso = float(row["Guardado"]) / float(row["Alvo"]) if float(row["Alvo"]) > 0 else 0.0
                if progresso > 1.0: progresso = 1.0 
                
                st.write(f"**{row['Meta']}** (Você tem R$ {float(row['Guardado']):.2f} de R$ {float(row['Alvo']):.2f})")
                st.progress(progresso)
            
            st.write("---")
            st.write("💰 **Adicionar dinheiro à caixinha:**")
            col_add1, col_add2 = st.columns(2)
            meta_id_escolhida = col_add1.selectbox(
                "Escolha o objetivo",
                df_minhas_metas["ID"].tolist(),
                format_func=lambda id_meta: df_minhas_metas.loc[
                    df_minhas_metas["ID"] == id_meta, "Meta"
                ].iloc[0]
            )
            valor_guardar = col_add2.number_input("Valor a adicionar (R$)", min_value=0.0, format="%.2f", key="add_dinheiro")
            
            if st.button("Guardar Dinheiro"):
               linha_meta = df_minhas_metas[
                   df_minhas_metas["ID"] == meta_id_escolhida
               ].iloc[0]

               if linha_meta["Email_Dono"] != usuario_logado:
                   st.error("Você não tem permissão para alterar esta meta.")
               else:
                   celula_id = planilha_metas.find(
                str(meta_id_escolhida).strip().removesuffix(".0"),
                in_column=1
            )
                   numero_linha = celula_id.row
                   guardado_atual = float(linha_meta["Guardado"])
                   novo_guardado = guardado_atual + float(valor_guardar)

                   planilha_metas.update_cell(
                       numero_linha,
                       5,
                       novo_guardado
                   )
                   
                   st.success(f"R$ {valor_guardar} adicionados!")
                   st.rerun()
                   
            if st.button("🗑️ Excluir Meta"):
                celula_id_excluir = planilha_metas.find(
                    str(meta_id_escolhida).strip().removesuffix(".0"),
                    in_column=1
                )
                
                numero_linha_excluir = celula_id_excluir.row
                email_dono_meta = planilha_metas.cell(numero_linha_excluir, 2).value

                if email_dono_meta != usuario_logado:
                    st.error("Você não tem permissão para excluir esta meta.")
                else:
                    planilha_metas.delete_rows(numero_linha_excluir)
                    st.success("Meta excluída com sucesso!")
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
            dados_para_editar = dados.drop(
    columns=[col for col in ["Mes_Ano", "Email_Dono"] if col in dados.columns]
)
            
            # 3. Ajuste da data para o formato BR na tabela de edição
            dados_editados = st.data_editor(
                dados_para_editar, 
                use_container_width=True, 
                num_rows="dynamic",
                column_config={
                    "ID": st.column_config.TextColumn("ID", disabled=True),
                    "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")
                }
            )
            
            if st.button("Salvar Alterações"):
                ids_antes = set(dados_para_editar["ID"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True))
                ids_depois = set(dados_editados["ID"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True))
                ids_excluidos = ids_antes - ids_depois
                
                for _, registro in dados_editados.iterrows():
                    id_registro = str(registro["ID"]).strip().removesuffix(".0")
                    celula_id = planilha_dados.find(str(id_registro), in_column=1)
                    numero_linha = celula_id.row
                    email_dono_linha = planilha_dados.cell(numero_linha, 2).value

                    if email_dono_linha != usuario_logado:
                        continue
                    
                    planilha_dados.update(
                        f"C{numero_linha}:G{numero_linha}",
                        [[
                            str(registro["Data"]),
                            registro["Categoria"],
                            registro["Descrição"],
                            float(registro["Valor"]),
                            registro["Tipo"]
                        ]]
                    )
                
                for id_excluido in ids_excluidos:
                    celula_id = planilha_dados.find(str(id_excluido).strip().removesuffix(".0"), in_column=1)
                    email_dono_linha = planilha_dados.cell(celula_id.row, 2).value
                    if email_dono_linha != usuario_logado:
                        continue
                    planilha_dados.delete_rows(celula_id.row) 
               
                st.success("Alterações salvas na nuvem!")
                st.rerun()
        else:
            st.info("Você ainda não tem registros para editar.")
