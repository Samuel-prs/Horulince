# Horulince

> Sistema inteligente para auxiliar na localização de veículos roubados ou furtados e de pessoas desaparecidas, com supervisão humana obrigatória e proteção de dados pessoais.

![Status](https://img.shields.io/badge/status-em%20desenvolvimento-yellow)
![Python](https://img.shields.io/badge/linguagem-Python-3776AB)
![SQLite](https://img.shields.io/badge/banco-SQLite-003B57)
![Web](https://img.shields.io/badge/painel-HTML%2FCSS%2FJS-E34F26)

> ⚠️ **Projeto acadêmico.** Todos os dados utilizados são **fictícios** e o sistema **não consulta bases policiais reais**. Os indicadores exibidos não representam estatísticas de criminalidade.

## 📌 Sobre o projeto

O Horulince é um projeto da **Fatec Franca "Dr. Thomaz Novelino"** (Análise e Desenvolvimento de Sistemas), apresentado no artigo *"Horulince: sistema inteligente para localização de veículos roubados ou furtados e pessoas desaparecidas"* (CODITEC).

A localização de veículos e de pessoas desaparecidas depende, em grande parte, da observação humana de imagens e de registros dispersos. O Horulince analisa imagens continuamente, aponta **candidatos a correspondência** e os apresenta a um operador, que valida ou descarta cada caso. O sistema produz **indícios, nunca certezas**.

O artigo completo está em [`docs/artigo/Artigo HoruLince.pdf`](docs/artigo/Artigo HoruLince.pdf).

## 🧭 Estado atual do repositório

Este repositório reúne **duas coisas**:

| | O que é | Onde está |
|---|---|---|
| **Implementação atual** | Painel funcional em Python, SQLite e HTML/CSS/JavaScript | Raiz do repositório |
| **Proposta original** | Documentação e arquitetura planejadas (incluindo componentes futuros como React, API e MySQL) | Pasta [`horulince/`](horulince/) |

A implementação executável usa **SQLite**. Os esquemas MySQL em `horulince/database/` foram preservados como referência e **não são usados** pelo painel local.

## ✅ Implementação atual

O painel inclui:

- Análise de veículos com OCR
- Câmera de rede / iPhone
- Revisão humana
- Auditoria
- Avaliação experimental
- Demonstrações de detecção e de captura facial autorizada
- Acervo pesquisável

**Não estão implementados:** identificação de pessoas e reconhecimento de emoções.

### Como executar

Instale as dependências, disponibilize o modelo local e execute `iniciar_painel.cmd`. O passo a passo completo está em [`GUIA_EXECUCAO.md`](GUIA_EXECUCAO.md).

> Modelos, vídeos, bancos locais, capturas e saídas de validação **não são versionados**.

### Documentação

| Documento | Conteúdo |
|-----------|----------|
| [`GUIA_EXECUCAO.md`](GUIA_EXECUCAO.md) | Instalação e execução da implementação atual |
| [`PAINEL.md`](PAINEL.md) | Guia do painel |
| [`DEMONSTRACOES.md`](DEMONSTRACOES.md) | Demonstrações e acervo |
| [`VALIDACAO.md`](VALIDACAO.md) | Validação do sistema |
| [`IPHONE.md`](IPHONE.md) | Uso do iPhone como câmera |
| [`banco/LEIA-ME_DBA.md`](banco/LEIA-ME_DBA.md) | Scripts SQLite e instruções para o DBA |
| [`horulince/README.md`](horulince/README.md) | Documentação original e arquitetura planejada |

### Estrutura de pastas

```
Horulince/
├── banco/
├── horulince/
├── legado/
├── models/
├── tests/
├── videos/
├── veiculos.py
├── tempo_real.py
├── buscar_alvo.py
├── iniciar_painel.cmd
├── iniciar_iphone.ps1
├── alvos.exemplo.json
├── referencia.exemplo.json
├── requirements.txt
└── requirements.lock.txt
```

## 🎯 Objetivos

- **Geral:** apresentar um sistema inteligente que auxilie na identificação e na localização de veículos roubados ou furtados e de pessoas desaparecidas, com supervisão humana e proteção de dados pessoais.
- **Específicos:**
  - Detectar veículos e ler placas em vídeos de teste
  - Comparar os resultados com listas de alerta (fictícias)
  - Emitir alertas para validação humana obrigatória
  - Registrar todas as ações em trilha de auditoria
  - Medir precisão, revocação e latência do sistema

## ⚙️ Requisitos

| Código | Descrição |
|--------|-----------|
| RF01 | Processar vídeos de teste (e, em etapa futura, câmeras autorizadas) e detectar veículos |
| RF02 | Ler a placa, validar os formatos anterior e Mercosul e registrar detalhes do veículo |
| RF03 | Consultar a lista fictícia de veículos e apoiar a busca assistida com caso fictício |
| RF04 | Emitir alerta com identificador, tipo, origem, data e hora, evidência, confiança e estado |
| RF05 | Exigir validação humana antes de qualquer encaminhamento e registrar tudo em auditoria |
| RNF01 | Exibir o alerta ao operador em poucos segundos após a captura |
| RNF02 | Proteger os dados (criptografia, perfis de acesso e autenticação) |
| RNF03 | Descartar dados sem correspondência e permitir a inclusão de novas fontes de vídeo |

## 🧱 Arquitetura (proposta)

O sistema foi planejado em **quatro camadas**:

```
1. Entrada            2. Borda                3. Servidor central        4. Central de alertas
Vídeos de teste  →    Detecção de veículos →  Correspondência com    →   Painel e dashboard
Câmeras (futuro)      Leitura de placas       listas de alerta           Validação humana
                      Eventos candidatos      Banco de dados             obrigatória
                                              Trilha de auditoria
```

A borda envia ao servidor central **apenas metadados e recortes**, não o vídeo contínuo (minimização de dados). Detalhes em [`horulince/`](horulince/).

### Fluxo de decisão

1. Cada quadro passa pela detecção e pela leitura da placa
2. Sem correspondência com as listas, os dados são **descartados imediatamente**
3. Com correspondência, é emitido um **alerta** ao operador
4. O operador compara a evidência e **confirma para análise**, **descarta** ou **solicita revisão**
5. Tudo fica registrado na auditoria

## 👥 Equipe

| Integrante | Responsabilidade | GitHub |
|-----------|------------------|--------|
| Samuel Paris Fernandes Bueno | Coordenação, banco de dados e integração | [@Samuel-prs](https://github.com/Samuel-prs) |
| Brendom Vinicius Ortiz Siqueira | IA e visão computacional | [@usuario](https://github.com/usuario) |
| Gianlucca Soncini de Lima e Silva | Back-end e regras de correspondência | [@usuario](https://github.com/usuario) |
| Rafael Martins de Souza | Telas e usabilidade | [@usuario](https://github.com/usuario) |
| Pedro Henrique Da Cunha Corsi | Testes, proteção de dados e documentação | [@usuario](https://github.com/usuario) |

## 🤝 Como contribuir

1. Crie uma branch a partir da `main`: `git checkout -b feature/nome-da-tarefa`
2. Faça commits pequenos no padrão `tipo: descrição` (ex.: `feat: valida placa Mercosul`)
3. Abra um **Pull Request** e aguarde a revisão de pelo menos um colega

Regras completas em [`CONTRIBUTING.md`](CONTRIBUTING.md).

## 🔒 Privacidade e governança

O projeto segue os princípios da **LGPD (Lei nº 13.709/2018)** como requisitos de arquitetura:

- **Finalidade restrita:** leitura de placas limitada às listas de veículos com restrição; busca assistida limitada a casos autorizados
- **Minimização:** descarte imediato de dados sem correspondência
- **Segurança:** criptografia, controle de acesso por perfil e autenticação
- **Transparência:** trilha de auditoria de todas as consultas
- **Supervisão humana** de toda decisão que resulte em encaminhamento
- **Biometria:** as demonstrações de captura facial exigem **autorização** de quem participa. Não há identificação de pessoas nem reconhecimento de emoções. Qualquer uso futuro exige revisão jurídica, de privacidade, de segurança e de desempenho

**Neste repositório, nunca versione** vídeos ou imagens reais de câmeras, placas reais ou dados de pessoas reais. Use apenas dados fictícios e gravações simuladas com consentimento.

## 🗺️ Roadmap

**Concluído**
- [x] Revisão bibliográfica e legislativa
- [x] Levantamento de requisitos
- [x] Projeto da arquitetura e do fluxo de decisão
- [x] Prototipagem das telas com dados fictícios
- [x] Painel funcional em Python, SQLite e HTML/CSS/JavaScript
- [x] Análise de veículos com leitura de placas (OCR)
- [x] Entrada por câmera de rede / iPhone
- [x] Revisão humana dos alertas
- [x] Trilha de auditoria
- [x] Avaliação experimental
- [x] Demonstrações de detecção e de captura facial autorizada
- [x] Acervo pesquisável

**Próximas etapas**
- [ ] Validação com vídeos e imagens de teste (precisão, revocação, latência)
- [ ] Migração para a arquitetura planejada (API, front-end React e MySQL), se o grupo decidir seguir esse caminho
- [ ] Diálogo institucional (perspectiva descrita no artigo)

## 📄 Licença

Distribuído sob a licença **MIT** (ajuste conforme decisão do grupo). Veja [`LICENSE`](LICENSE).
