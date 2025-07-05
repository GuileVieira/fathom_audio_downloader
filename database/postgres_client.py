"""
Cliente PostgreSQL direto para máxima performance com Supabase
"""

import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, date
import json
from contextlib import contextmanager

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, Json, execute_batch
    from psycopg2.pool import ThreadedConnectionPool
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None
    RealDictCursor = None
    Json = None
    execute_batch = None
    ThreadedConnectionPool = None

from config import Config

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PostgreSQLClient:
    """Cliente PostgreSQL direto para máxima performance"""
    
    def __init__(self):
        self.pool: Optional[ThreadedConnectionPool] = None
        self.connected = False
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Inicializa pool de conexões PostgreSQL"""
        if not PSYCOPG2_AVAILABLE:
            logger.error("❌ psycopg2 não instalado. Execute: pip install psycopg2-binary")
            return
        
        try:
            # Parâmetros de conexão
            connection_params = {
                'host': Config.POSTGRES_HOST,
                'port': Config.POSTGRES_PORT,
                'database': Config.POSTGRES_DB,
                'user': Config.POSTGRES_USER,
                'password': Config.POSTGRES_PASSWORD,
                'sslmode': 'require',  # Supabase exige SSL
                'connect_timeout': 10,
                'application_name': 'fathom_analytics'
            }
            
            # Criar pool de conexões
            self.pool = ThreadedConnectionPool(
                minconn=2,  # Mínimo 2 conexões
                maxconn=10,  # Máximo 10 conexões
                **connection_params
            )
            
            self.connected = True
            logger.info("✅ Pool PostgreSQL conectado com sucesso")
            logger.info(f"   Host: {Config.POSTGRES_HOST}")
            logger.info(f"   Database: {Config.POSTGRES_DB}")
            logger.info(f"   Pool: 2-10 conexões")
            
        except Exception as e:
            logger.error(f"❌ Erro ao conectar PostgreSQL: {e}")
            self.connected = False
    
    @contextmanager
    def get_connection(self):
        """Context manager para conexões do pool"""
        if not self.connected or not self.pool:
            raise Exception("PostgreSQL não conectado")
        
        conn = None
        try:
            conn = self.pool.getconn()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                self.pool.putconn(conn)
    
    def test_connection(self) -> bool:
        """Testa conexão com banco de dados"""
        if not self.connected:
            logger.error("❌ Pool não conectado")
            return False
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    result = cur.fetchone()
                    
            logger.info("✅ Conexão PostgreSQL testada com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao testar conexão: {e}")
            return False
    
    def execute_query(self, sql: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Executa query SELECT e retorna resultados"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(sql, params)
                    return [dict(row) for row in cur.fetchall()]
                    
        except Exception as e:
            logger.error(f"❌ Erro ao executar query: {e}")
            logger.error(f"   SQL: {sql}")
            return []
    
    def execute_single(self, sql: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """Executa query e retorna um único resultado"""
        results = self.execute_query(sql, params)
        return results[0] if results else None
    
    def execute_insert(self, sql: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """Executa INSERT e retorna o registro inserido"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(sql + " RETURNING *", params)
                    result = cur.fetchone()
                    conn.commit()
                    return dict(result) if result else None
                    
        except Exception as e:
            logger.error(f"❌ Erro ao executar insert: {e}")
            return None
    
    def execute_upsert(self, table: str, data: Dict[str, Any], conflict_column: str = 'id') -> Optional[Dict[str, Any]]:
        """Executa UPSERT otimizado"""
        try:
            # Prepara colunas e valores
            columns = list(data.keys())
            values = list(data.values())
            placeholders = ', '.join(['%s'] * len(values))
            columns_str = ', '.join(columns)
            
            # Colunas para UPDATE (exceto a chave de conflito)
            update_columns = [col for col in columns if col != conflict_column]
            update_set = ', '.join([f"{col} = EXCLUDED.{col}" for col in update_columns])
            
            sql = f"""
                INSERT INTO {table} ({columns_str})
                VALUES ({placeholders})
                ON CONFLICT ({conflict_column}) DO UPDATE SET
                {update_set}
                RETURNING *
            """
            
            return self.execute_insert(sql, tuple(values))
            
        except Exception as e:
            logger.error(f"❌ Erro ao executar upsert: {e}")
            return None
    
    def execute_batch_insert(self, sql: str, data_list: List[tuple], page_size: int = 1000) -> bool:
        """Executa batch insert otimizado"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    execute_batch(cur, sql, data_list, page_size=page_size)
                    conn.commit()
                    
            logger.info(f"✅ Batch insert: {len(data_list)} registros")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro no batch insert: {e}")
            return False
    
    def insert_call(self, call_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Insere uma chamada no banco de dados"""
        try:
            # Prepara dados para inserção
            prepared_data = self._prepare_call_data(call_data)
            
            # Insere na tabela principal
            result = self.execute_upsert('fathom_calls', prepared_data, 'id')
            
            if result:
                call_id = result['id']
                logger.info(f"✅ Chamada inserida: ID {call_id}")
                
                # Insere dados normalizados
                self._insert_normalized_data(call_id, call_data)
                
                return result
            else:
                logger.error("❌ Erro ao inserir chamada")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro ao inserir chamada: {e}")
            return None
    
    def get_call_by_id(self, call_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Busca chamada por ID"""
        return self.execute_single(
            "SELECT * FROM fathom_calls WHERE id = %s",
            (call_id,)
        )
    
    def get_all_calls(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Busca todas as chamadas com paginação"""
        return self.execute_query(
            "SELECT * FROM fathom_calls ORDER BY call_date DESC LIMIT %s OFFSET %s",
            (limit, offset)
        )
    
    def search_calls(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Busca full-text otimizada"""
        return self.execute_query("""
            SELECT *, ts_rank(search_vector, websearch_to_tsquery('portuguese', %s)) as rank
            FROM fathom_calls 
            WHERE search_vector @@ websearch_to_tsquery('portuguese', %s)
            ORDER BY rank DESC, call_date DESC
            LIMIT %s
        """, (query, query, limit))
    
    def get_call_stats(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        """Busca estatísticas usando função SQL"""
        params = []
        if start_date:
            params.append(start_date)
        if end_date:
            params.append(end_date)
        
        return self.execute_single(
            "SELECT * FROM get_calls_summary(%s, %s)",
            tuple(params) if params else (None, None)
        )
    
    def get_analytics_data(self) -> Dict[str, Any]:
        """Busca dados completos para analytics com queries otimizadas"""
        try:
            analytics = {}
            
            # Estatísticas básicas
            basic_stats = self.execute_single("""
                SELECT 
                    COUNT(*) as total_calls,
                    SUM(duration_minutes) as total_duration,
                    AVG(duration_minutes) as avg_duration,
                    COUNT(DISTINCT host_name) as unique_hosts,
                    COUNT(DISTINCT company_domain) as unique_companies,
                    COUNT(DISTINCT participants_data) as unique_participants
                FROM fathom_calls
                WHERE status = 'extracted'
            """)
            
            analytics['basic_stats'] = basic_stats
            
            # Top hosts
            analytics['top_hosts'] = self.execute_query("""
                SELECT 
                    host_name,
                    COUNT(*) as call_count,
                    SUM(duration_minutes) as total_duration,
                    AVG(duration_minutes) as avg_duration,
                    AVG(participant_count) as avg_participants
                FROM fathom_calls
                WHERE host_name IS NOT NULL AND status = 'extracted'
                GROUP BY host_name
                ORDER BY call_count DESC
                LIMIT 10
            """)
            
            # Atividade mensal
            analytics['monthly_activity'] = self.execute_query("""
                SELECT 
                    DATE_TRUNC('month', call_date) as month,
                    COUNT(*) as call_count,
                    SUM(duration_minutes) as total_duration,
                    COUNT(DISTINCT host_name) as unique_hosts
                FROM fathom_calls
                WHERE status = 'extracted'
                GROUP BY month
                ORDER BY month DESC
                LIMIT 12
            """)
            
            # Top tópicos
            analytics['top_topics'] = self.execute_query("""
                SELECT 
                    title,
                    COUNT(*) as frequency,
                    COUNT(DISTINCT call_id) as unique_calls,
                    AVG(array_length(points, 1)) as avg_points
                FROM call_topics ct
                JOIN fathom_calls fc ON ct.call_id = fc.id
                WHERE fc.status = 'extracted'
                GROUP BY title
                ORDER BY frequency DESC
                LIMIT 10
            """)
            
            # Distribuição de duração
            duration_dist = self.execute_single("""
                SELECT 
                    COUNT(CASE WHEN duration_minutes < 10 THEN 1 END) as short_calls,
                    COUNT(CASE WHEN duration_minutes BETWEEN 10 AND 30 THEN 1 END) as medium_calls,
                    COUNT(CASE WHEN duration_minutes > 30 THEN 1 END) as long_calls,
                    MIN(duration_minutes) as min_duration,
                    MAX(duration_minutes) as max_duration
                FROM fathom_calls
                WHERE duration_minutes IS NOT NULL AND status = 'extracted'
            """)
            
            analytics['duration_distribution'] = duration_dist
            
            # Participantes mais ativos
            analytics['top_participants'] = self.execute_query("""
                SELECT 
                    name,
                    COUNT(*) as call_count,
                    COUNT(CASE WHEN is_host THEN 1 END) as hosted_calls,
                    AVG(fc.duration_minutes) as avg_call_duration
                FROM call_participants cp
                JOIN fathom_calls fc ON cp.call_id = fc.id
                WHERE fc.status = 'extracted'
                GROUP BY name
                ORDER BY call_count DESC
                LIMIT 10
            """)
            
            return analytics
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar analytics: {e}")
            return {'error': str(e)}
    
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
            prepared['call_date'] = datetime.strptime(call_data['date_formatted'], '%Y-%m-%d').date()
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
        
        # Dados JSON usando psycopg2.extras.Json para otimização
        prepared['raw_data'] = Json(call_data)
        prepared['summary_data'] = Json(call_data.get('summary')) if call_data.get('summary') else None
        prepared['participants_data'] = Json(call_data.get('participants', []))
        
        if 'transcript_text' in call_data:
            prepared['transcript_data'] = Json({'transcript_text': call_data['transcript_text']})
        
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
        """Insere dados normalizados usando batch operations"""
        try:
            # Remove dados existentes primeiro
            self._delete_normalized_data(call_id)
            
            # Participantes (batch insert)
            if 'participants' in call_data and call_data['participants']:
                participants_sql = """
                    INSERT INTO call_participants (call_id, speaker_id, name, is_host)
                    VALUES (%s, %s, %s, %s)
                """
                participants_data = [
                    (call_id, p['speaker_id'], p['name'], p.get('is_host', False))
                    for p in call_data['participants']
                ]
                self.execute_batch_insert(participants_sql, participants_data)
            
            # Tópicos (batch insert)
            if 'summary' in call_data and 'topics' in call_data['summary']:
                topics_sql = """
                    INSERT INTO call_topics (call_id, title, points, topic_order)
                    VALUES (%s, %s, %s, %s)
                """
                topics_data = [
                    (call_id, topic['title'], topic.get('points', []), i)
                    for i, topic in enumerate(call_data['summary']['topics'])
                ]
                self.execute_batch_insert(topics_sql, topics_data)
            
            # Key Takeaways
            if 'summary' in call_data and 'key_takeaways' in call_data['summary']:
                takeaways_sql = """
                    INSERT INTO call_takeaways (call_id, takeaway, takeaway_order)
                    VALUES (%s, %s, %s)
                """
                takeaways_data = [
                    (call_id, takeaway, i)
                    for i, takeaway in enumerate(call_data['summary']['key_takeaways'])
                ]
                self.execute_batch_insert(takeaways_sql, takeaways_data)
            
            # Next Steps
            if 'summary' in call_data and 'next_steps' in call_data['summary']:
                steps_sql = """
                    INSERT INTO call_next_steps (call_id, step, step_order)
                    VALUES (%s, %s, %s)
                """
                steps_data = [
                    (call_id, step, i)
                    for i, step in enumerate(call_data['summary']['next_steps'])
                ]
                self.execute_batch_insert(steps_sql, steps_data)
            
            # Perguntas
            if 'questions' in call_data and call_data['questions']:
                questions_sql = """
                    INSERT INTO call_questions (call_id, speaker_id, question, question_order)
                    VALUES (%s, %s, %s, %s)
                """
                questions_data = [
                    (call_id, q.get('speaker_id'), q['question'], i)
                    for i, q in enumerate(call_data['questions'])
                ]
                self.execute_batch_insert(questions_sql, questions_data)
            
            logger.info(f"✅ Dados normalizados inseridos para chamada {call_id}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao inserir dados normalizados: {e}")
    
    def _delete_normalized_data(self, call_id: int):
        """Remove dados normalizados de forma eficiente"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Delete em uma transação
                    tables = ['call_participants', 'call_topics', 'call_takeaways', 'call_next_steps', 'call_questions']
                    
                    for table in tables:
                        cur.execute(f"DELETE FROM {table} WHERE call_id = %s", (call_id,))
                    
                    conn.commit()
            
            logger.debug(f"✅ Dados normalizados removidos para chamada {call_id}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao remover dados normalizados: {e}")
    
    def close(self):
        """Fecha pool de conexões"""
        if self.pool:
            self.pool.closeall()
            logger.info("✅ Pool PostgreSQL fechado")
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Retorna status da conexão"""
        return {
            'connected': self.connected,
            'psycopg2_available': PSYCOPG2_AVAILABLE,
            'host': Config.POSTGRES_HOST if self.connected else None,
            'database': Config.POSTGRES_DB if self.connected else None,
            'pool_initialized': self.pool is not None
        } 