# Urna a Urna 2022 × 2026

Dashboard Streamlit para consulta e comparação de boletins de urna do TSE.

## Publicação
- Arquivo principal: `app.py`
- Dependências: `requirements.txt`
- Plataforma: Streamlit Community Cloud, branch `main`, entrypoint `app.py`

## Observações de integridade
- Lula é vermelho (`#dc2626`); Bolsonaro é azul (`#2563eb`).
- Gráficos mostram percentual dos votos nominais no conjunto filtrado.
- A contagem de seções presentes no CSV não é apresentada como percentual oficial de apuração.
- A curva histórica horária e o percentual oficial de seções só devem ser habilitados após integrar e validar os campos oficiais de acompanhamento do TSE para o segundo turno.
- A fonte JSON de segundo turno pode não publicar resultados antes da abertura da divulgação.
