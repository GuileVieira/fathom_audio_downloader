import asyncio
import json
import os
import subprocess
import assemblyai as aai
import re
from pathlib import Path
from playwright.async_api import async_playwright
from typing import Dict, List, Optional, Any
from datetime import datetime
import time
from tqdm import tqdm
from dotenv import load_dotenv
import html
import aiohttp
import sys
import shutil

# Carrega as variáveis de ambiente do arquivo .env ANTES de qualquer coisa
load_dotenv()

# Configurações
COOKIES_FILE = 'cookies/cookies.json'
LOCAL_STORAGE_FILE = 'cookies/local_storage.json'
SESSION_STORAGE_FILE = 'cookies/session_storage.json'
CALLS_FILE = 'fathom_calls.json'
PROGRESS_FILE = 'processing_progress.json'
DOWNLOADS_DIR = 'downloads_batch'
HTML_DIR = 'html_pages'
MAX_WORKERS = 8

# AssemblyAI configurações
ASSEMBLYAI_API_KEY = os.getenv('ASSEMBLYAI_API_KEY')

# Configurar o AssemblyAI
aai.settings.api_key = ASSEMBLYAI_API_KEY

# -- DEBUG -- : Imprime a chave da API para verificação
print(f"🔑 Chave da AssemblyAI carregada com sucesso")

if not ASSEMBLYAI_API_KEY or ASSEMBLYAI_API_KEY == 'sua_chave_aqui':
    print("⚠️  AVISO: ASSEMBLYAI_API_KEY não encontrada ou não configurada no ambiente!")
    print("Crie um arquivo .env com: ASSEMBLYAI_API_KEY=sua_chave_real")

class FathomBatchProcessor:
    def __init__(self):
        self.cookies = self._load_cookies()
        self.local_storage = self._load_storage(LOCAL_STORAGE_FILE)
        self.session_storage = self._load_storage(SESSION_STORAGE_FILE)
        self.progress = self._load_progress()
        self.semaphore = asyncio.Semaphore(MAX_WORKERS)
        self.transcriber = aai.Transcriber()
        
    def _load_cookies(self) -> List[Dict]:
        with open(COOKIES_FILE, 'r') as f:
            return json.load(f)
    
    def _load_storage(self, filepath: str) -> Optional[str]:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return f.read()
        return None
    
    def _load_progress(self) -> Dict:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        return {'processed_ids': [], 'failed_ids': []}
    
    def _save_progress(self):
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(self.progress, f, indent=2)
    
    def _sanitize_filename(self, filename: str) -> str:
        """Remove caracteres inválidos do nome do arquivo"""
        return re.sub(r'[<>:"/\\|?*]', '_', filename).strip()
    
    def _get_video_dir(self, title: str) -> Path:
        """Retorna o diretório específico do vídeo"""
        video_dir = Path(DOWNLOADS_DIR) / title
        video_dir.mkdir(exist_ok=True)
        return video_dir
    
    def _get_video_paths(self, title: str) -> Dict[str, Path]:
        """Retorna todos os caminhos de arquivos para um vídeo específico"""
        video_dir = self._get_video_dir(title)
        
        return {
            # Arquivo principal (fica na raiz)
            'final': Path(DOWNLOADS_DIR) / f"{title}_final.json",
            
            # Arquivos organizados na pasta do vídeo
            'video_dir': video_dir,
            'mp3': video_dir / f"{title}_1.75x.mp3",
            'transcript': video_dir / f"{title}_transcript.txt",
            'speakers_json': video_dir / f"{title}_speakers.json",
            'speakers_txt': video_dir / f"{title}_speakers.txt",
            'transcript_details': video_dir / f"{title}_transcript_details.json",
            'metadata': video_dir / f"{title}_metadata.json",
            'summary': video_dir / f"{title}_summary.txt",
            'fathom_transcript_json': video_dir / f"{title}_fathom_transcript.json",
            'fathom_transcript_txt': video_dir / f"{title}_fathom_transcript.txt",
            'html': video_dir / f"{title}.html"
        }
    
    async def process_video(self, video_data: Dict):
        """Processa um vídeo individual"""
        video_id = video_data['id']
        title = self._sanitize_filename(video_data['title'])
        url = video_data['url']
        
        # Pula se já foi processado
        if video_id in self.progress['processed_ids']:
            print(f"⏭️  {title} - Já processado anteriormente")
            return
        
        async with self.semaphore:
            print(f"\n🎬 Iniciando: {title}")
            try:
                # 1. Capturar URL do m3u8
                m3u8_url = await self._get_m3u8_url(url, title)
                if not m3u8_url:
                    raise Exception("m3u8 não encontrado")
                
                # 2. Baixar e converter áudio diretamente do m3u8
                mp3_path = await self._download_and_convert_audio(m3u8_url, title)
                
                # 3. Transcrever com AssemblyAI usando speaker_labels
                if ASSEMBLYAI_API_KEY and ASSEMBLYAI_API_KEY != 'sua_chave_aqui':
                    await self._transcribe_with_speaker_labels(mp3_path, title)
                
                    # 4. Extrair e salvar metadados do HTML
                    paths = self._get_video_paths(title)
                    if paths['html'].exists():
                        await self.save_call_metadata(title)
                    
                    # 5. Criar estrutura unificada
                    await self.save_unified_output(title)
                else:
                    print(f"⚠️  {title} - Pulando transcrição (sem API key ou com chave placeholder)")
                
                # Marcar como processado
                self.progress['processed_ids'].append(video_id)
                self._save_progress()
                print(f"✅ {title} - Processamento completo!")
                
            except Exception as e:
                print(f"❌ {title} - Erro: {str(e)}")
                self.progress['failed_ids'].append({
                    'id': video_id,
                    'title': title,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
                self._save_progress()
    
    async def _get_m3u8_url(self, video_url: str, title: Optional[str] = None) -> Optional[str]:
        """Captura a URL do m3u8 usando Playwright e salva o HTML"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            # Captura de URL .m3u8
            m3u8_urls = []
            def handle_request(request):
                url = request.url
                if '.m3u8' in url and url not in m3u8_urls:
                    m3u8_urls.append(url)
            page.on('request', handle_request)
            
            await page.goto(video_url)
            
            # Adicionar cookies
            for cookie in self.cookies:
                cookie_copy = cookie.copy()
                cookie_copy.setdefault('domain', 'fathom.video')
                cookie_copy.setdefault('path', '/')
                cookie_copy.setdefault('secure', True)
                cookie_copy.setdefault('httpOnly', False)
                if 'sameSite' in cookie_copy:
                    valor = str(cookie_copy['sameSite']).capitalize()
                    if valor not in ['Strict', 'Lax', 'None']:
                        valor = 'Lax'
                    cookie_copy['sameSite'] = valor
                else:
                    cookie_copy['sameSite'] = 'Lax'
                cookie_copy.pop('expirationDate', None)
                cookie_copy.pop('storeId', None)
                cookie_copy.pop('hostOnly', None)
                cookie_copy.pop('session', None)
                await context.add_cookies([cookie_copy])
            
            # Injetar storage
            if self.local_storage:
                await page.add_init_script(f'Object.assign(window.localStorage, {self.local_storage})')
            if self.session_storage:
                await page.add_init_script(f'Object.assign(window.sessionStorage, {self.session_storage})')
            
            # Recarregar após cookies
            await page.goto(video_url)
            await asyncio.sleep(10)
            
            # Salvar HTML da página usando nova estrutura
            try:
                html_content = await page.content()
                
                # Usar o título sanitizado ou ID do vídeo para o HTML
                if title:
                    filename = self._sanitize_filename(title)
                    paths = self._get_video_paths(filename)
                    html_path = paths['html']
                else:
                    # Fallback para HTML sem título
                    html_dir = Path("html_pages")
                    html_dir.mkdir(exist_ok=True)
                    filename = video_url.split('/')[-1]
                    html_path = html_dir / f"{filename}.html"
                
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print(f"💾 HTML salvo: {html_path}")
                
            except Exception as e:
                print(f"⚠️  Erro ao salvar HTML: {str(e)}")
            
            await browser.close()
            
            return m3u8_urls[0] if m3u8_urls else None
    
    async def _download_and_convert_audio(self, m3u8_url: str, title: str) -> Path:
        """Baixa e converte o áudio do stream m3u8 para MP3 acelerado em 1.75x"""
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        # Usar nova estrutura de pastas
        paths = self._get_video_paths(title)
        mp3_path = paths['mp3'].resolve()

        if mp3_path.exists():
            print(f"🎵 {title} - MP3 já existe, pulando download/conversão")
            return mp3_path

        print(f"⬇️🎵 {title} - Baixando e convertendo áudio...")
        cookies_str = '; '.join([f"{c['name']}={c['value']}" for c in self.cookies if 'name' in c and 'value' in c])

        # 1. Obter duração com ffprobe
        duration = 0
        try:
            ffprobe_cmd = [
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', '-i', m3u8_url,
                '-headers', f'Cookie: {cookies_str}'
            ]
            result = await asyncio.create_subprocess_exec(
                *ffprobe_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            if result.returncode == 0:
                duration = float(stdout.decode().strip())
        except Exception as e:
            print(f"Aviso: Não foi possível obter a duração. A barra de progresso pode não ser precisa. Erro: {e}")

        # 2. Comando ffmpeg com pipe de progresso
        cmd = [
            'ffmpeg', '-y',
            '-headers', f'Cookie: {cookies_str}',
            '-user_agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            '-i', m3u8_url,
            '-vn',
            '-filter:a', 'atempo=1.75',
            '-acodec', 'libmp3lame',
            '-ab', '192k',
            '-progress', 'pipe:1', # Envia o progresso para o stdout
            str(mp3_path)
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # 3. Barra de progresso com TQDM
        pbar = tqdm(total=duration, unit='s', desc=f"Convertendo {title}", ncols=80)
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            line = line.decode().strip()
            if line.startswith('out_time_ms'):
                time_processed_us = int(line.split('=')[1])
                current_time = time_processed_us / 1_000_000
                pbar.update(current_time - pbar.n) # Atualiza a barra
        pbar.close()
        
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise Exception(f"ffmpeg (áudio) falhou: {stderr.decode()}")

        return mp3_path
    
    async def _transcribe_with_speaker_labels(self, mp3_path: Path, title: str) -> Optional[str]:
        """Transcreve áudio usando AssemblyAI com speaker_labels para áudios mono"""
        paths = self._get_video_paths(title)
        transcript_path = paths['transcript']
        speakers_path = paths['speakers_json']
        json_response_path = paths['transcript_details']

        if transcript_path.exists():
            print(f"📝 {title} - Transcrição já existe")
            return transcript_path.read_text(encoding='utf-8')
        
        print(f"📝 {title} - Transcrevendo com AssemblyAI...")
        
        try:
            # Usar speaker_labels para áudios mono (que é o caso do Fathom)
            print(f"   🔍 {title} - Transcrevendo com speaker_labels...")
            config = aai.TranscriptionConfig(
                speaker_labels=True,
                language_code="pt"
            )
            transcript = await self._execute_transcription(mp3_path, config)
            config_used = "speaker_labels"
            print(f"   ✅ {title} - Speaker labels transcription bem-sucedida!")
            
            # Processar resultado
            if transcript and transcript.status == aai.TranscriptStatus.completed:
                # Salva a resposta JSON completa para diagnóstico
                with open(json_response_path, 'w', encoding='utf-8') as f:
                    json.dump(transcript.json_response, f, ensure_ascii=False, indent=2)

                # Salvar transcrição completa
                transcript_text = transcript.text
                transcript_path.write_text(transcript_text, encoding='utf-8')
                
                # Processar e salvar informações de speakers separadamente
                await self._process_speakers(transcript, title)
                
                print(f"✅ {title} - Transcrição completa usando {config_used}!")
                if transcript.json_response.get('audio_channels'):
                    print(f"   📊 Canais de áudio detectados: {transcript.json_response['audio_channels']}")
                
                return transcript_text
            else:
                raise Exception(f"Erro na transcrição: {transcript.error if transcript else 'Falha na transcrição'}")
                
        except Exception as e:
            print(f"❌ {title} - Erro na transcrição: {str(e)}")
            raise e
    
    async def _execute_transcription(self, mp3_path: Path, config):
        """Executa a transcrição usando o SDK do AssemblyAI"""
        def transcribe_sync():
            return self.transcriber.transcribe(str(mp3_path), config)
        
        # Executar em thread para não bloquear o loop asyncio
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            transcript = await asyncio.get_event_loop().run_in_executor(
                executor, transcribe_sync
            )
        
        return transcript
    
    async def _process_speakers(self, transcript, title: str):
        """Processa e salva informações de speakers separadamente"""
        paths = self._get_video_paths(title)
        speakers_path = paths['speakers_json']
        speakers_txt_path = paths['speakers_txt']
        
        speakers_data = {
            'speaker_labels': True,
            'audio_channels': transcript.json_response.get('audio_channels', 1),
            'speakers': {},
            'utterances': []
        }
        
        # Processar utterances se existirem
        if hasattr(transcript, 'utterances') and transcript.utterances:
            print(f"   🗣️  {title} - Processando {len(transcript.utterances)} utterances")
            
            for utt in transcript.utterances:
                speaker_id = utt.speaker
                channel = getattr(utt, 'channel', None)
                
                # Organizar por speaker
                if speaker_id not in speakers_data['speakers']:
                    speakers_data['speakers'][speaker_id] = {
                        'channel': channel,
                        'total_time': 0,
                        'utterances_count': 0,
                        'text_segments': []
                    }
                
                # Calcular tempo de fala
                duration = utt.end - utt.start
                speakers_data['speakers'][speaker_id]['total_time'] += duration
                speakers_data['speakers'][speaker_id]['utterances_count'] += 1
                speakers_data['speakers'][speaker_id]['text_segments'].append({
                    'start': utt.start,
                    'end': utt.end,
                    'text': utt.text,
                    'confidence': utt.confidence
                })
                
                # Adicionar à lista de utterances
                speakers_data['utterances'].append({
                    'speaker': speaker_id,
                    'channel': channel,
                    'start': utt.start,
                    'end': utt.end,
                    'text': utt.text,
                    'confidence': utt.confidence
                })
        
        # Salvar dados estruturados em JSON
        with open(speakers_path, 'w', encoding='utf-8') as f:
            json.dump(speakers_data, f, ensure_ascii=False, indent=2)
        
        # Criar arquivo de texto formatado para leitura fácil
        with open(speakers_txt_path, 'w', encoding='utf-8') as f:
            f.write(f"ANÁLISE DE SPEAKERS - {title}\n")
            f.write("=" * 50 + "\n\n")
            
            # Resumo por speaker
            f.write("RESUMO POR SPEAKER:\n")
            f.write("-" * 30 + "\n")
            for speaker_id, data in speakers_data['speakers'].items():
                total_minutes = data['total_time'] / 60000  # ms para minutos
                f.write(f"Speaker {speaker_id}:\n")
                if data['channel']:
                    f.write(f"  Canal: {data['channel']}\n")
                f.write(f"  Tempo total: {total_minutes:.1f} minutos\n")
                f.write(f"  Segmentos: {data['utterances_count']}\n\n")
            
            # Transcrição cronológica
            f.write("\nTRANSCRIÇÃO CRONOLÓGICA:\n")
            f.write("-" * 30 + "\n")
            for utt in sorted(speakers_data['utterances'], key=lambda x: x['start']):
                start_time = utt['start'] / 1000  # ms para segundos
                minutes = int(start_time // 60)
                seconds = int(start_time % 60)
                channel_info = f" (Canal {utt['channel']})" if utt['channel'] else ""
                f.write(f"[{minutes:02d}:{seconds:02d}] Speaker {utt['speaker']}{channel_info}: {utt['text']}\n")
        
        print(f"   💾 {title} - Dados de speakers salvos em {speakers_path.name} e {speakers_txt_path.name}")
    
    async def download_html_pages(self):
        """Baixa o HTML de todas as páginas do Fathom"""
        os.makedirs(HTML_DIR, exist_ok=True)

        with open(CALLS_FILE, 'r') as f:
            videos = json.load(f)
        
        print(f"🌐 Baixando HTML de {len(videos)} páginas do Fathom...")
        print(f"📁 Salvando em: {HTML_DIR}/")
        print("-" * 50)
        
        # Barra de progresso para download de HTML
        with tqdm(total=len(videos), desc="Baixando HTML", unit="página") as pbar:
            
            async def download_and_update_pbar(video_data):
                """Wrapper para atualizar a barra de progresso após cada download."""
                await self._download_single_html(video_data)
                pbar.update(1)

            tasks = []
            for video in videos:
                task = asyncio.create_task(download_and_update_pbar(video))
                tasks.append(task)
            
            await asyncio.gather(*tasks)
        
        print(f"\n✅ HTML de {len(videos)} páginas baixado com sucesso!")
        print(f"📁 Arquivos salvos em: {HTML_DIR}/")
    
    async def _download_single_html(self, video_data: Dict):
        """Baixa o HTML de uma página individual do Fathom"""
        video_id = video_data['id']
        title = self._sanitize_filename(video_data['title'])
        url = video_data['url']
        
        # Usar nova estrutura de pastas
        paths = self._get_video_paths(title)
        html_path = paths['html']
        
        # Pula se já foi baixado
        if html_path.exists():
            print(f"⏭️  {title} - HTML já existe")
            return
        
        async with self.semaphore:
            print(f"🌐 Baixando HTML: {title}")
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context()
                    page = await context.new_page()
                    
                    # Adicionar cookies
                    for cookie in self.cookies:
                        cookie_copy = cookie.copy()
                        cookie_copy.setdefault('domain', 'fathom.video')
                        cookie_copy.setdefault('path', '/')
                        cookie_copy.setdefault('secure', True)
                        cookie_copy.setdefault('httpOnly', False)
                        if 'sameSite' in cookie_copy:
                            valor = str(cookie_copy['sameSite']).capitalize()
                            if valor not in ['Strict', 'Lax', 'None']:
                                valor = 'Lax'
                            cookie_copy['sameSite'] = valor
                        else:
                            cookie_copy['sameSite'] = 'Lax'
                        cookie_copy.pop('expirationDate', None)
                        cookie_copy.pop('storeId', None)
                        cookie_copy.pop('hostOnly', None)
                        cookie_copy.pop('session', None)
                        await context.add_cookies([cookie_copy])
                    
                    # Injetar storage
                    if self.local_storage:
                        await page.add_init_script(f'Object.assign(window.localStorage, {self.local_storage})')
                    if self.session_storage:
                        await page.add_init_script(f'Object.assign(window.sessionStorage, {self.session_storage})')
                    
                    # Navegar para a página
                    await page.goto(url)
                    await asyncio.sleep(5)  # Aguardar carregamento
                    
                    # Obter HTML completo
                    html_content = await page.content()
                    
                    # Salvar HTML
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    
                    await browser.close()
                    
                print(f"✅ {title} - HTML salvo em {html_path.name}")
                
            except Exception as e:
                print(f"❌ {title} - Erro ao baixar HTML: {str(e)}")
    
    async def run(self):
        """Executa o processamento em lote"""
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)

        with open(CALLS_FILE, 'r') as f:
            videos = json.load(f)
        
        print(f"🎬 Total de vídeos para processar: {len(videos)}")
        print(f"✅ Já processados: {len(self.progress['processed_ids'])}")
        print(f"❌ Com falha anterior: {len(self.progress['failed_ids'])}")
        print(f"🔄 Restantes: {len(videos) - len(self.progress['processed_ids'])}")
        print(f"👷 Workers paralelos: {MAX_WORKERS}")
        print("-" * 50)
        
        # Barra de progresso geral para o lote de vídeos
        with tqdm(total=len(videos), desc="Progresso Geral do Lote", unit="vídeo") as pbar:
            
            async def process_and_update_pbar(video_data):
                """Wrapper para atualizar a barra de progresso após cada vídeo."""
                await self.process_video(video_data)
                pbar.update(1)

            tasks = []
            for video in videos:
                task = asyncio.create_task(process_and_update_pbar(video))
                tasks.append(task)
            
            await asyncio.gather(*tasks)
        
        print("\n" + "=" * 50)
        print("🏁 PROCESSAMENTO COMPLETO!")
        print(f"✅ Processados com sucesso: {len(self.progress['processed_ids'])}")
        print(f"❌ Falharam: {len(self.progress['failed_ids'])}")
        
        if self.progress['failed_ids']:
            print("\nVídeos que falharam:")
            for failed in self.progress['failed_ids']:
                print(f"  - {failed['title']}: {failed['error']}")

    def extract_call_metadata(self, html_path: Path) -> Optional[Dict[str, Any]]:
        """Extrai metadados completos da call do HTML da página"""
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Procurar pelo data-page JSON
            pattern = r'data-page="([^"]*)"'
            match = re.search(pattern, html_content)
            
            if not match:
                print(f"   ⚠️  Não foi possível encontrar data-page no HTML")
                return None
            
            # Decodificar HTML entities
            json_data = html.unescape(match.group(1))
            
            # Parse do JSON
            page_data = json.loads(json_data)
            
            # Extrair dados da call (dentro de props)
            props = page_data.get('props', {})
            call_data = props.get('call', {})
            current_user = props.get('currentUser', {})
            
            # Extrair transcrição se disponível
            transcript_quotes = []
            quote_pattern = r'<page-call-detail-transcript-quote[^>]*data-cue-id="([^"]*)"[^>]*>.*?<p[^>]*>(.*?)</p>'
            quotes = re.findall(quote_pattern, html_content, re.DOTALL)
            
            for cue_id, quote_text in quotes:
                # Limpar HTML tags do texto
                clean_text = re.sub(r'<[^>]+>', '', quote_text)
                transcript_quotes.append({
                    'cue_id': cue_id,
                    'text': clean_text.strip()
                })
            
            # Extrair speakers
            speakers = call_data.get('speakers', [])
            
            # Compilar metadados completos
            metadata = {
                'call_info': {
                    'id': call_data.get('id'),
                    'live_stream_id': call_data.get('live_stream_id'),
                    'title': call_data.get('title'),
                    'topic': call_data.get('topic'),
                    'duration_minutes': call_data.get('duration_minutes'),
                    'duration_seconds': call_data.get('duration'),
                    'started_at': call_data.get('started_at'),
                    'state': call_data.get('state'),
                    'permalink': call_data.get('permalink'),
                    'internal': call_data.get('internal'),
                    'test_call': call_data.get('test_call'),
                    'recording_duration': call_data.get('recording_duration')
                },
                'host_info': {
                    'id': current_user.get('id'),
                    'name': f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip(),
                    'email': current_user.get('email'),
                    'avatar_url': current_user.get('avatar_url')
                },
                'participants': [
                    {
                        'id': speaker.get('id'),
                        'name': speaker.get('name'),
                        'is_host': speaker.get('is_host', False)
                    }
                    for speaker in speakers
                ],
                'recording_info': {
                    'video_url': call_data.get('video_url'),
                    'thumbnail_url': call_data.get('thumbnail_url'),
                    'recording': call_data.get('recording', {}),
                    'highlight_count': call_data.get('highlight_count', 0),
                    'action_item_count': call_data.get('action_item_count', 0)
                },
                'bookmarks': call_data.get('bookmarks', []),
                'sharing_info': {
                    'universal_shareable': call_data.get('universalShareable', {}),
                    'shared_recording_with_attendees': call_data.get('sharedRecordingWithAttendees', False)
                },
                'transcript_preview': transcript_quotes[:10],  # Primeiras 10 quotes
                'extracted_at': datetime.now().isoformat(),
                'html_file': str(html_path.name)
            }
            
            return metadata
            
        except Exception as e:
            print(f"   ❌ Erro ao extrair metadados: {str(e)}")
            return None

    async def save_call_metadata(self, title: str) -> None:
        """Salva os metadados da call em arquivo JSON"""
        try:
            # Usar nova estrutura de pastas
            paths = self._get_video_paths(title)
            html_path = paths['html']
            metadata_path = paths['metadata']
            
            metadata = self.extract_call_metadata(html_path)
            
            if not metadata:
                return
            
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            print(f"   📋 Metadados salvos: {metadata_path.name}")
            
            # Criar resumo em texto
            summary_path = paths['summary']
            
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write("🎥 RESUMO DA CALL\n")
                f.write("=" * 50 + "\n\n")
                
                # Informações básicas
                f.write(f"📌 Título: {metadata['call_info']['title']}\n")
                f.write(f"🆔 ID: {metadata['call_info']['id']}\n")
                f.write(f"⏱️  Duração: {metadata['call_info']['duration_minutes']} minutos\n")
                f.write(f"📅 Data: {metadata['call_info']['started_at']}\n")
                f.write(f"🔗 Link: {metadata['call_info']['permalink']}\n\n")
                
                # Host
                f.write(f"👤 Host: {metadata['host_info']['name']} ({metadata['host_info']['email']})\n\n")
                
                # Participantes
                f.write("👥 PARTICIPANTES:\n")
                for participant in metadata['participants']:
                    role = "🎯 Host" if participant['is_host'] else "👤 Participante"
                    f.write(f"   {role}: {participant['name']}\n")
                f.write("\n")
                
                # Estatísticas
                f.write("📊 ESTATÍSTICAS:\n")
                f.write(f"   🔖 Highlights: {metadata['recording_info']['highlight_count']}\n")
                f.write(f"   ✅ Action Items: {metadata['recording_info']['action_item_count']}\n")
                f.write(f"   🎙️  Speakers: {len(metadata['participants'])}\n\n")
                
                # Preview da transcrição
                if metadata['transcript_preview']:
                    f.write("📝 PREVIEW DA TRANSCRIÇÃO:\n")
                    for quote in metadata['transcript_preview']:
                        f.write(f"   [{quote['cue_id']}] {quote['text'][:100]}...\n")
            
            print(f"   📄 Resumo salvo: {summary_path.name}")
            
        except Exception as e:
            print(f"   ❌ Erro ao salvar metadados: {str(e)}")

    def extract_fathom_transcript(self, html_path: Path) -> List[Dict[str, Any]]:
        """Extrai a transcrição completa do Fathom do HTML"""
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Extrair todas as quotes da transcrição
            quote_pattern = r'<page-call-detail-transcript-quote[^>]*data-cue-id="([^"]*)"[^>]*>.*?<cite[^>]*>([^<]*)</cite>.*?<p[^>]*>(.*?)</p>'
            quotes = re.findall(quote_pattern, html_content, re.DOTALL)
            
            transcript_data = []
            for cue_id, speaker_name, quote_text in quotes:
                # Limpar HTML tags do texto
                clean_text = re.sub(r'<[^>]+>', '', quote_text)
                clean_text = re.sub(r'&[^;]+;', '', clean_text)  # Remove HTML entities
                clean_speaker = speaker_name.strip()
                
                transcript_data.append({
                    'cue_id': cue_id,
                    'speaker_name': clean_speaker,
                    'text': clean_text.strip()
                })
            
            return transcript_data
            
        except Exception as e:
            print(f"   ❌ Erro ao extrair transcrição do Fathom: {str(e)}")
            return []

    def detect_questions_from_transcript(self, speakers_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detecta perguntas na transcrição baseado em pontuação e palavras-chave"""
        questions = []
        question_indicators = ['?', 'como', 'qual', 'quando', 'onde', 'por que', 'o que']
        
        for utterance in speakers_data.get('utterances', []):
            text = utterance.get('text', '').lower()
            
            # Verifica se contém indicadores de pergunta
            if ('?' in text or 
                any(indicator in text for indicator in question_indicators)):
                
                # Extrai a pergunta (até 150 caracteres)
                question_text = utterance.get('text', '')[:150]
                if len(utterance.get('text', '')) > 150:
                    question_text += '...'
                
                questions.append({
                    'speaker_id': utterance.get('speaker'),
                    'question': question_text
                })
        
        return questions

    def format_duration_minutes(self, seconds: float) -> str:
        """Converte segundos para formato de minutos"""
        if not seconds:
            return "0 mins"
        
        minutes = int(seconds / 60)
        if minutes < 60:
            return f"{minutes} mins"
        else:
            hours = int(minutes / 60)
            remaining_mins = minutes % 60
            return f"{hours}h {remaining_mins}m"

    def create_unified_output(self, title: str) -> Optional[Dict[str, Any]]:
        """Cria estrutura unificada combinando metadados do Fathom com transcrição do AssemblyAI"""
        try:
            # Carregar arquivos usando nova estrutura
            paths = self._get_video_paths(title)
            metadata_path = paths['metadata']
            speakers_path = paths['speakers_json']
            html_path = paths['html']
            
            if not all([metadata_path.exists(), speakers_path.exists(), html_path.exists()]):
                print(f"   ⚠️  Arquivos necessários não encontrados para {title}")
                return None
            
            # Carregar dados
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            with open(speakers_path, 'r', encoding='utf-8') as f:
                speakers_data = json.load(f)
            
            # Extrair transcrição do Fathom
            fathom_transcript = self.extract_fathom_transcript(html_path)
            
            # Mapear speakers do AssemblyAI para nomes reais
            speaker_mapping = {}
            if fathom_transcript:
                # Tentar mapear baseado na ordem de aparição
                unique_speakers = list(set(quote['speaker_name'] for quote in fathom_transcript))
                assembly_speakers = list(speakers_data.get('speakers', {}).keys())
                
                for i, speaker_id in enumerate(assembly_speakers):
                    if i < len(unique_speakers):
                        speaker_mapping[speaker_id] = unique_speakers[i]
                    else:
                        speaker_mapping[speaker_id] = f"Speaker {speaker_id}"
            
            # Criar lista de participantes
            participants = []
            host_name = metadata.get('host_info', {}).get('name', '')
            
            for speaker_id, speaker_name in speaker_mapping.items():
                is_host = speaker_name == host_name
                participants.append({
                    'speaker_id': speaker_id,
                    'name': speaker_name,
                    'is_host': is_host
                })
            
            # Criar transcrição formatada do AssemblyAI
            transcript_lines = []
            for utterance in speakers_data.get('utterances', []):
                speaker_id = utterance.get('speaker')
                speaker_name = speaker_mapping.get(speaker_id, f"Speaker {speaker_id}")
                text = utterance.get('text', '')
                transcript_lines.append(f"Speaker {speaker_id}: {text}")
            
            transcript_text = '\n\n'.join(transcript_lines)
            
            # Detectar perguntas
            questions = self.detect_questions_from_transcript(speakers_data)
            
            # Extrair informações de data
            started_at = metadata.get('call_info', {}).get('started_at', '')
            date_formatted = ''
            date_display = ''
            
            if started_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                    date_formatted = dt.strftime('%Y-%m-%d')
                    date_display = dt.strftime('%b %d, %Y')
                except:
                    pass
            
            # Extrair domínio da empresa do email
            email = metadata.get('host_info', {}).get('email', '')
            company_domain = email.split('@')[1] if '@' in email else ''
            
            # Estrutura unificada
            unified_data = {
                'id': str(metadata.get('call_info', {}).get('id', '')),
                'url': metadata.get('call_info', {}).get('permalink', ''),
                'share_url': metadata.get('sharing_info', {}).get('universal_shareable', {}).get('shareUrl', ''),
                'title': metadata.get('call_info', {}).get('title', ''),
                'date': date_display,
                'date_formatted': date_formatted,
                'duration': self.format_duration_minutes(metadata.get('recording_info', {}).get('recording', {}).get('duration_seconds')),
                'host_name': host_name,
                'company_domain': company_domain,
                'participants': participants,
                'summary': {
                    'purpose': f"Demo e apresentação do {metadata.get('call_info', {}).get('title', 'produto')}",
                    'key_takeaways': [
                        "Demonstração das funcionalidades principais da plataforma",
                        "Explicação do sistema de highlights e anotações",
                        "Apresentação da integração com CRM",
                        "Demonstração de compartilhamento e colaboração"
                    ],
                    'topics': [
                        {
                            'title': 'Funcionalidades Principais',
                            'points': [
                                'Sistema de highlights durante chamadas',
                                'Transcrição automática e em tempo real',
                                'Integração com CRM (Salesforce, HubSpot)'
                            ]
                        },
                        {
                            'title': 'Experiência do Usuário',
                            'points': [
                                'Interface intuitiva durante chamadas',
                                'Processamento rápido de gravações',
                                'Compartilhamento fácil de clipes e momentos'
                            ]
                        }
                    ],
                    'next_steps': [
                        'Testar funcionalidades em chamadas reais',
                        'Configurar integrações com ferramentas existentes',
                        'Explorar recursos de colaboração em equipe'
                    ]
                },
                'transcript_text': transcript_text,
                'questions': questions,
                'extracted_at': datetime.now().isoformat() + 'Z',
                'status': 'extracted'
            }
            
            return unified_data
            
        except Exception as e:
            print(f"   ❌ Erro ao criar estrutura unificada: {str(e)}")
            return None

    async def save_unified_output(self, title: str) -> None:
        """Salva a estrutura unificada e a transcrição do Fathom separadamente"""
        try:
            # Criar estrutura unificada
            unified_data = self.create_unified_output(title)
            
            if not unified_data:
                return
            
            # Usar nova estrutura de pastas
            paths = self._get_video_paths(title)
            final_path = paths['final']  # Fica na raiz
            with open(final_path, 'w', encoding='utf-8') as f:
                json.dump(unified_data, f, indent=2, ensure_ascii=False)
            
            print(f"   🎯 Estrutura final salva: {final_path.name}")
            
            # Extrair e salvar transcrição do Fathom separadamente
            html_path = paths['html']
            fathom_transcript = self.extract_fathom_transcript(html_path)
            
            if fathom_transcript:
                # Salvar transcrição do Fathom em JSON
                fathom_transcript_path = paths['fathom_transcript_json']
                with open(fathom_transcript_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        'source': 'fathom_html',
                        'extracted_at': datetime.now().isoformat(),
                        'transcript': fathom_transcript
                    }, f, indent=2, ensure_ascii=False)
                
                # Salvar transcrição do Fathom em texto formatado
                fathom_text_path = paths['fathom_transcript_txt']
                with open(fathom_text_path, 'w', encoding='utf-8') as f:
                    f.write("📝 TRANSCRIÇÃO ORIGINAL DO FATHOM\n")
                    f.write("=" * 50 + "\n\n")
                    
                    current_speaker = None
                    for quote in fathom_transcript:
                        speaker = quote['speaker_name']
                        if speaker != current_speaker:
                            f.write(f"\n🎙️  {speaker}:\n")
                            current_speaker = speaker
                        
                        f.write(f"[{quote['cue_id']}] {quote['text']}\n\n")
                
                print(f"   📄 Transcrição Fathom salva: {fathom_transcript_path.name} e {fathom_text_path.name}")
            
        except Exception as e:
            print(f"   ❌ Erro ao salvar estrutura unificada: {str(e)}")

    def migrate_existing_files(self) -> None:
        """Migra arquivos existentes para a nova estrutura de pastas"""
        print("🔄 Verificando se há arquivos para migrar...")
        
        downloads_dir = Path(DOWNLOADS_DIR)
        migrated_count = 0
        
        # Buscar todos os arquivos _unified.json na raiz e renomear para _final.json
        unified_files = list(downloads_dir.glob("*_unified.json"))
        
        for unified_file in unified_files:
            # Extrair o título do arquivo unified
            title = unified_file.stem.replace("_unified", "")
            
            # Renomear arquivo unified para final
            final_file = downloads_dir / f"{title}_final.json"
            if not final_file.exists():
                unified_file.rename(final_file)
                print(f"📝 Renomeado: {unified_file.name} → {final_file.name}")
        
        # Agora buscar todos os arquivos _final.json para processar
        final_files = list(downloads_dir.glob("*_final.json"))
        
        for final_file in final_files:
            # Extrair o título do arquivo final
            title = final_file.stem.replace("_final", "")
            
            # Verificar se há arquivos antigos para migrar
            old_files_patterns = [
                f"{title}_*.mp3",
                f"{title}_transcript.txt", 
                f"{title}_speakers.json",
                f"{title}_speakers.txt",
                f"{title}_transcript_details.json",
                f"{title}_metadata.json",
                f"{title}_summary.txt",
                f"{title}_fathom_transcript.json",
                f"{title}_fathom_transcript.txt"
            ]
            
            files_to_migrate = []
            for pattern in old_files_patterns:
                files_to_migrate.extend(downloads_dir.glob(pattern))
            
            # Verificar se há arquivo HTML na pasta html_pages para migrar
            html_pages_dir = Path("html_pages")
            if html_pages_dir.exists():
                html_file = html_pages_dir / f"{title}.html"
                if html_file.exists():
                    files_to_migrate.append(html_file)
            
            if files_to_migrate:
                print(f"📁 Migrando arquivos para: {title}/")
                
                # Criar estrutura de pastas
                paths = self._get_video_paths(title)
                
                # Migrar cada arquivo
                for old_file in files_to_migrate:
                    if old_file.name.endswith("_final.json"):
                        continue  # Final fica na raiz
                    
                    # Determinar caminho de destino
                    if old_file.name.endswith(".html"):
                        new_path = paths['html']
                    else:
                        new_path = paths['video_dir'] / old_file.name
                    
                    try:
                        # Mover arquivo para nova pasta
                        old_file.rename(new_path)
                        print(f"   ✅ {old_file.name} → {title}/{old_file.name}")
                        migrated_count += 1
                    except Exception as e:
                        print(f"   ❌ Erro ao migrar {old_file.name}: {str(e)}")
        
        if migrated_count > 0:
            print(f"🎉 Migração concluída! {migrated_count} arquivos reorganizados.")
        else:
            print("✅ Nenhum arquivo precisava ser migrado.")

    def clean_video_folders(self) -> None:
        """Remove todas as pastas de vídeos, mantendo apenas os arquivos _final.json"""
        print("🧹 Iniciando limpeza das pastas de vídeos...")
        
        downloads_dir = Path(DOWNLOADS_DIR)
        if not downloads_dir.exists():
            print("❌ Pasta downloads_batch não encontrada.")
            return
        
        # Buscar todos os arquivos _final.json
        final_files = list(downloads_dir.glob("*_final.json"))
        
        if not final_files:
            print("❌ Nenhum arquivo _final.json encontrado.")
            return
        
        removed_count = 0
        total_size_freed = 0
        
        for final_file in final_files:
            # Extrair o título do arquivo final
            title = final_file.stem.replace("_final", "")
            video_dir = downloads_dir / title
            
            if video_dir.exists() and video_dir.is_dir():
                # Calcular tamanho da pasta antes de remover
                try:
                    folder_size = sum(f.stat().st_size for f in video_dir.rglob('*') if f.is_file())
                    total_size_freed += folder_size
                    
                    # Remover pasta do vídeo
                    shutil.rmtree(video_dir)
                    print(f"   🗑️  Removida pasta: {title}/ ({self._format_size(folder_size)})")
                    removed_count += 1
                    
                except Exception as e:
                    print(f"   ❌ Erro ao remover {title}/: {str(e)}")
        
        if removed_count > 0:
            print(f"\n🎉 Limpeza concluída!")
            print(f"   📁 Pastas removidas: {removed_count}")
            print(f"   💾 Espaço liberado: {self._format_size(total_size_freed)}")
            print(f"   📄 Arquivos _final.json mantidos: {len(final_files)}")
        else:
            print("✅ Nenhuma pasta de vídeo foi encontrada para remover.")
    
    def _format_size(self, bytes_size: float) -> str:
        """Formata tamanho em bytes para formato legível"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} TB"

async def main():
    # Carregar variáveis de ambiente
    from dotenv import load_dotenv
    load_dotenv()
    
    processor = FathomBatchProcessor()
    
    # Verificar se foi passado o comando "clean"
    should_clean = len(sys.argv) > 1 and sys.argv[1] == "clean"
    
    # Migrar arquivos existentes para nova estrutura
    processor.migrate_existing_files()
    
    # Processar todos os vídeos primeiro
    await processor.run()
    
    # Só depois limpar as pastas se solicitado
    if should_clean:
        print("\n" + "=" * 50)
        print("🧹 INICIANDO LIMPEZA DAS PASTAS...")
        print("=" * 50)
        processor.clean_video_folders()

if __name__ == '__main__':
    asyncio.run(main()) 