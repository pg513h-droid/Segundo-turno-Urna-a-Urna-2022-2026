# Urna a Urna 2022 × 2026 — integração TSE

## Executar
Requer Python 3.10+ e conexão à internet.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## O que esta versão faz
- Consulta as páginas oficiais dos conjuntos de Boletins de Urna de 2022 e 2026 no portal CKAN do TSE.
- Descobre links de arquivos reais publicados na página, identificando turno e UF quando possível.
- Baixa sob demanda o ZIP do segundo turno para uma UF (ou exterior ZZ) escolhida.
- Lê CSV com delimitador `;` e codificação Latin-1, valida as colunas essenciais e filtra presidente/turno.
- Soma votos nominais por número/nome do candidato e partido, com filtros opcionais de município, zona e seção.
- Mostra mapa das UFs; somente pinta como líder um estado cujo arquivo foi baixado e processado. Os demais ficam como pendentes.
- Mantém cache temporário para evitar downloads repetidos.

## Fontes
- 2022: https://dadosabertos.tse.jus.br/dataset/resultados-2022-boletim-de-urna
- 2026: https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna
- Candidaturas: https://divulgacandcontas.tse.jus.br/divulga/

## Limitações e cuidados
- O conjunto do TSE informa periodicidade de carregamento após cada turno, não garantia de atualização minuto a minuto.
- Em 23/10/2026, a página consultada de 2026 listava recursos do primeiro turno e ainda não mostrava recursos do segundo turno. O app detecta isso e mantém 2026 como pendente até que os links oficiais existam.
- Os arquivos são grandes e o download é por UF sob demanda. Para mapa nacional integral em produção, será necessário processar todas as UFs em tarefa de backend e armazenar agregados num banco, em vez de baixar 27 ZIPs em uma requisição da interface.
- A identificação de fotos de candidatos não é feita por aproximação de nome. É preciso integrar o cadastro oficial de candidaturas por ID/código de candidatura e usar a foto oficial retornada pela fonte.
- O esquema é validado antes do cálculo. Se o TSE alterar nomes/valores das colunas ou a classificação de tipo de voto, a app mostra erro em vez de inferir números.
- O mapa usa GeoJSON público de estados do Brasil. Antes de uso em produção, hospede uma cópia licenciada/verificada do GeoJSON no próprio projeto.
