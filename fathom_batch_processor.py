import asyncio
import json
import os
import subprocess
import assemblyai as aai
import re
from pathlib import Path
from playwright.async_api import async_playwright
from typing import Dict, List, Optional
from datetime import datetime
import time
from tqdm import tqdm
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env ANTES de qualquer coisa
load_dotenv()

# Configurações
COOKIES_FILE = 'cookies/cookies.json'
LOCAL_STORAGE_FILE = 'cookies/local_storage.json'
SESSION_STORAGE_FILE = 'cookies/session_storage.json'
CALLS_FILE = 'fathom_calls.json'
PROGRESS_FILE = 'processing_progress.json'
DOWNLOADS_DIR = 'downloads_batch'
MAX_WORKERS = 4

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
                m3u8_url = await self._get_m3u8_url(url)
                if not m3u8_url:
                    raise Exception("m3u8 não encontrado")
                
                # 2. Baixar e converter áudio diretamente do m3u8
                mp3_path = await self._download_and_convert_audio(m3u8_url, title)
                
                # 3. Transcrever com AssemblyAI usando Multichannel
                if ASSEMBLYAI_API_KEY and ASSEMBLYAI_API_KEY != 'sua_chave_aqui':
                    await self._transcribe_with_multichannel(mp3_path, title)
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
    
    async def _get_m3u8_url(self, video_url: str) -> Optional[str]:
        """Captura a URL do m3u8 usando Playwright"""
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
            
            await browser.close()
            
            return m3u8_urls[0] if m3u8_urls else None
    
    async def _download_and_convert_audio(self, m3u8_url: str, title: str) -> Path:
        """Baixa e converte o áudio do stream m3u8 para MP3 acelerado em 1.5x"""
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        # Usa caminho absoluto para garantir que o ffmpeg encontre o diretório
        mp3_path = Path(DOWNLOADS_DIR).resolve() / f"{title}_1.5x.mp3"

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
            '-filter:a', 'atempo=1.5',
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
    
    async def _transcribe_with_multichannel(self, mp3_path: Path, title: str) -> Optional[str]:
        """Transcreve áudio usando AssemblyAI com detecção automática de canais"""
        transcript_path = Path(DOWNLOADS_DIR) / f"{title}_transcript.txt"
        speakers_path = Path(DOWNLOADS_DIR) / f"{title}_speakers.json"
        json_response_path = Path(DOWNLOADS_DIR) / f"{title}_transcript_details.json"

        if transcript_path.exists():
            print(f"📝 {title} - Transcrição já existe")
            return transcript_path.read_text(encoding='utf-8')
        
        print(f"📝 {title} - Transcrevendo com AssemblyAI...")
        
        try:
            # Primeiro, tenta com multichannel (para áudios com canais separados)
            transcript = None
            config_used = None
            
            try:
                print(f"   🔍 {title} - Tentando transcrição multichannel...")
                config = aai.TranscriptionConfig(
                    multichannel=True,
                    language_code="pt"
                )
                transcript = await self._execute_transcription(mp3_path, config)
                config_used = "multichannel"
                print(f"   ✅ {title} - Multichannel transcription bem-sucedida!")
                
            except Exception as multichannel_error:
                print(f"   ⚠️  {title} - Multichannel falhou: {str(multichannel_error)}")
                print(f"   🔄 {title} - Tentando com speaker_labels...")
                
                # Se multichannel falhou, tenta com speaker_labels
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
        speakers_path = Path(DOWNLOADS_DIR) / f"{title}_speakers.json"
        speakers_txt_path = Path(DOWNLOADS_DIR) / f"{title}_speakers.txt"
        
        speakers_data = {
            'multichannel': transcript.json_response.get('multichannel', False),
            'audio_channels': transcript.json_response.get('audio_channels', 0),
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
            
            if speakers_data['multichannel']:
                f.write(f"🎙️  MULTICHANNEL: {speakers_data['audio_channels']} canais detectados\n\n")
            
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

async def main():
    # Carregar variáveis de ambiente
    from dotenv import load_dotenv
    load_dotenv()
    
    processor = FathomBatchProcessor()
    await processor.run()

if __name__ == '__main__':
    asyncio.run(main()) 