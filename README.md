# Urna a Urna 2022 × 2026 — apuração ao vivo e comparação histórica

## Executar
Requer Python 3.10+ e conexão à internet.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Recursos desta versão
- Consulta as páginas oficiais dos conjuntos de Boletins de Urna de 2022 e 2026 no portal de Dados Abertos do TSE.
- Baixa sob demanda o ZIP do segundo turno para uma UF ou exterior (ZZ), quando o recurso estiver publicado.
- Filtra município, zona e seção e soma votos nominais presidenciais.
- Exibe percentuais de votos nominais dentro do recorte carregado e gráfico por candidato.
- Inclui um módulo de acompanhamento ao vivo que consulta os endpoints JSON oficiais do TSE para a eleição presidencial de segundo turno de 2026.
- O módulo ao vivo permite atualização manual ou atualização automática a cada 60 segundos enquanto a página fica aberta. O TSE pode não publicar esses arquivos até o início da divulgação; nesse caso o app mostra indisponibilidade, sem inventar resultados.
- No recorte exterior, oferece filtro por país somente se o arquivo oficial consultado tiver uma coluna explícita de país reconhecível. Não confunde nome de local de votação com país. Se o campo não existir, informa essa limitação na tela.
- Mantém mapa estadual e identifica claramente recortes sem dados.

## Fontes oficiais
- Resultados 2026 e documentação técnica de divulgação: https://www.tse.jus.br/eleicoes/informacoes-tecnicas-sobre-a-divulgacao-de-resultados
- Arquivos técnicos de divulgação 2026: https://www.tse.jus.br/eleicoes/eleicoes-2026-content/arquivos/divulgacao-de-resultados
- Boletins de Urna 2022: https://dadosabertos.tse.jus.br/dataset/resultados-2022-boletim-de-urna
- Boletins de Urna 2026: https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna
- Candidaturas: https://divulgacandcontas.tse.jus.br/divulga/

## Endpoints de totalização ao vivo
O módulo usa os arquivos oficiais do TSE para o segundo turno presidencial de 2026:
- Acompanhamento Brasil: `https://resultados.tse.jus.br/oficial/ele2026/6258/dados/br/br-e006258-ab.json`
- Resultado presidencial: `https://resultados.tse.jus.br/oficial/ele2026/6258/dados/br/br-c0001-e006258-u.json`

Os códigos e caminhos devem ser conferidos na documentação técnica vigente do TSE. Se o TSE alterar a estrutura JSON, o módulo pode precisar de ajuste. O TSE estabelece limites de requisições e pode bloquear temporariamente acessos excessivos; use o intervalo automático de 60 segundos e não reduza esse intervalo.

## Limitações importantes
- Esta versão não foi executada contra os arquivos de totalização do segundo turno durante uma apuração real. A resposta e o esquema dos JSONs devem ser validados quando os arquivos estiverem disponíveis.
- O contador de seções nos arquivos BU não equivale ao percentual oficial de urnas apuradas. O painel ao vivo só exibirá campos que conseguir identificar na resposta oficial.
- O filtro por país depende da existência de uma coluna explícita de país nos CSVs de exterior. Se o arquivo publicado pelo TSE não tiver essa coluna, é necessária uma integração adicional com a estrutura oficial de locais/seções para construir a relação país → local de votação. O aplicativo não infere países a partir de nomes de locais.
- Os arquivos de Boletins de Urna são resultados por seção publicados após o turno; não substituem os arquivos JSON de totalização em tempo real.
- A comparação 2022 × 2026 só é válida quando os dois anos têm arquivos oficiais correspondentes e o mesmo recorte geográfico.
