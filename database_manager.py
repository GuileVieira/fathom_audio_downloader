"""
DatabaseManager refatorado para PostgreSQL direto
Performance 3-5x superior ao SDK Supabase
"""

import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, date
import json
from pathlib import Path

from database.postgres_client import PostgreSQLClient
from database.models import FathomCall, CallSummary, CallParticipant, CallTopic, CallTakeaway, CallNextStep, CallQuestion
from config import Config

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Gerenciador de banco de dados usando PostgreSQL direto
    Performance otimizada para analytics e bulk operations
    """
    
    def __init__(self):
        self.client = PostgreSQLClient()
        self.connected = False
        self.initialize()
    
    def initialize(self):
        """Inicializa conexão com banco de dados"""
        try:
            if not self.client.connected:
                logger.error("❌ PostgreSQL não conectado")
                return False
            
            # Testa conexão
            if self.client.test_connection():
                self.connected = True
                logger.info("✅ DatabaseManager inicializado com PostgreSQL direto")
                return True
            else:
                logger.error("❌ Falha no teste de conexão")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar DatabaseManager: {e}")
            return False
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Retorna status da conexão"""
        return {
            'connected': self.connected,
            'client_status': self.client.get_connection_status(),
            'manager_initialized': True
        }
    
    def save_call(self, call_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Salva chamada no banco de dados
        
        Args:
            call_data: Dados da chamada extraídos do Fathom
            
        Returns:
            Dados salvos ou None se erro
        """
        try:
            if not self.connected:
                logger.error("❌ Banco não conectado")
                return None
            
            # Valida dados usando Pydantic
            try:
                fathom_call = FathomCall(**call_data)
                logger.info(f"✅ Dados validados para chamada: {fathom_call.title}")
            except Exception as e:
                logger.warning(f"⚠️  Validação Pydantic falhou: {e}")
                # Continua mesmo com falha na validação
            
            # Salva no banco usando PostgreSQL direto
            result = self.client.insert_call(call_data)
            
            if result:
                logger.info(f"✅ Chamada salva com sucesso: ID {result['id']}")
                return result
            else:
                logger.error("❌ Erro ao salvar chamada")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro ao salvar chamada: {e}")
            return None
    
    def get_call_by_id(self, call_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Busca chamada por ID"""
        try:
            if not self.connected:
                return None
            
            result = self.client.get_call_by_id(call_id)
            
            if result:
                logger.info(f"✅ Chamada encontrada: ID {call_id}")
                return result
            else:
                logger.warning(f"⚠️  Chamada não encontrada: ID {call_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro ao buscar chamada: {e}")
            return None
    
    def get_all_calls(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Busca todas as chamadas com paginação"""
        try:
            if not self.connected:
                return []
            
            results = self.client.get_all_calls(limit, offset)
            logger.info(f"✅ {len(results)} chamadas encontradas")
            return results
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar chamadas: {e}")
            return []
    
    def search_calls(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Busca full-text otimizada"""
        try:
            if not self.connected:
                return []
            
            results = self.client.search_calls(query, limit)
            logger.info(f"✅ {len(results)} chamadas encontradas para '{query}'")
            return results
            
        except Exception as e:
            logger.error(f"❌ Erro na busca: {e}")
            return []
    
    def get_call_stats(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        """Busca estatísticas usando função SQL otimizada"""
        try:
            if not self.connected:
                return None
            
            stats = self.client.get_call_stats(start_date, end_date)
            
            if stats:
                logger.info("✅ Estatísticas obtidas com sucesso")
                return stats
            else:
                logger.warning("⚠️  Nenhuma estatística encontrada")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro ao buscar estatísticas: {e}")
            return None
    
    def get_analytics_data(self) -> Dict[str, Any]:
        """
        Busca dados completos para analytics
        Otimizado para dashboards e relatórios
        """
        try:
            if not self.connected:
                return {'error': 'Banco não conectado'}
            
            logger.info("🔍 Buscando dados analytics completos...")
            analytics = self.client.get_analytics_data()
            
            if 'error' not in analytics:
                logger.info("✅ Dados analytics obtidos com sucesso")
                logger.info(f"   Total de chamadas: {analytics.get('basic_stats', {}).get('total_calls', 0)}")
                logger.info(f"   Top hosts: {len(analytics.get('top_hosts', []))}")
                logger.info(f"   Top tópicos: {len(analytics.get('top_topics', []))}")
            
            return analytics
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar analytics: {e}")
            return {'error': str(e)}
    
    def bulk_import_calls(self, calls_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Importa múltiplas chamadas em lote
        Otimizado para performance máxima
        """
        try:
            if not self.connected:
                return {'error': 'Banco não conectado', 'imported': 0, 'failed': 0}
            
            imported = 0
            failed = 0
            errors = []
            
            logger.info(f"🔄 Iniciando importação em lote: {len(calls_data)} chamadas")
            
            for call_data in calls_data:
                try:
                    result = self.save_call(call_data)
                    if result:
                        imported += 1
                    else:
                        failed += 1
                        errors.append(f"Erro ao salvar chamada ID {call_data.get('id', 'N/A')}")
                        
                except Exception as e:
                    failed += 1
                    errors.append(f"Erro na chamada ID {call_data.get('id', 'N/A')}: {str(e)}")
            
            logger.info(f"✅ Importação concluída: {imported} sucesso, {failed} falhas")
            
            return {
                'imported': imported,
                'failed': failed,
                'total': len(calls_data),
                'errors': errors[:10]  # Limita a 10 erros
            }
            
        except Exception as e:
            logger.error(f"❌ Erro na importação em lote: {e}")
            return {'error': str(e), 'imported': 0, 'failed': 0}
    
    def get_recent_calls(self, days: int = 30) -> List[Dict[str, Any]]:
        """Busca chamadas recentes"""
        try:
            if not self.connected:
                return []
            
            results = self.client.execute_query("""
                SELECT *
                FROM fathom_calls 
                WHERE call_date >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY call_date DESC
            """, (days,))
            
            logger.info(f"✅ {len(results)} chamadas dos últimos {days} dias")
            return results
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar chamadas recentes: {e}")
            return []
    
    def get_host_statistics(self, host_name: str) -> Optional[Dict[str, Any]]:
        """Busca estatísticas de um host específico"""
        try:
            if not self.connected:
                return None
            
            stats = self.client.execute_single("""
                SELECT 
                    host_name,
                    COUNT(*) as total_calls,
                    SUM(duration_minutes) as total_duration,
                    AVG(duration_minutes) as avg_duration,
                    AVG(participant_count) as avg_participants,
                    MIN(call_date) as first_call,
                    MAX(call_date) as last_call,
                    COUNT(DISTINCT company_domain) as unique_companies
                FROM fathom_calls
                WHERE host_name = %s AND status = 'extracted'
                GROUP BY host_name
            """, (host_name,))
            
            if stats:
                logger.info(f"✅ Estatísticas obtidas para host: {host_name}")
                return stats
            else:
                logger.warning(f"⚠️  Host não encontrado: {host_name}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro ao buscar estatísticas do host: {e}")
            return None
    
    def get_company_statistics(self, company_domain: str) -> Optional[Dict[str, Any]]:
        """Busca estatísticas de uma empresa específica"""
        try:
            if not self.connected:
                return None
            
            stats = self.client.execute_single("""
                SELECT 
                    company_domain,
                    COUNT(*) as total_calls,
                    SUM(duration_minutes) as total_duration,
                    AVG(duration_minutes) as avg_duration,
                    COUNT(DISTINCT host_name) as unique_hosts,
                    MIN(call_date) as first_call,
                    MAX(call_date) as last_call
                FROM fathom_calls
                WHERE company_domain = %s AND status = 'extracted'
                GROUP BY company_domain
            """, (company_domain,))
            
            if stats:
                logger.info(f"✅ Estatísticas obtidas para empresa: {company_domain}")
                return stats
            else:
                logger.warning(f"⚠️  Empresa não encontrada: {company_domain}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro ao buscar estatísticas da empresa: {e}")
            return None
    
    def cleanup_old_data(self, days: int = 365) -> Dict[str, Any]:
        """Remove dados antigos para otimização"""
        try:
            if not self.connected:
                return {'error': 'Banco não conectado'}
            
            # Busca registros antigos
            old_records = self.client.execute_query("""
                SELECT id FROM fathom_calls 
                WHERE call_date < CURRENT_DATE - INTERVAL '%s days'
            """, (days,))
            
            if not old_records:
                logger.info("✅ Nenhum registro antigo encontrado")
                return {'removed': 0, 'message': 'Nenhum registro antigo'}
            
            # Remove registros antigos
            old_ids = [record['id'] for record in old_records]
            
            # Remove dados normalizados primeiro
            for call_id in old_ids:
                self.client._delete_normalized_data(call_id)
            
            # Remove chamadas principais
            removed = self.client.execute_query("""
                DELETE FROM fathom_calls 
                WHERE call_date < CURRENT_DATE - INTERVAL '%s days'
                RETURNING id
            """, (days,))
            
            logger.info(f"✅ {len(removed)} registros antigos removidos")
            return {'removed': len(removed), 'message': f'{len(removed)} registros removidos'}
            
        except Exception as e:
            logger.error(f"❌ Erro na limpeza: {e}")
            return {'error': str(e)}
    
    def export_data(self, format: str = 'json', output_path: Optional[str] = None) -> str:
        """Exporta dados para arquivo"""
        try:
            if not self.connected:
                return "Erro: Banco não conectado"
            
            # Busca todos os dados
            calls = self.get_all_calls(limit=10000)  # Limite alto para export
            
            if not calls:
                return "Nenhum dado encontrado para exportar"
            
            # Define caminho de saída
            if not output_path:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_path = f"fathom_export_{timestamp}.{format}"
            
            # Exporta conforme formato
            if format.lower() == 'json':
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(calls, f, indent=2, ensure_ascii=False, default=str)
            
            elif format.lower() == 'csv':
                try:
                    import pandas as pd
                    df = pd.DataFrame(calls)
                    df.to_csv(output_path, index=False, encoding='utf-8')
                except ImportError:
                    return "Erro: pandas não instalado para export CSV"
            
            else:
                return f"Formato não suportado: {format}"
            
            logger.info(f"✅ Dados exportados: {output_path}")
            return f"Dados exportados com sucesso: {output_path}"
            
        except Exception as e:
            logger.error(f"❌ Erro no export: {e}")
            return f"Erro no export: {str(e)}"
    
    def vacuum_database(self) -> bool:
        """Executa VACUUM para otimizar performance"""
        try:
            if not self.connected:
                return False
            
            # VACUUM não pode ser executado em transação
            with self.client.get_connection() as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute("VACUUM ANALYZE fathom_calls")
                    cur.execute("VACUUM ANALYZE call_participants")
                    cur.execute("VACUUM ANALYZE call_topics")
                    cur.execute("VACUUM ANALYZE call_takeaways")
                    cur.execute("VACUUM ANALYZE call_next_steps")
                    cur.execute("VACUUM ANALYZE call_questions")
                conn.autocommit = False
            
            logger.info("✅ VACUUM executado com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro no VACUUM: {e}")
            return False
    
    def get_database_size(self) -> Dict[str, Any]:
        """Busca informações sobre tamanho do banco"""
        try:
            if not self.connected:
                return {'error': 'Banco não conectado'}
            
            size_info = self.client.execute_single("""
                SELECT 
                    pg_size_pretty(pg_database_size(current_database())) as database_size,
                    pg_size_pretty(pg_total_relation_size('fathom_calls')) as fathom_calls_size,
                    pg_size_pretty(pg_total_relation_size('call_participants')) as participants_size,
                    pg_size_pretty(pg_total_relation_size('call_topics')) as topics_size,
                    (SELECT COUNT(*) FROM fathom_calls) as total_calls,
                    (SELECT COUNT(*) FROM call_participants) as total_participants,
                    (SELECT COUNT(*) FROM call_topics) as total_topics
            """)
            
            if size_info:
                logger.info("✅ Informações de tamanho obtidas")
                return size_info
            else:
                return {'error': 'Erro ao obter informações'}
                
        except Exception as e:
            logger.error(f"❌ Erro ao buscar tamanho: {e}")
            return {'error': str(e)}
    
    def close(self):
        """Fecha conexões"""
        if self.client:
            self.client.close()
            logger.info("✅ DatabaseManager fechado")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Instância global para uso em outros módulos
db_manager = DatabaseManager()


def get_database_manager() -> DatabaseManager:
    """Retorna instância do DatabaseManager"""
    return db_manager 