import io, re, zipfile, unicodedata
from datetime import datetime
from urllib.parse import urljoin
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
from bs4 import BeautifulSoup
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Urna a Urna 2022 × 2026", page_icon="🗳️", layout="wide")
TSE="https://dadosabertos.tse.jus.br"
DATASET={2022:f"{TSE}/dataset/resultados-2022-boletim-de-urna",2026:f"{TSE}/dataset/resultados-2026-boletim-de-urna"}
LIVE_BASE="https://resultados.tse.jus.br/oficial/ele2026/6258/dados/br/"
LIVE_STATUS_URL=LIVE_BASE+"br-e006258-ab.json"
LIVE_PRESIDENT_URL=LIVE_BASE+"br-c0001-e006258-u.json"
UF_NAMES={"AC":"Acre","AL":"Alagoas","AP":"Amapá","AM":"Amazonas","BA":"Bahia","CE":"Ceará","DF":"Distrito Federal","ES":"Espírito Santo","GO":"Goiás","MA":"Maranhão","MG":"Minas Gerais","MS":"Mato Grosso do Sul","MT":"Mato Grosso","PA":"Pará","PB":"Paraíba","PE":"Pernambuco","PI":"Piauí","PR":"Paraná","RJ":"Rio de Janeiro","RN":"Rio Grande do Norte","RO":"Rondônia","RR":"Roraima","RS":"Rio Grande do Sul","SC":"Santa Catarina","SE":"Sergipe","SP":"São Paulo","TO":"Tocantins"}
RED="#dc2626"; BLUE="#2563eb"; NEUTRAL="#64748b"
def norm(x):
    return unicodedata.normalize("NFKD",str(x)).encode("ascii","ignore").decode().upper().strip()
def candidate_color(name):
    n=norm(name)
    if "LULA" in n or "LUIZ INACIO" in n: return RED
    if "BOLSONARO" in n: return BLUE
    return NEUTRAL
st.markdown("""<style>
.block-container{max-width:1500px;padding-top:1.2rem}
.hero{background:linear-gradient(120deg,#101c32,#204b70);color:#fff;padding:24px;border-radius:18px;margin-bottom:1rem}
.hero h1{color:#fff;margin:0}.stMetric{background:#f8fafc;border:1px solid #e2e8f0;padding:12px;border-radius:14px}
div[data-testid="stPlotlyChart"]{border:1px solid #e2e8f0;border-radius:14px;padding:8px}
</style><div class="hero"><h1>🗳️ URNA A URNA</h1><p>BRASIL · 2022 × 2026 · SEGUNDO TURNO PRESIDENCIAL</p><p>Resultados oficiais · comparação histórica · gráficos percentuais</p></div>""",unsafe_allow_html=True)

@st.cache_data(ttl=300,show_spinner=False)
def discover_resources(year):
    url=DATASET[year]; r=requests.get(url,timeout=30,headers={"User-Agent":"Urna-a-Urna/2.0"}); r.raise_for_status()
    soup=BeautifulSoup(r.text,"html.parser"); found=[]
    for a in soup.find_all("a",href=True):
        href=a["href"].strip(); full=urljoin(url,href); label=" ".join(a.get_text(" ",strip=True).split())
        if "cdn.tse.jus.br" not in full or ".zip" not in full.lower(): continue
        blob=(label+" "+full).lower()
        turn=2 if ("2t_" in blob or "segundo turno" in blob or "2º turno" in blob) else (1 if ("1t_" in blob or "primeiro turno" in blob or "1º turno" in blob) else 0)
        m=re.search(r"(?:bweb_[12]t_|^|/)([a-z]{2})[_-]",full.lower()); uf=m.group(1).upper() if m else None
        found.append({"label":label or full.rsplit("/",1)[-1],"url":full,"turn":turn,"uf":uf})
    return list({x["url"]:x for x in found}.values())

def normalize_col(x): return re.sub(r"[^a-z0-9]+","_",str(x).strip().lower()).strip("_")
@st.cache_data(ttl=900,show_spinner=False)
def load_uf(year,uf,turn=2):
    resources=discover_resources(year)
    matches=[r for r in resources if r["turn"]==turn and (r["uf"]==uf or f"/{uf.lower()}_" in r["url"].lower())]
    if not matches: return None,f"Arquivo oficial de {year}, {turn}º turno para {uf} não encontrado no catálogo."
    response=requests.get(matches[0]["url"],timeout=120,headers={"User-Agent":"Urna-a-Urna/2.0"}); response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        frames=[]
        for member in z.namelist():
            if member.lower().endswith(".csv"):
                with z.open(member) as f:
                    d=pd.read_csv(f,sep=";",encoding="latin1",dtype=str,low_memory=False)
                    if len(d.columns)>1: frames.append(d)
    if not frames: return None,"O ZIP oficial não contém CSV legível."
    df=pd.concat(frames,ignore_index=True); df.columns=[normalize_col(c) for c in df.columns]
    required={"nr_turno","sg_uf","nr_zona","nr_secao","ds_cargo_pergunta","ds_tipo_votavel","nr_votavel","nm_votavel","qt_votos"}
    if required-set(df.columns): return None,"Formato do CSV diferente do esperado: "+", ".join(sorted(required-set(df.columns)))
    df=df[pd.to_numeric(df.nr_turno,errors="coerce")==turn].copy()
    df=df[df.ds_cargo_pergunta.fillna("").map(norm).str.contains("PRESIDENTE")]
    df["votos"]=pd.to_numeric(df.qt_votos.str.replace(".","",regex=False).str.replace(",",".",regex=False),errors="coerce").fillna(0).astype("int64")
    cand=df[df.ds_tipo_votavel.fillna("").map(norm).str.contains("NOMINAL")].copy()
    if cand.empty: return None,"Não foram identificados votos nominais no arquivo oficial."
    country_col=next((c for c in ["nm_pais","ds_pais","pais","nome_pais"] if c in cand.columns),None)
    keys=[c for c in ["sg_uf","nm_municipio","nr_zona","nr_secao",country_col,"nr_votavel","nm_votavel","sg_partido","nm_partido"] if c and c in cand.columns]
    agg=cand.groupby(keys,dropna=False,as_index=False).votos.sum().rename(columns={"sg_uf":"uf","nm_municipio":"municipio","nr_zona":"zona","nr_secao":"secao","nr_votavel":"numero","nm_votavel":"candidato","sg_partido":"sigla_partido","nm_partido":"partido"})
    if country_col: agg=agg.rename(columns={country_col:"pais"})
    return {"votes":agg,"resource":matches[0],"country_column":country_col,"rows":len(df)},None
def totals(data):
    if data is None: return pd.DataFrame()
    d=data["votes"]
    return d.groupby(["numero","candidato"],dropna=False,as_index=False).votos.sum().sort_values("votos",ascending=False)
@st.cache_data(ttl=45,show_spinner=False)
def live_json(url):
    r=requests.get(url,timeout=20,headers={"User-Agent":"Urna-a-Urna/2.0"}); r.raise_for_status()
    return r.json(),datetime.now().astimezone().strftime("%d/%m/%Y %H:%M:%S %Z")
def candidate_rows(obj):
    out=[]
    def walk(x):
        if isinstance(x,dict):
            name=x.get("nm") or x.get("nome"); votes=x.get("vap",x.get("votos")); number=x.get("n",x.get("numero",""))
            if name is not None and votes is not None:
                try: out.append({"Número":str(number),"Candidato":str(name),"Votos":int(str(votes).replace(".","")),"Percentual oficial":float(str(x.get("pvap","0")).replace(",","."))})
                except (ValueError,TypeError): pass
            for v in x.values(): walk(v)
        elif isinstance(x,list):
            for v in x: walk(v)
    walk(obj)
    return list({(r["Número"],r["Candidato"]):r for r in out}.values())

with st.sidebar:
    st.header("Filtros")
    view=st.radio("Visualização",["Comparar 2022 × 2026","2022","2026"])
    uf=st.selectbox("Estado",list(UF_NAMES),index=3,format_func=lambda x:f"{x} — {UF_NAMES[x]}")
    scope=st.selectbox("Abrangência",["Estado selecionado","Exterior"])
    ufload="ZZ" if scope=="Exterior" else uf
    municipality=st.text_input("Município (opcional)")
    zone=st.text_input("Zona eleitoral (opcional)")
    section=st.text_input("Seção eleitoral (opcional)")
    st.caption("Os arquivos históricos são baixados somente quando solicitados.")
st.subheader("Apuração ao vivo — 2º turno presidencial de 2026")
st.caption("Fonte: arquivos oficiais JSON do TSE. A divulgação do 2º turno está prevista para 25/10/2026, após o encerramento da votação.")
auto=st.checkbox("Atualizar a cada 60 segundos",value=False)
if auto: st_autorefresh(interval=60_000,key="refresh_tse")
if st.button("Consultar agora",type="primary"):
    st.cache_data.clear(); st.session_state["refresh_live"]=True
if auto or st.session_state.get("refresh_live"):
    try:
        status,checked=live_json(LIVE_STATUS_URL); obj,_=live_json(LIVE_PRESIDENT_URL); rows=candidate_rows(obj)
        st.caption(f"Última consulta concluída: {checked} · TSE")
        if rows:
            live=pd.DataFrame(rows).drop_duplicates(["Número","Candidato"])
            st.dataframe(live,use_container_width=True,hide_index=True)
            fig=px.bar(live.sort_values("Votos"),x="Votos",y="Candidato",orientation="h",text="Percentual oficial",color="Candidato",color_discrete_map={r["Candidato"]:candidate_color(r["Candidato"]) for r in rows})
            fig.update_traces(texttemplate="%{text:.2f}%",textposition="outside",cliponaxis=False)
            fig.update_layout(template="plotly_white",showlegend=False,xaxis_title="Votos",yaxis_title="",margin=dict(l=8,r=40,t=12,b=8))
            st.plotly_chart(fig,use_container_width=True)
        else: st.info("O arquivo respondeu, mas ainda não há registros de candidatos reconhecíveis. Nenhum resultado foi estimado.")
    except Exception as e: st.warning(f"Dados ao vivo indisponíveis neste momento. Nenhum resultado foi inventado. Detalhe: {type(e).__name__}")

if st.button("Buscar dados históricos oficiais",type="primary"):
    with st.spinner("Consultando os catálogos oficiais do TSE…"):
        d22,e22=load_uf(2022,ufload,2); d26,e26=load_uf(2026,ufload,2)
    st.session_state.update({"d22":d22,"e22":e22,"d26":d26,"e26":e26,"loaded":ufload})
d22=st.session_state.get("d22") if st.session_state.get("loaded")==ufload else None
d26=st.session_state.get("d26") if st.session_state.get("loaded")==ufload else None
e22=st.session_state.get("e22"); e26=st.session_state.get("e26")
def apply_filters(d):
    if d is None: return None
    v=d["votes"].copy()
    if municipality and "municipio" in v: v=v[v.municipio.fillna("").str.contains(municipality,case=False,na=False)]
    if zone and "zona" in v: v=v[v.zona.astype(str)==zone.strip()]
    if section and "secao" in v: v=v[v.secao.astype(str)==section.strip()]
    return {**d,"votes":v}
d22=apply_filters(d22); d26=apply_filters(d26)
if scope=="Exterior":
    opts=[]
    for d in (d22,d26):
        if d is not None and "pais" in d["votes"]: opts += d["votes"].pais.dropna().astype(str).unique().tolist()
    opts=sorted(set(x for x in opts if x.strip()))
    if opts:
        country=st.selectbox("País",["Todos os países"]+opts)
        if country!="Todos os países":
            d22={**d22,"votes":d22["votes"][d22["votes"].pais.astype(str)==country]} if d22 is not None and "pais" in d22["votes"] else d22
            d26={**d26,"votes":d26["votes"][d26["votes"].pais.astype(str)==country]} if d26 is not None and "pais" in d26["votes"] else d26
    else: st.warning("O catálogo carregado não expõe um campo de país reconhecível; filtro por país indisponível para evitar atribuições incorretas.")
def render_year(year,d,err):
    st.markdown(f"### {year}")
    if d is None:
        st.warning(err or "Clique em “Buscar dados históricos oficiais” para carregar este ano.")
        return
    t=totals(d)
    if t.empty: st.info("Sem votos nominais reconhecidos neste recorte."); return
    total=int(t.votos.sum()); t["Percentual"]=t.votos/total*100; t["Cor"]=t.candidato.map(candidate_color)
    a,b=st.columns(2); a.metric("Votos nominais",f"{total:,}".replace(",",".")); b.metric("Candidatos no arquivo",len(t))
    st.dataframe(t[["numero","candidato","votos","Percentual"]].style.format({"votos":"{:,.0f}","Percentual":"{:.2f}%"}),use_container_width=True,hide_index=True)
    fig=px.bar(t.sort_values("votos"),x="votos",y="candidato",orientation="h",text="Percentual",color="candidato",color_discrete_map={r.candidato:r.Cor for r in t.itertuples()})
    fig.update_traces(texttemplate="%{text:.2f}%",textposition="outside",cliponaxis=False,marker_line_width=0)
    fig.update_layout(template="plotly_white",showlegend=False,xaxis_title="Votos nominais",yaxis_title="",margin=dict(l=8,r=50,t=12,b=8),height=max(260,48*len(t)),font=dict(size=13))
    st.plotly_chart(fig,use_container_width=True)
    section_cols=[c for c in ["uf","municipio","zona","secao"] if c in d["votes"]]
    if section_cols:
        count=d["votes"][section_cols].drop_duplicates().shape[0]
        st.metric("Seções presentes no arquivo carregado",f"{count:,}".replace(",","."),help="Este número não é o percentual oficial de seções totalizadas.")
    st.caption(f"Fonte: [arquivo oficial do TSE]({d['resource']['url']})")
if view=="Comparar 2022 × 2026":
    left,right=st.columns(2)
    with left: render_year(2022,d22,e22)
    with right: render_year(2026,d26,e26)
else: render_year(int(view),d22 if view=="2022" else d26,e22 if view=="2022" else e26)

st.divider()
st.subheader("Evolução hora a hora e percentual oficial de seções")
st.info("O histórico de boletins por si só não contém a sequência horária da totalização. A curva horária só será mostrada quando houver uma série histórica oficial disponível; o percentual oficial exige o campo de seções totalizadas e esperadas do JSON de acompanhamento. Esta versão não infere esses valores a partir do horário dos boletins.")
st.subheader("Fotos dos candidatos")
c1,c2=st.columns(2)
with c1:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/2/2c/Lula_da_Silva_-_foto_oficial_2023_%28cropped%29.jpg/400px-Lula_da_Silva_-_foto_oficial_2023_%28cropped%29.jpg",caption="Luiz Inácio Lula da Silva · referência visual",use_container_width=True)
    st.markdown(f"<div style='color:{RED};font-weight:700'>Lula — vermelho</div>",unsafe_allow_html=True)
with c2:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Fl%C3%A1vio_Bolsonaro_em_2023.jpg/400px-Fl%C3%A1vio_Bolsonaro_em_2023.jpg",caption="Flávio Bolsonaro · referência visual",use_container_width=True)
    st.markdown(f"<div style='color:{BLUE};font-weight:700'>Flávio Bolsonaro — azul</div>",unsafe_allow_html=True)
st.caption("As fotografias são referências visuais e não substituem a identificação oficial do cadastro de candidaturas do TSE.")
st.markdown("Fontes: [Informações técnicas de divulgação do TSE](https://www.tse.jus.br/eleicoes/informacoes-tecnicas-sobre-a-divulgacao-de-resultados) · [Dados Abertos — BU 2022](https://dadosabertos.tse.jus.br/dataset/resultados-2022-boletim-de-urna)")
st.caption("Painel de comparação. Verifique sempre a abrangência, o turno e a disponibilidade dos dados antes de comparar.")
