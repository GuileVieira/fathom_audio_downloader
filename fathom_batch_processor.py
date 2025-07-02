import asyncio
import json
import os
import subprocess
import aiohttp
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
                
                # 3. Transcrever com AssemblyAI
                if ASSEMBLYAI_API_KEY and ASSEMBLYAI_API_KEY != 'sua_chave_aqui':
                    await self._transcribe_audio(mp3_path, title)
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
    
    async def _transcribe_audio(self, mp3_path: Path, title: str) -> Optional[str]:
        """Transcreve áudio usando AssemblyAI"""
        transcript_path = Path(DOWNLOADS_DIR) / f"{title}_transcript.txt"
        json_response_path = Path(DOWNLOADS_DIR) / f"{title}_transcript_details.json" # Log de diagnóstico

        if transcript_path.exists():
            print(f"📝 {title} - Transcrição já existe")
            return transcript_path.read_text(encoding='utf-8')
        
        print(f"📝 {title} - Transcrevendo com AssemblyAI...")
        
        headers = {"authorization": ASSEMBLYAI_API_KEY}
        
        # Upload do arquivo
        async with aiohttp.ClientSession() as session:
            with open(mp3_path, 'rb') as f:
                async with session.post(
                    "https://api.assemblyai.com/v2/upload",
                    headers=headers,
                    data=f
                ) as response:
                    upload_result = await response.json()
                    audio_url = upload_result["upload_url"]
            
            # Solicitar transcrição
            payload = {
                "audio_url": audio_url,
                "language_code": "pt",
                "speaker_labels": True
            }
            
            async with session.post(
                "https://api.assemblyai.com/v2/transcript",
                headers=headers,
                json=payload
            ) as response:
                transcript_data = await response.json()
                transcript_id = transcript_data["id"]
            
            # Aguardar conclusão
            while True:
                async with session.get(
                    f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                    headers=headers
                ) as response:
                    result = await response.json()
                    
                    # Salva a resposta JSON completa para diagnóstico
                    with open(json_response_path, 'w', encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)

                    if result["status"] == "completed":
                        transcript_text = result["text"]
                        transcript_path.write_text(transcript_text, encoding='utf-8')
                        return transcript_text
                    elif result["status"] == "error":
                        raise Exception(f"Erro na transcrição: {result.get('error', 'Unknown error')}")
                    
                    print(f"    Status: {result['status']}... aguardando...")
                    await asyncio.sleep(10)
    
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