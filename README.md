[README.md](https://github.com/user-attachments/files/34156174/README.md)
# Horulince

> Sistema inteligente para auxiliar na localização de veículos roubados ou furtados e de pessoas desaparecidas, com supervisão humana obrigatória e proteção de dados pessoais.

![Status](https://img.shields.io/badge/status-em%20desenvolvimento-yellow)
![Python](https://img.shields.io/badge/backend-Python-3776AB)
![React](https://img.shields.io/badge/frontend-React-61DAFB)
![MySQL](https://img.shields.io/badge/banco-MySQL-4479A1)

> ⚠️ **Projeto acadêmico.** Todos os dados utilizados são **fictícios** e o sistema **não consulta bases policiais reais**. Os indicadores exibidos não representam estatísticas de criminalidade.

## 📌 Sobre o projeto

O Horulince é um projeto da **Fatec Franca "Dr. Thomaz Novelino"** (Análise e Desenvolvimento de Sistemas), apresentado no artigo *"Horulince: sistema inteligente para localização de veículos roubados ou furtados e pessoas desaparecidas"* (CODITEC).

A localização de veículos e de pessoas desaparecidas depende, em grande parte, da observação humana de imagens e de registros dispersos. O Horulince analisa imagens continuamente, aponta **candidatos a correspondência** e os apresenta a um operador, que valida ou descarta cada caso. O sistema produz **indícios, nunca certezas**.

O artigo completo está em [`docs/artigo/`](docs/artigo/).

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

## 🧱 Arquitetura

O sistema é organizado em **quatro camadas**:

```
1. Entrada            2. Borda                3. Servidor central        4. Central de alertas
Vídeos de teste  →    Detecção de veículos →  Correspondência com    →   Painel e dashboard
Câmeras (futuro)      Leitura de placas       listas de alerta           Validação humana
                      Eventos candidatos      Banco de dados             obrigatória
                                              Trilha de auditoria
```

A borda envia ao servidor central **apenas metadados e recortes**, não o vídeo contínuo (minimização de dados). Detalhes em [`docs/arquitetura.md`](docs/arquitetura.md).

### Fluxo de decisão

1. Cada quadro passa pela detecção e pela leitura da placa
2. Sem correspondência com as listas, os dados são **descartados imediatamente**
3. Com correspondência, é emitido um **alerta** ao operador
4. O operador compara a evidência e **confirma para análise**, **descarta** ou **solicita revisão**
5. Tudo fica registrado na auditoria

## 🖥️ Telas do protótipo

1. **Dashboard operacional:** resumo de eventos, alertas pendentes e distribuição por horário
2. **Consulta de veículos:** leitura da placa, detalhes (cor, adesivos, avarias) e consulta à lista fictícia
3. **Busca assistida de pessoa desaparecida:** caso fictício e eventos candidatos *(sem reconhecimento facial)*
4. **Central de alertas e validação humana**
5. **Análise experimental e auditoria**

## 🛠️ Tecnologias

| Camada | Tecnologia |
|--------|-----------|
| Back-end / API | Python (FastAPI ou Flask), SQLAlchemy |
| Detecção de veículos | Modelo da família YOLO |
| Leitura de placas | OpenCV (pré-tratamento) + Tesseract (OCR) |
| Front-end | React + Vite |
| Banco de dados | MySQL |
| Versionamento | Git e GitHub |

## 📁 Estrutura de pastas

```
horulince/
├── backend/     # API, correspondência com listas, alertas e auditoria (Python)
├── edge/        # Camada de borda: captura, detecção de veículos e leitura de placas (Python)
├── frontend/    # Telas do protótipo (React)
├── database/    # Schema, migrations e dados fictícios
├── docs/        # Requisitos, arquitetura, LGPD, plano de validação e artigo
├── scripts/     # Automações e utilitários
└── tests/       # Testes e conjuntos de teste (apenas dados fictícios)
```

## 🚀 Como executar

### Pré-requisitos

- Python 3.10+
- Node.js 18+
- MySQL 8+
- Tesseract OCR instalado no sistema

## 👥 Equipe

| Integrante | Responsabilidade | GitHub |
|-----------|------------------|--------|
| Samuel Paris Fernandes Bueno | Coordenação, banco de dados e integração | [@usuario](https://github.com/usuario) |
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
- **Sem reconhecimento facial** na primeira demonstração; qualquer biometria futura exige revisão jurídica, de privacidade, de segurança e de desempenho

**Neste repositório, nunca versione** vídeos ou imagens reais de câmeras, placas reais ou dados de pessoas reais. Use apenas dados fictícios e gravações simuladas com consentimento.

## 🗺️ Roadmap

- [x] Revisão bibliográfica e legislativa
- [x] Levantamento de requisitos
- [x] Projeto da arquitetura e do fluxo de decisão
- [x] Prototipagem das telas com dados fictícios
- [ ] Implementação dos módulos (detecção, leitura de placas, alertas, auditoria)
- [ ] Validação com vídeos e imagens de teste (precisão, revocação, latência)
- [ ] Diálogo institucional (perspectiva descrita no artigo)

## 📄 Licença

Distribuído sob a licença **MIT** (ajuste conforme decisão do grupo). Veja [`LICENSE`](LICENSE).
