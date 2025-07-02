# Fathom - Processador de Vídeos em Lote

Este projeto automatiza o download, conversão e transcrição de vídeos da plataforma Fathom em lote.

## Funcionalidades

-   **Processamento Paralelo:** Processa até 4 vídeos simultaneamente.
-   **Extração de Áudio:** Baixa e converte apenas o áudio dos vídeos para MP3, economizando tempo e espaço.
-   **Aceleração de Áudio:** Acelera automaticamente o áudio para 1.5x.
-   **Transcrição Automática:** Usa a API do AssemblyAI para transcrever os áudios.
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

2.  **Execute o Script:** Rode o processador em lote a partir do seu terminal:
    ```bash
    python fathom_batch_processor.py
    ```
3.  **Acompanhe o Progresso:** O script exibirá uma barra de progresso geral e barras individuais para cada conversão de áudio.

## 4. Arquivos Gerados

Todos os arquivos processados serão salvos na pasta `downloads_batch/`, organizados pelo título do vídeo:
-   `{título}_1.5x.mp3`
-   `{título}_transcript.txt`
-   `{título}_transcript_details.json` (log de diagnóstico da API)

O progresso fica salvo em `processing_progress.json`. Para reprocessar um vídeo, basta removê-lo da lista de `processed_ids` neste arquivo. 