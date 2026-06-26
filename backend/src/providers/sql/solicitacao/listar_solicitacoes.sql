SELECT
    sol.seq AS codigo_solicitacao,
    to_char(sol.criado_em, 'DD/MM/YYYY') AS data_solicitacao,
    pac.nome AS nome_paciente,
    to_char(pac.dt_nascimento, 'DD/MM/YYYY') AS data_nascimento,
    pac.prontuario AS prontuario,
    cnv.descricao AS convenio,
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
    unf_atd.descricao AS unidade,
    sol.informacoes_clinicas AS informacoes_clinica,
    item.ufe_ema_exa_sigla AS sigla_exame,
    exm.descricao AS nome_exame,
    item.desc_material_analise AS descricao_material
FROM agh.ael_solicitacao_exames sol
JOIN agh.ael_item_solicitacao_exames item ON item.soe_seq = sol.seq
LEFT JOIN agh.agh_atendimentos atd ON atd.seq = sol.atd_seq
LEFT JOIN agh.aip_pacientes pac ON pac.codigo = atd.pac_codigo
LEFT JOIN agh.fat_convenios_saude cnv ON cnv.codigo = sol.csp_cnv_codigo
LEFT JOIN agh.agh_unidades_funcionais unf_atd ON unf_atd.seq = atd.unf_seq
JOIN agh.ael_exames exm ON exm.sigla = item.ufe_ema_exa_sigla
WHERE sol.criado_em >= '2026-01-01 00:00:00'
ORDER BY sol.criado_em DESC;
