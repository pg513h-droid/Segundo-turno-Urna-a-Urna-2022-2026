import io, re, zipfile, json, time
from datetime import datetime, timezone
from urllib.parse import urljoin
import requests
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import plotly.express as px
from bs4 import BeautifulSoup

st.set_page_config(page_title="Urna a Urna 2022 × 2026", page_icon="🗳️", layout="wide")
LIVE_BASE = "https://resultados.tse.jus.br/oficial/ele2026/6258/dados/br/"
LIVE_STATUS_URL = LIVE_BASE + "br-e006258-ab.json"
LIVE_PRESIDENT_URL = LIVE_BASE + "br-c0001-e006258-u.json"
TSE = "https://dadosabertos.tse.jus.br"
DATASET = {
    2022: f"{TSE}/dataset/resultados-2022-boletim-de-urna",
    2026: f"{TSE}/dataset/resultados-2026-boletim-de-urna",
}
UF_NAMES = {"AC":"Acre","AL":"Alagoas","AP":"Amapá","AM":"Amazonas","BA":"Bahia","CE":"Ceará","DF":"Distrito Federal","ES":"Espírito Santo","GO":"Goiás","MA":"Maranhão","MG":"Minas Gerais","MS":"Mato Grosso do Sul","MT":"Mato Grosso","PA":"Pará","PB":"Paraíba","PE":"Pernambuco","PI":"Piauí","PR":"Paraná","RJ":"Rio de Janeiro","RN":"Rio Grande do Norte","RO":"Rondônia","RR":"Roraima","RS":"Rio Grande do Sul","SC":"Santa Catarina","SE":"Sergipe","SP":"São Paulo","TO":"Tocantins"}
UF_ALL=list(UF_NAMES)
COLORS=["#2563eb","#e5a11a","#16a34a","#9333ea","#dc2626","#0891b2"]
BLUE_CANDIDATES=("JAIR BOLSONARO", "FLAVIO BOLSONARO", "FLÁVIO BOLSONARO")
RED_CANDIDATES=("LUIZ INACIO LULA DA SILVA", "LUIZ INÁCIO LULA DA SILVA", "LULA")

def candidate_color(name):
    normalized=" ".join(str(name).upper().split())
    if any(term in normalized for term in BLUE_CANDIDATES): return "#2563eb"
    if any(term in normalized for term in RED_CANDIDATES): return "#dc2626"
    return "#64748b"

st.markdown("""
<style>
.block-container{max-width:1500px;padding-top:1.3rem}
.hero{background:linear-gradient(120deg,#101c32,#204b70);color:white;padding:24px;border-radius:18px}
.hero h1{color:white;margin:0}.small{color:#64748b;font-size:.85rem}
</style>
<div class="hero"><h1>🗳️ URNA A URNA</h1><p>BRASIL · 2022 × 2026 · SEGUNDO TURNO PRESIDENCIAL</p>
<p>Boletins de Urna oficiais · comparação histórica · mapa por estado</p></div>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300, show_spinner=False)
def discover_resources(year):
    """Scrape the official TSE dataset page, returning only actual linked resources."""
    url=DATASET[year]
    r=requests.get(url,timeout=30,headers={"User-Agent":"Urna-a-Urna/1.0 (research dashboard)"})
    r.raise_for_status()
    soup=BeautifulSoup(r.text,"html.parser")
    found=[]
    for a in soup.find_all("a",href=True):
        href=a["href"].strip()
        label=" ".join(a.get_text(" ",strip=True).split())
        full=urljoin(url,href)
        if "cdn.tse.jus.br" in full and (".zip" in full.lower() or "Boletim de Urna" in label):
            blob=(label+" "+full).lower()
            turn=2 if ("2t_" in blob or "segundo turno" in blob or "2º turno" in blob) else (1 if ("1t_" in blob or "primeiro turno" in blob or "1º turno" in blob) else 0)
            ufmatch=re.search(r"(?:bweb_[12]t_|^|/)([a-z]{2})[_-]",full.lower())
            uf=ufmatch.group(1).upper() if ufmatch else None
            if uf not in UF_NAMES and uf!="ZZ": uf=None
            found.append({"label":label or full.rsplit("/",1)[-1],"url":full,"turn":turn,"uf":uf})
    # remove duplicate links, preserve published resource names
    unique={x["url"]:x for x in found}
    return list(unique.values())

def normalize_col(name):
    return re.sub(r"[^a-z0-9]+","_",str(name).strip().lower()).strip("_")

@st.cache_data(ttl=900, show_spinner=False)
def load_uf(year, uf, turn=2):
    resources=discover_resources(year)
    matches=[r for r in resources if r["turn"]==turn and (r["uf"]==uf or uf in r["url"].upper()) and ".zip" in r["url"].lower()]
    if not matches:
        return None, f"Arquivo de {year}, {turn}º turno para {uf} ainda não foi encontrado no catálogo oficial."
    # TSE publishes one ZIP per UF. Download only the requested resource.
    res=matches[0]
    response=requests.get(res["url"],timeout=120,headers={"User-Agent":"Urna-a-Urna/1.0"})
    if response.status_code != 200:
        return None, f"Download TSE retornou HTTP {response.status_code}."
    try:
        z=zipfile.ZipFile(io.BytesIO(response.content))
        csvs=[n for n in z.namelist() if n.lower().endswith(".csv")]
        if not csvs:
            return None, "ZIP oficial não contém CSV reconhecível."
        frames=[]
        for member in csvs:
            with z.open(member) as f:
                df=pd.read_csv(f,sep=";",encoding="latin1",dtype=str,low_memory=False)
                if len(df.columns)>1: frames.append(df)
        if not frames: return None, "CSV oficial não pôde ser lido."
        df=pd.concat(frames,ignore_index=True)
        df.columns=[normalize_col(c) for c in df.columns]
        required={"nr_turno","sg_uf","nr_zona","nr_secao","ds_cargo_pergunta","ds_tipo_votavel","nr_votavel","nm_votavel","qt_votos"}
        missing=required-set(df.columns)
        if missing: return None, "Esquema não reconhecido; faltam colunas: "+", ".join(sorted(missing))
        df["nr_turno_num"]=pd.to_numeric(df["nr_turno"],errors="coerce")
        df=df[df["nr_turno_num"]==turn].copy()
        cargo=df["ds_cargo_pergunta"].fillna("").str.normalize("NFKD").str.encode("ascii",errors="ignore").str.decode("ascii").str.upper()
        df=df[cargo.str.contains("PRESIDENTE",na=False)]
        df["qt_votos_num"]=pd.to_numeric(df["qt_votos"].str.replace(".","",regex=False).str.replace(",",".",regex=False),errors="coerce").fillna(0).astype("int64")
        df["ds_tipo_votavel_norm"]=df["ds_tipo_votavel"].fillna("").str.upper()
        # Candidate votes only; blanks/nulls are available separately for future metric expansion.
        cand=df[df["ds_tipo_votavel_norm"].str.contains("NOMINAL",na=False)].copy()
        if cand.empty:
            # Some TSE releases label candidate votes differently; don't guess if schema differs.
            return None, "Coluna de tipo de voto não identificou votos nominais. Revisão do esquema necessária."
        # Preserve a country field only when the source explicitly provides one.
        country_candidates=["nm_pais","ds_pais","pais","nome_pais","nm_pais_exterior","ds_localidade_exterior"]
        country_col=next((c for c in country_candidates if c in cand.columns),None)
        group_cols=[c for c in ["sg_uf","nm_municipio","cd_municipio","nr_zona","nr_secao",country_col,"nr_votavel","nm_votavel","sg_partido","nm_partido"] if c and c in cand.columns]
        agg=cand.groupby(group_cols,dropna=False,as_index=False)["qt_votos_num"].sum()
        agg=agg.rename(columns={"qt_votos_num":"votos","nm_votavel":"candidato","nr_votavel":"numero","sg_uf":"uf","nm_municipio":"municipio","nr_zona":"zona","nr_secao":"secao","sg_partido":"sigla_partido","nm_partido":"partido"})
        if country_col and country_col in agg.columns: agg=agg.rename(columns={country_col:"pais"})
        return {"votes":agg,"resource":res,"rows":len(df),"columns":list(df.columns),"country_column":country_col}, None
    except Exception as e:
        return None, f"Falha ao processar arquivo oficial: {e}"

@st.cache_data(ttl=86400, show_spinner=False)
def geojson_states():
    url="https://raw.githubusercontent.com/codeforgermany/click_that_hood/main/public/data/brazil-states.geojson"
    r=requests.get(url,timeout=20); r.raise_for_status()
    return r.json()

@st.cache_data(ttl=45, show_spinner=False)
def fetch_live_json(url):
    """Fetch an official TSE 2026 second-round JSON endpoint; no fabricated fallback."""
    response=requests.get(url,timeout=20,headers={"User-Agent":"Urna-a-Urna/1.1"})
    response.raise_for_status()
    return response.json(), datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M:%S %Z")

def find_candidate_rows(obj):
    """Find candidate-shaped records in TSE JSON while tolerating harmless schema nesting."""
    found=[]
    def walk(node):
        if isinstance(node,dict):
            # TSE result records commonly use n/nm/vap/pvap; accept only explicit vote fields.
            name=node.get("nm") or node.get("nome") or node.get("candidateName")
            votes=node.get("vap",node.get("votos",node.get("votes")))
            number=node.get("n",node.get("numero",node.get("candidateNumber","")))
            if name is not None and votes is not None:
                try:
                    numeric=int(str(votes).replace(".","").replace(",","."))
                    pct=node.get("pvap",node.get("percentual",node.get("percentage")))
                    found.append({"Número":str(number),"Candidato":str(name),"Votos":numeric,"Percentual informado pelo TSE":str(pct) if pct is not None else "—"})
                except (TypeError,ValueError): pass
            for value in node.values(): walk(value)
        elif isinstance(node,list):
            for value in node: walk(value)
    walk(obj)
    unique={ (r["Número"],r["Candidato"]):(r) for r in found }
    return list(unique.values())

def candidate_totals(data):
    if data is None: return pd.DataFrame()
    return data["votes"].groupby(["numero","candidato","sigla_partido","partido"],dropna=False,as_index=False)["votos"].sum().sort_values("votos",ascending=False)

with st.sidebar:
    st.header("Filtros")
    view=st.radio("Visualização",["Comparar 2022 × 2026","2022","2026"])
    uf=st.selectbox("Estado para carregar",UF_ALL,index=3,format_func=lambda x:f"{x} — {UF_NAMES[x]}")
    scope=st.selectbox("Recorte",["Estado selecionado","Exterior (ZZ)"])
    ufload="ZZ" if scope.startswith("Exterior") else uf
    municipality=st.text_input("Município (opcional)")
    zone=st.text_input("Zona eleitoral (opcional)")
    section=st.text_input("Seção eleitoral (opcional)")
    st.caption("O download é feito por UF, sob demanda, para evitar baixar dezenas de arquivos grandes de uma vez.")

st.divider()
st.subheader("🔴 Apuração ao vivo — 2º turno presidencial de 2026")
st.caption("Consulta os arquivos JSON oficiais de divulgação do TSE. O endpoint do segundo turno pode ainda não estar ativo antes do início da divulgação.")
auto_live=st.checkbox("Atualizar automaticamente a cada 60 segundos enquanto esta página estiver aberta",value=False)
if auto_live:
    st_autorefresh(interval=60_000,key="tse_live_autorefresh")
if st.button("Consultar / atualizar apuração ao vivo",type="primary",key="live_refresh"):
    st.cache_data.clear()
    st.session_state["live_refresh_requested"]=True
if auto_live or st.session_state.get("live_refresh_requested",False):
    try:
        live_status, checked_at=fetch_live_json(LIVE_STATUS_URL)
        live_json, checked_at2=fetch_live_json(LIVE_PRESIDENT_URL)
        rows=find_candidate_rows(live_json)
        st.caption(f"Última consulta concluída: {checked_at2} · Fonte: TSE")
        if rows:
            live_df=pd.DataFrame(rows).drop_duplicates(subset=["Número","Candidato"])
            st.dataframe(live_df,use_container_width=True,hide_index=True)
            st.info("Os campos apresentados são extraídos do JSON oficial. Confira no portal do TSE se a divulgação do segundo turno já começou; a ausência de resultados não significa zero votos.")
        else:
            st.warning("O endpoint respondeu, mas não foi possível reconhecer registros de candidatos no formato recebido. Nenhum resultado foi estimado.")
            with st.expander("Ver metadados do arquivo oficial"):
                st.json({k:v for k,v in live_status.items() if k in ["dt","hora","st","s","pst","ps","e"]} if isinstance(live_status,dict) else {})
    except Exception as e:
        st.warning("Os arquivos oficiais de totalização do segundo turno ainda não estão disponíveis ou não puderam ser consultados. Tente novamente mais tarde. Nenhum dado foi inventado.")
        st.caption(f"Detalhe técnico: {type(e).__name__}: {e}")

st.subheader("Disponibilidade das fontes oficiais")
resource_status={}
for year in (2022,2026):
    with st.expander(f"Catálogo TSE — {year}",expanded=(year==2026)):
        try:
            rs=discover_resources(year)
            twos=[x for x in rs if x["turn"]==2]
            ones=[x for x in rs if x["turn"]==1]
            resource_status[year]=(len(twos),len(ones))
            st.write(f"Recursos localizados: {len(rs)} · 1º turno: {len(ones)} · 2º turno: {len(twos)}")
            if twos:
                st.success("Há recursos identificados como segundo turno no catálogo.")
                for x in twos[:5]: st.markdown(f"- [{x['label'] or x['url']}]({x['url']})")
            else:
                st.warning("Segundo turno ainda não encontrado no catálogo consultado. O painel mantém o ano como pendente; não estima resultados.")
            st.markdown(f"[Abrir conjunto oficial {year}]({DATASET[year]})")
        except Exception as e:
            st.error(f"Não foi possível consultar o catálogo: {e}")
            resource_status[year]=(0,0)

st.info("Os ZIPs de Boletins de Urna são conjuntos históricos publicados após cada turno. Para acompanhamento durante a apuração, use o módulo JSON ao vivo acima, que consulta os arquivos oficiais de totalização do TSE.")

if st.button("Buscar e processar dados oficiais para o recorte",type="primary"):
    with st.spinner(f"Consultando TSE e baixando arquivo de {ufload}…"):
        data22,err22=load_uf(2022,ufload,2)
        data26,err26=load_uf(2026,ufload,2)
    st.session_state["data22"]=data22
    st.session_state["err22"]=err22
    st.session_state["data26"]=data26
    st.session_state["err26"]=err26
    st.session_state["loaded_uf"]=ufload

if "loaded_uf" in st.session_state and st.session_state["loaded_uf"]==ufload:
    data22=st.session_state.get("data22")
    data26=st.session_state.get("data26")
    err22=st.session_state.get("err22")
    err26=st.session_state.get("err26")
else:
    data22=data26=err22=err26=None

if municipality or zone or section:
    def filtered(data):
        if not data: return data
        d=data.copy(); v=d["votes"]
        if municipality and "municipio" in v: v=v[v["municipio"].fillna("").str.contains(municipality,case=False)]
        if zone and "zona" in v: v=v[v["zona"].astype(str)==zone.strip()]
        if section and "secao" in v: v=v[v["secao"].astype(str)==section.strip()]
        return {**d,"votes":v}
    data22=filtered(data22); data26=filtered(data26)

if scope.startswith("Exterior"):
    country_options=[]
    for loaded_data in (data22,data26):
        if loaded_data is not None and "pais" in loaded_data["votes"].columns:
            country_options.extend(loaded_data["votes"]["pais"].dropna().astype(str).unique().tolist())
    country_options=sorted(set(x for x in country_options if x.strip()))
    if country_options:
        selected_country=st.selectbox("País do exterior (somente se informado explicitamente no arquivo oficial)", ["Todos os países"]+country_options)
        if selected_country!="Todos os países":
            def country_filter(data):
                if data is None or "pais" not in data["votes"].columns: return data
                return {**data,"votes":data["votes"][data["votes"]["pais"].astype(str)==selected_country]}
            data22=country_filter(data22); data26=country_filter(data26)
    else:
        st.warning("Os CSVs encontrados não expõem uma coluna de país reconhecível. Para não confundir local de votação com país, o filtro por país ficará indisponível até confirmar o campo correto do arquivo oficial.")

st.subheader("Resumo por candidato")
left,right=st.columns(2)
for col,year,data,err in [(left,2022,data22,err22),(right,2026,data26,err26)]:
    with col:
        st.markdown(f"### {year}")
        if data is None:
            st.warning(err or "Pendente: clique em “Buscar e processar dados oficiais” para consultar a fonte.")
        else:
            totals=candidate_totals(data)
            if totals.empty: st.warning("Nenhum voto nominal de presidente foi identificado.")
            else:
                total=int(totals["votos"].sum())
                totals=totals.copy()
                totals["% dos votos nominais"]=(totals["votos"] / total * 100).round(2)
                totals["cor"] = totals["candidato"].map(candidate_color)
                st.metric("Votos nominais processados",f"{total:,}".replace(",","."),help="Soma dos votos nominais identificados nos boletins carregados para o recorte.")
                st.dataframe(totals[["numero","candidato","sigla_partido","votos","% dos votos nominais"]],use_container_width=True,hide_index=True)
                bar=px.bar(totals.sort_values("votos"),x="votos",y="candidato",orientation="h",text="% dos votos nominais",color="candidato",color_discrete_map={r["candidato"]:r["cor"] for _,r in totals.iterrows()})
                bar.update_traces(texttemplate="%{text:.2f}%",textposition="outside",cliponaxis=False)
                bar.update_layout(showlegend=False,xaxis_title="Votos nominais",yaxis_title="",margin={"l":0,"r":35,"t":10,"b":10},height=max(220,50*len(totals)))
                st.plotly_chart(bar,use_container_width=True)
                # Count distinct polling sections represented in this dataset, without claiming it is the official turnout/apuração percentage.
                vote_rows=data["votes"]
                section_cols=[c for c in ["uf","municipio","zona","secao"] if c in vote_rows.columns]
                section_count=int(vote_rows[section_cols].drop_duplicates().shape[0]) if section_cols else 0
                st.metric("Seções representadas no arquivo",f"{section_count:,}".replace(",","."),help="Contagem de seções distintas presentes no arquivo oficial baixado; não equivale ao percentual nacional de urnas apuradas.")
                st.caption(f"Linhas eleitorais processadas: {data['rows']:,} · [Arquivo oficial]({data['resource']['url']})")

st.divider()
st.subheader("Mapa do Brasil — candidato com maior votação por estado")
st.caption("O mapa colore somente estados para os quais os dados do segundo turno foram efetivamente baixados e validados. Estados sem dados permanecem neutros.")
try:
    gj=geojson_states()
    maprows=[]
    loaded={ufload: (data22,data26)}
    # Map is populated from the loaded recorte only. No implied nationwide completeness.
    for code,name in UF_NAMES.items():
        data=data26 if view=="2026" else data22
        if view=="Comparar 2022 × 2026":
            data=data26 if data26 is not None else data22
        if data is not None and ufload==code:
            t=candidate_totals(data)
            if not t.empty:
                win=t.iloc[0]
                maprows.append({"sigla":code,"nome":name,"lider":str(win["candidato"]),"votos":int(win["votos"]),"partido":str(win.get("sigla_partido",""))})
            else: maprows.append({"sigla":code,"nome":name,"lider":"Sem dados","votos":0,"partido":""})
        else:
            maprows.append({"sigla":code,"nome":name,"lider":"Dados pendentes","votos":0,"partido":""})
    m=pd.DataFrame(maprows)
    # Neutral base plus leader labels; colors are assigned only to leaders observed in actual processed data.
    leaders=sorted(m.loc[m["lider"].ne("Dados pendentes") & m["lider"].ne("Sem dados"),"lider"].unique())
    color_map={name:COLORS[i%len(COLORS)] for i,name in enumerate(leaders)}
    color_map.update({"Dados pendentes":"#d1d5db","Sem dados":"#9ca3af"})
    fig=px.choropleth_map(m,geojson=gj,locations="sigla",featureidkey="properties.sigla",color="lider",
       color_discrete_map=color_map,hover_name="nome",hover_data={"lider":True,"partido":True,"votos":":,", "sigla":False},
       map_style="carto-positron",center={"lat":-14.5,"lon":-52},zoom=2.4,opacity=.78)
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0},height=560,legend_title_text="Maior votação no recorte")
    st.plotly_chart(fig,use_container_width=True)
    st.dataframe(m[["sigla","nome","lider","partido","votos"]],use_container_width=True,hide_index=True)
except Exception as e:
    st.error(f"Mapa indisponível neste momento: {e}")

st.divider()
st.subheader("Comparativo hora a hora e percentual de urnas")
st.info("O arquivo final de Boletins de Urna traz os totais de cada seção, não um histórico horário dos resultados durante a apuração. Para exibir uma curva hora a hora real e o percentual oficial de urnas recebidas, é necessário integrar os arquivos históricos/variáveis de totalização do TSE e o total oficial de seções esperadas. Esta versão não estima esses números a partir do horário de geração do boletim.")
st.markdown("Fonte oficial: [Dados Abertos do TSE — Resultados 2022](https://dadosabertos.tse.jus.br/dataset/resultados-2022) · [Conjuntos de Boletins de Urna](https://dadosabertos.tse.jus.br/dataset/resultados-2022-boletim-de-urna)")

st.subheader("Fotos e cadastro oficial dos candidatos")
st.write("O nome e o partido são lidos dos boletins. As fotos oficiais precisam ser vinculadas ao cadastro de candidaturas do TSE (DivulgaCandContas) por número/ID de candidatura; esta versão não associa fotos por busca textual para evitar identificação errada.")
st.markdown("[Portal oficial DivulgaCandContas](https://divulgacandcontas.tse.jus.br/divulga/) · [Portal de Dados Abertos do TSE](https://dadosabertos.tse.jus.br/dataset/)")
st.caption("Última consulta local: "+datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M:%S %Z"))
