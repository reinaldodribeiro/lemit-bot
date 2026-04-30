====================================================
  LEMIT DADOS BOT - Guia do Usuário
====================================================

REQUISITOS
----------
- Windows 10 ou superior
- Conexão com a internet
- Uma conta ativa no Lemit Dados (lemit.app.br)

ESTRUTURA DE PASTAS
-------------------
LemitBot/
  lemit_bot.exe     <- Execute este arquivo para iniciar o bot
  config.json       <- Configurações e credenciais (EDITE ANTES DE USAR)
  entrada/          <- Coloque sua planilha Excel aqui
  saida/            <- Os resultados serão gerados aqui
  logs/             <- Arquivos de log detalhados
  chromium/         <- Navegador interno (não mexa nesta pasta)

PASSO A PASSO
-------------

1. CONFIGURAR CREDENCIAIS
   - Abra o arquivo config.json com o Bloco de Notas
   - Substitua "usuario@email.com" pelo seu email do Lemit Dados
   - Substitua "senha" pela sua senha do Lemit Dados
   - Salve o arquivo

2. PREPARAR A PLANILHA
   - Sua planilha Excel deve ter uma aba com as colunas:
       cpf    (CPF do cliente, com ou sem formatação)
       nome   (Nome completo do cliente)
   - Coloque o arquivo .xlsx na pasta "entrada"

3. EXECUTAR O BOT
   - Clique duas vezes em lemit_bot.exe
   - Se houver mais de um arquivo Excel na pasta "entrada",
     o bot exibirá um menu para você escolher qual processar
   - Acompanhe o progresso na janela que abrir

4. VERIFICAR RESULTADOS
   - Ao terminar, o bot criará um arquivo Excel em "saida/"
     com o nome: resultado_YYYY-MM-DD_HH-MM.xlsx
   - O arquivo conterá as colunas originais mais:
       telefone_1, telefone_2, telefone_3  (números encontrados)
       consulta_usada  (cpf, nome ou cpf+nome)
       status_consulta (veja abaixo)
       observacao      (detalhes em caso de erro)
       data_consulta   (data e hora da consulta)

STATUS DA CONSULTA
------------------
  encontrado_por_cpf   = Dados encontrados usando o CPF          (verde)
  encontrado_por_nome  = Dados encontrados usando o nome          (amarelo)
  nao_encontrado       = Nenhum dado encontrado                   (vermelho)
  erro                 = Ocorreu um erro técnico nessa linha      (cinza)

CAPTCHA
-------
Se aparecer um captcha durante a execução:
  - Configure "headless": false no config.json
  - Execute o bot novamente
  - Quando aparecer a mensagem [CAPTCHA], resolva o captcha
    no navegador que abrir e pressione ENTER

CONTINUAR UMA EXECUÇÃO INTERROMPIDA
------------------------------------
Se o bot for fechado no meio do processamento, execute-o novamente.
Ele detectará automaticamente quais linhas já foram processadas
e continuará de onde parou.

PERSONALIZAR NOMES DE COLUNAS
------------------------------
Se sua planilha usa nomes de colunas diferentes de "cpf" e "nome",
edite o config.json e ajuste os campos:
  "excel": {
    "cpf_column": "seu_nome_de_coluna_cpf",
    "name_column": "seu_nome_de_coluna_nome"
  }

CONFIGURAÇÕES AVANÇADAS (config.json)
--------------------------------------
  headless                       true = navegador oculto (padrão)
                                 false = navegador visível (útil para depurar)
  delay_between_queries_seconds  Pausa entre consultas (padrão: 2 segundos)
  max_retries                    Tentativas em caso de erro (padrão: 2)

EM CASO DE PROBLEMAS
--------------------
1. Verifique os arquivos de log em "logs/" para detalhes do erro
2. Certifique-se de que seu email/senha no config.json estão corretos
3. Verifique se você tem acesso ativo ao Lemit Dados no navegador
4. Se o antivírus bloquear o .exe, adicione-o à lista de exceções

SEGURANÇA E PRIVACIDADE
-----------------------
- O config.json contém suas credenciais. NÃO compartilhe este arquivo.
- Os arquivos de saída contêm CPF e telefone (dados sensíveis).
  Trate-os com o mesmo cuidado que a planilha original.
- O bot NÃO tenta contornar captchas, limites ou bloqueios do sistema.

====================================================
