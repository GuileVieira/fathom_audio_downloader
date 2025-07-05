"""
Cliente Supabase para o sistema Fathom Analytics
"""

import os
import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, date
import json

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None

from config import Config

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SupabaseClient:
    """Cliente para interação com Supabase"""
    
    def __init__(self):
        self.client: Optional[Client] = None
        self.connected = False
        self._initialize_client()
    
    def _initialize_client(self):
        """Inicializa cliente Supabase"""
        if not SUPABASE_AVAILABLE:
            logger.error("❌ Supabase não instalado. Execute: pip install supabase")
            return
        
        if not Config.validate():
            logger.error("❌ Configurações do Supabase não encontradas")
            return
        
        try:
            self.client = create_client(
                Config.SUPABASE_URL,
                Config.SUPABASE_KEY
            )
            self.connected = True
            logger.info("✅ Cliente Supabase conectado com sucesso")
        except Exception as e:
            logger.error(f"❌ Erro ao conectar com Supabase: {e}")
            self.connected = False
    
    def test_connection(self) -> bool:
        """Testa conexão com banco de dados"""
        if not self.connected:
            logger.error("❌ Cliente não conectado")
            return False
        
        try:
            # Testa com uma query simples
            result = self.client.table('fathom_calls').select('id').limit(1).execute()
            logger.info("✅ Conexão com banco testada com sucesso")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao testar conexão: {e}")
            return False
    
    def execute_migration(self, sql_file_path: str) -> bool:
        """Executa migração SQL"""
        if not self.connected:
            logger.error("❌ Cliente não conectado")
            return False
        
        try:
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # Nota: Supabase não permite execução direta de SQL complexo via client
            # Isso deve ser feito via dashboard ou API de admin
            logger.warning("⚠️  Migração SQL deve ser executada via Supabase Dashboard")
            logger.info(f"📄 Arquivo SQL: {sql_file_path}")
            logger.info("🔗 Acesse: https://supabase.com/dashboard/project/[seu-projeto]/sql")
            
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao ler arquivo SQL: {e}")
            return False
    
    def insert_call(self, call_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Insere uma chamada no banco de dados"""
        if not self.connected:
            logger.error("❌ Cliente não conectado")
            return None
        
        try:
            # Prepara dados para inserção
            insert_data = self._prepare_call_data(call_data)
            
            # Insere na tabela principal
            result = self.client.table('fathom_calls').insert(insert_data).execute()
            
            if result.data:
                call_id = result.data[0]['id']
                logger.info(f"✅ Chamada inserida com sucesso: ID {call_id}")
                
                # Insere dados normalizados
                self._insert_normalized_data(call_id, call_data)
                
                return result.data[0]
            else:
                logger.error("❌ Erro ao inserir chamada: sem dados retornados")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro ao inserir chamada: {e}")
            return None
    
    def upsert_call(self, call_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Insere ou atualiza uma chamada"""
        if not self.connected:
            logger.error("❌ Cliente não conectado")
            return None
        
        try:
            # Prepara dados
            insert_data = self._prepare_call_data(call_data)
            
            # Upsert na tabela principal
            result = self.client.table('fathom_calls').upsert(
                insert_data,
                on_conflict='id'
            ).execute()
            
            if result.data:
                call_id = result.data[0]['id']
                logger.info(f"✅ Chamada upsert com sucesso: ID {call_id}")
                
                # Remove dados normalizados existentes
                self._delete_normalized_data(call_id)
                
                # Insere novos dados normalizados
                self._insert_normalized_data(call_id, call_data)
                
                return result.data[0]
            else:
                logger.error("❌ Erro ao fazer upsert da chamada")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro ao fazer upsert da chamada: {e}")
            return None
    
    def get_call_by_id(self, call_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Busca chamada por ID"""
        if not self.connected:
            return None
        
        try:
            result = self.client.table('fathom_calls').select('*').eq('id', call_id).execute()
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar chamada {call_id}: {e}")
            return None
    
    def get_all_calls(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Busca todas as chamadas"""
        if not self.connected:
            return []
        
        try:
            result = self.client.table('fathom_calls').select('*').limit(limit).execute()
            return result.data or []
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar chamadas: {e}")
            return []
    
    def get_call_stats(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        """Busca estatísticas de chamadas"""
        if not self.connected:
            return None
        
        try:
            # Usar função SQL personalizada
            params = {}
            if start_date:
                params['start_date'] = start_date.isoformat()
            if end_date:
                params['end_date'] = end_date.isoformat()
            
            result = self.client.rpc('get_calls_summary', params).execute()
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar estatísticas: {e}")
            return None
    
    def search_calls(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Busca chamadas por texto"""
        if not self.connected:
            return []
        
        try:
            # Busca full-text usando search_vector
            result = self.client.table('fathom_calls').select('*').text_search(
                'search_vector', 
                query,
                type='websearch',
                config='portuguese'
            ).limit(limit).execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar chamadas: {e}")
            return []
    
    def _prepare_call_data(self, call_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepara dados para inserção no banco"""
        prepared = {}
        
        # Campos obrigatórios
        prepared['id'] = int(call_data['id']) if isinstance(call_data['id'], str) and call_data['id'].isdigit() else call_data['id']
        prepared['url'] = call_data['url']
        prepared['title'] = call_data['title']
        prepared['date_formatted'] = call_data['date_formatted']
        
        # Converte data
        try:
            prepared['call_date'] = datetime.strptime(call_data['date_formatted'], '%Y-%m-%d').date().isoformat()
        except (ValueError, KeyError):
            prepared['call_date'] = None
        
        # Campos opcionais
        prepared['share_url'] = call_data.get('share_url')
        prepared['duration_raw'] = call_data.get('duration')
        prepared['host_name'] = call_data.get('host_name')
        prepared['company_domain'] = call_data.get('company_domain')
        prepared['extracted_at'] = call_data.get('extracted_at')
        prepared['status'] = call_data.get('status', 'extracted')
        
        # Calcula duração em minutos
        if 'duration' in call_data:
            prepared['duration_minutes'] = self._parse_duration_minutes(call_data['duration'])
        
        # Conta elementos
        prepared['participant_count'] = len(call_data.get('participants', []))
        prepared['questions_count'] = len(call_data.get('questions', []))
        
        if 'summary' in call_data:
            summary = call_data['summary']
            prepared['topics_count'] = len(summary.get('topics', []))
            prepared['key_takeaways_count'] = len(summary.get('key_takeaways', []))
            prepared['next_steps_count'] = len(summary.get('next_steps', []))
        else:
            prepared['topics_count'] = 0
            prepared['key_takeaways_count'] = 0
            prepared['next_steps_count'] = 0
        
        # Dados JSON
        prepared['raw_data'] = call_data
        prepared['summary_data'] = call_data.get('summary')
        prepared['participants_data'] = call_data.get('participants', [])
        
        if 'transcript_text' in call_data:
            prepared['transcript_data'] = {'transcript_text': call_data['transcript_text']}
        
        return prepared
    
    def _parse_duration_minutes(self, duration_str: str) -> Optional[int]:
        """Converte string de duração para minutos"""
        if not duration_str:
            return None
        
        duration_str = duration_str.lower()
        total_minutes = 0
        
        # Extrai horas
        if 'h' in duration_str:
            hours_part = duration_str.split('h')[0].strip()
            if hours_part.isdigit():
                total_minutes += int(hours_part) * 60
        
        # Extrai minutos
        if 'min' in duration_str:
            mins_part = duration_str.split('min')[0]
            if 'h' in mins_part:
                mins_part = mins_part.split('h')[1].strip()
            else:
                mins_part = mins_part.strip()
            
            mins_clean = ''.join(c for c in mins_part if c.isdigit())
            if mins_clean:
                total_minutes += int(mins_clean)
        
        return total_minutes if total_minutes > 0 else None
    
    def _insert_normalized_data(self, call_id: int, call_data: Dict[str, Any]):
        """Insere dados normalizados em tabelas relacionadas"""
        try:
            # Participantes
            if 'participants' in call_data:
                participants_data = []
                for p in call_data['participants']:
                    participants_data.append({
                        'call_id': call_id,
                        'speaker_id': p['speaker_id'],
                        'name': p['name'],
                        'is_host': p.get('is_host', False)
                    })
                
                if participants_data:
                    self.client.table('call_participants').insert(participants_data).execute()
            
            # Tópicos
            if 'summary' in call_data and 'topics' in call_data['summary']:
                topics_data = []
                for i, topic in enumerate(call_data['summary']['topics']):
                    topics_data.append({
                        'call_id': call_id,
                        'title': topic['title'],
                        'points': topic.get('points', []),
                        'topic_order': i
                    })
                
                if topics_data:
                    self.client.table('call_topics').insert(topics_data).execute()
            
            # Key Takeaways
            if 'summary' in call_data and 'key_takeaways' in call_data['summary']:
                takeaways_data = []
                for i, takeaway in enumerate(call_data['summary']['key_takeaways']):
                    takeaways_data.append({
                        'call_id': call_id,
                        'takeaway': takeaway,
                        'takeaway_order': i
                    })
                
                if takeaways_data:
                    self.client.table('call_takeaways').insert(takeaways_data).execute()
            
            # Next Steps
            if 'summary' in call_data and 'next_steps' in call_data['summary']:
                steps_data = []
                for i, step in enumerate(call_data['summary']['next_steps']):
                    steps_data.append({
                        'call_id': call_id,
                        'step': step,
                        'step_order': i
                    })
                
                if steps_data:
                    self.client.table('call_next_steps').insert(steps_data).execute()
            
            # Perguntas
            if 'questions' in call_data:
                questions_data = []
                for i, question in enumerate(call_data['questions']):
                    questions_data.append({
                        'call_id': call_id,
                        'speaker_id': question.get('speaker_id'),
                        'question': question['question'],
                        'question_order': i
                    })
                
                if questions_data:
                    self.client.table('call_questions').insert(questions_data).execute()
            
            logger.info(f"✅ Dados normalizados inseridos para chamada {call_id}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao inserir dados normalizados: {e}")
    
    def _delete_normalized_data(self, call_id: int):
        """Remove dados normalizados de tabelas relacionadas"""
        try:
            tables = ['call_participants', 'call_topics', 'call_takeaways', 'call_next_steps', 'call_questions']
            
            for table in tables:
                self.client.table(table).delete().eq('call_id', call_id).execute()
            
            logger.info(f"✅ Dados normalizados removidos para chamada {call_id}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao remover dados normalizados: {e}")
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Retorna status da conexão"""
        return {
            'connected': self.connected,
            'supabase_available': SUPABASE_AVAILABLE,
            'url': Config.SUPABASE_URL if self.connected else None,
            'client_initialized': self.client is not None
        } 