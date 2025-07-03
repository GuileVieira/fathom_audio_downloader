# Fathom - Processador de Vídeos em Lote

Este projeto automatiza o download, conversão e transcrição de vídeos da plataforma Fathom em lote.

## Funcionalidades

-   **Processamento Paralelo:** Processa até 4 vídeos simultaneamente.
-   **Extração de Áudio:** Baixa e converte apenas o áudio dos vídeos para MP3, economizando tempo e espaço.
-   **Aceleração de Áudio:** Acelera automaticamente o áudio para 1.75x (otimizado para qualidade).
-   **Transcrição Automática:** Usa a API do AssemblyAI para transcrever os áudios com separação de speakers.
-   **Extração de Metadados:** Extrai metadados completos das calls diretamente do HTML.
-   **Estrutura Unificada:** Combina metadados do Fathom com transcrição do AssemblyAI em formato padronizado.
-   **Transcrição Original:** Preserva a transcrição original do Fathom extraída do HTML.
-   **Download de HTML:** Baixa o HTML completo das páginas do Fathom para backup/análise.
-   **Controle de Progresso:** Salva o progresso e permite retomar o processo em caso de falha, evitando trabalho duplicado.

---

## 1. Instalação e Configuração

### Dependências do Sistema

Certifique-se de que você tem o **FFmpeg** instalado no seu sistema. Ele é necessário para a conversão de áudio.

-   **Windows (usando Chocolatey):** `choco install ffmpeg`
-   **macOS (usando Homebrew):** `brew install ffmpeg`
-   **Linux (Debian/Ubuntu):** `sudo apt update && sudo apt install ffmpeg`

### Dependências do Python

1.  Instale todas as bibliotecas Python necessárias com um único comando:
    ```bash
    pip install -r requirements.txt
    ```
2.  Instale os navegadores para o Playwright (só precisa ser feito uma vez):
    ```bash
    playwright install
    ```

### Chave da API (AssemblyAI)

1.  Crie uma cópia do arquivo de exemplo `.env.example` e renomeie para `.env`.
2.  Abra o arquivo `.env` e substitua `"sua_chave_aqui"` pela sua chave real da API do AssemblyAI.
    ```
    ASSEMBLYAI_API_KEY=sua_chave_real_aqui
    ```

---

## 2. Obtenção dos Dados de Autenticação

Para que o script possa acessar os vídeos, ele precisa dos seus dados de autenticação. Crie uma pasta chamada `cookies` na raiz do projeto. O processo é feito em duas etapas para obter os 3 arquivos necessários.

### Etapa A: Exportar Cookies com Extensão

1.  Instale uma extensão para exportar cookies no seu navegador, como a **Cookie-Editor**.
2.  Acesse [fathom.video](https://fathom.video) e faça login na sua conta.
3.  Com a extensão, exporte todos os cookies do site no formato **JSON**.
4.  Salve o arquivo com o nome `cookies.json` dentro da pasta `cookies/`.

### Etapa B: Exportar Local e Session Storage via Console

1.  Ainda na página do Fathom (logado), abra as Ferramentas de Desenvolvedor (F12) e vá para a aba "Console".
2.  Copie todo o conteúdo do arquivo `download_data_cookies.js`.
3.  Cole o código no console e pressione Enter.
4.  Isso irá baixar automaticamente os arquivos `local_storage.json` e `session_storage.json`.
5.  Mova esses dois arquivos para dentro da pasta `cookies/`.

Ao final, sua pasta `cookies/` **deve conter os 3 arquivos**: `cookies.json`, `local_storage.json` e `session_storage.json`.

---

## 3. Como Usar

1.  **Liste os Vídeos:** Abra o arquivo `fathom_calls.json` e adicione os objetos JSON dos vídeos que você deseja processar. Mantenha o formato de um array de objetos, onde cada objeto deve ter `id`, `url` e `title`.

    **Exemplo de formato para `fathom_calls.json`:**
    ```json
    [
      {
        "id": "342446955",
        "url": "https://fathom.video/calls/342446955",
        "title": "Reunião de Alinhamento Semanal"
      },
      {
        "id": "123456789",
        "url": "https://fathom.video/calls/123456789",
        "title": "Demonstração para Cliente Importante"
      }
    ]
    ```

2.  **Execute o Script:**
    
    **Para processamento completo (áudio + transcrição + estrutura unificada):**
    ```bash
    python fathom_batch_processor.py
    ```
    
    **Para baixar apenas o HTML das páginas:**
    ```bash
    python download_html.py
    ```

3.  **Acompanhe o Progresso:** O script exibirá uma barra de progresso geral e barras individuais para cada conversão de áudio.

## 4. Arquivos Gerados

### 🆕 **Nova Estrutura Organizada por Vídeo:**

O sistema agora organiza automaticamente os arquivos em pastas individuais para cada vídeo, mantendo apenas o arquivo principal `_unified.json` na raiz para fácil acesso:

```
downloads_batch/
├── {título}_final.json (arquivo principal - fica na raiz)
└── {título}/
    ├── {título}_1.75x.mp3
    ├── {título}_transcript.txt
    ├── {título}_speakers.json
    ├── {título}_speakers.txt
    ├── {título}_transcript_details.json
    ├── {título}_metadata.json
    ├── {título}_summary.txt
    ├── {título}_fathom_transcript.json
    └── {título}_fathom_transcript.txt
```

### **Migração Automática:**
- O sistema **migra automaticamente** arquivos existentes para a nova estrutura
- Arquivos antigos são movidos para suas respectivas pastas sem perder dados
- O processo é executado automaticamente na primeira vez que você rodar o script

### Processamento de Áudio e Transcrição:

#### Arquivo Principal (Raiz):
-   `{título}_final.json` - **Estrutura padronizada** que combina:
    - Metadados do Fathom (ID, URL, título, data, duração, host, participantes)
    - Transcrição processada do AssemblyAI em português
    - Mapeamento automático de speakers (IDs → nomes reais)
    - Detecção automática de perguntas na conversa
    - Summary estruturado com purpose, key_takeaways, topics, next_steps
    - Formato pronto para análise de dados e integração com outras ferramentas

#### Pasta Individual do Vídeo:

**Arquivos de Áudio:**
-   `{título}_1.75x.mp3` - Áudio acelerado em 1.75x (otimizado para qualidade)

**Transcrição AssemblyAI:**
-   `{título}_transcript.txt` - Transcrição completa em português
-   `{título}_speakers.json` - Dados estruturados de speakers com timestamps
-   `{título}_speakers.txt` - Análise de speakers formatada para leitura
-   `{título}_transcript_details.json` - Log de diagnóstico da API

**Metadados e Estruturas:**
-   `{título}_metadata.json` - Metadados completos extraídos do HTML
-   `{título}_summary.txt` - Resumo formatado da call

**Transcrição Original do Fathom:**
-   `{título}_fathom_transcript.json` - Transcrição original extraída do HTML
-   `{título}_fathom_transcript.txt` - Transcrição original formatada
    - Preserva o texto original em inglês do Fathom
    - Mantém speakers com nomes reais (ex: "Richard White", "Susannah DuRant")
    - Inclui cue IDs originais para referência

### Download de HTML (`html_pages/`):
-   `{título}.html` - HTML completo da página do Fathom (salvo automaticamente durante o processamento)

## 5. Estrutura da Saída Unificada

A nova funcionalidade gera um arquivo `_unified.json` com a seguinte estrutura padronizada:

```json
{
  "id": "342446955",
  "url": "https://fathom.video/calls/342446955",
  "share_url": "https://fathom.video/share/...",
  "title": "Fathom Demo",
  "date": "Sep 16, 2021",
  "date_formatted": "2021-09-16",
  "duration": "8 mins",
  "host_name": "Guilherme Vieira",
  "company_domain": "gmail.com",
  "participants": [
    {
      "speaker_id": "A",
      "name": "Richard White",
      "is_host": false
    },
    {
      "speaker_id": "B", 
      "name": "Susannah DuRant",
      "is_host": false
    }
  ],
  "summary": {
    "purpose": "Demo e apresentação do produto",
    "key_takeaways": [...],
    "topics": [...],
    "next_steps": [...]
  },
  "transcript_text": "Speaker A: Texto da transcrição...",
  "questions": [
    {
      "speaker_id": "A",
      "question": "Como funciona o sistema de highlights?"
    }
  ],
  "extracted_at": "2025-07-03T18:25:09.205018Z",
  "status": "extracted"
}
```

## 6. Benefícios da Nova Versão

### 📁 **Organização Inteligente:**
- **Pastas individuais** para cada vídeo mantêm arquivos organizados
- **Arquivo principal** `_final.json` na raiz para acesso rápido
- **Migração automática** de arquivos existentes sem perda de dados
- **Estrutura limpa** facilita navegação e backup

### 🎯 **Dados Estruturados:**
- **Formato padronizado** para análise de dados
- **Mapeamento automático** de speakers (IDs do AssemblyAI → nomes reais do Fathom)
- **Detecção inteligente** de perguntas na conversa
- **Metadados completos** extraídos automaticamente

### 📊 **Duas Fontes de Transcrição:**
- **AssemblyAI**: Processada, traduzida para português, com speaker labels
- **Fathom Original**: Preservada em inglês com nomes reais e cue IDs

### 🚀 **Pronto para Análise:**
- Estrutura JSON compatível com ferramentas de análise
- Summary automático com insights estruturados
- Timestamps e confiança para cada utterance
- Formato ideal para integração com dashboards e relatórios

---

## 7. Solução de Problemas

O progresso fica salvo em `processing_progress.json`. Para reprocessar um vídeo, basta removê-lo da lista de `processed_ids` neste arquivo. 