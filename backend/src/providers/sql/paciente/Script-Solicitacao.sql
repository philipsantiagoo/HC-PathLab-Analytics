SELECT 
    -- Código da Solicitação Digitado
    sol.seq AS codigo_solicitacao,
    
    -- Data da Solicitação do Exame (Formatada em dd/mm/aaaa)
    to_char(sol.criado_em, 'DD/MM/YYYY') AS data_solicitacao,
    
    -- Nome do Paciente (Buscado via Atendimento)
    pac.nome AS nome_paciente,
    
    -- Data de Nascimento Ajustada (Sem hora e formatada em dd/mm/aaaa)
    to_char(pac.dt_nascimento, 'DD/MM/YYYY') AS data_nascimento,
    
    pac.prontuario AS prontuario,
    
    -- Convênio do Paciente
    cnv.descricao AS convenio,
    
    -- Origem do Atendimento (Calibrado com as regras reais do seu hospital)
    CASE 
        WHEN atd.origem = 'I' THEN 'Internação'
        WHEN atd.origem = 'A' THEN 'Ambulatório'
        WHEN atd.origem = 'C' THEN 'Cirurgia'
        WHEN atd.origem = 'N' THEN 'Neonatal'
        WHEN atd.origem = 'U' THEN 'Urgência'
        WHEN atd.origem = 'X' THEN 'Paciente Externo'
        WHEN atd.origem = 'D' THEN 'Doação de Sangue'
        WHEN atd.origem = 'H' THEN 'Hospital Dia'
        ELSE 'Outra Origem (' || atd.origem || ')' 
    END AS origem,
    
    -- Unidade Funcional Hospitalar (Onde o paciente está/esteve)
    unf_atd.descricao AS unidade,
    
    -- Informações Clínicas gravadas na solicitação pelo médico
    sol.informacoes_clinicas AS informacoes_clinica,
    
    -- Identificadores e Nomes do Exame / Material
    item.ufe_ema_exa_sigla AS sigla_exame,
    exm.descricao AS nome_exame,                  
    item.desc_material_analise AS descricao_material 

FROM agh.ael_solicitacao_exames sol
-- Junção com os itens da solicitação
JOIN agh.ael_item_solicitacao_exames item ON item.soe_seq = sol.seq

-- Junção com o Atendimento para alcançar os dados do paciente
LEFT JOIN agh.agh_atendimentos atd ON atd.seq = sol.atd_seq
LEFT JOIN agh.aip_pacientes pac ON pac.codigo = atd.pac_codigo

-- Tradução do código do convênio
LEFT JOIN agh.fat_convenios_saude cnv ON cnv.codigo = sol.csp_cnv_codigo

-- Tradução da Unidade Funcional do Atendimento
LEFT JOIN agh.agh_unidades_funcionais unf_atd ON unf_atd.seq = atd.unf_seq

-- Cadastro Geral do Exame
JOIN agh.ael_exames exm ON exm.sigla = item.ufe_ema_exa_sigla

-- FILTRO TEMPORAL: Traz apenas solicitações feitas de 1º de Janeiro de 2026 em diante
WHERE sol.criado_em >= '2026-01-01 00:00:00'

-- Ordenação para mostrar as solicitações mais recentes no topo da lista
ORDER BY sol.criado_em DESC;