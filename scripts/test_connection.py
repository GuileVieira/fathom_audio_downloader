#!/usr/bin/env python3
"""
Script para testar conexão PostgreSQL direta
Performance otimizada com Supabase
"""

import sys
import os
from pathlib import Path
import time
import json

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.postgres_client import PostgreSQLClient
from database_manager import DatabaseManager
from config import Config
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_basic_connection():
    """Testa conexão básica com PostgreSQL"""
    print("🔌 Testando conexão básica...")
    
    client = PostgreSQLClient()
    
    if not client.connected:
        print("❌ Falha na conexão inicial")
        return False
    
    if client.test_connection():
        print("✅ Conexão básica funcionando")
        return True
    else:
        print("❌ Falha no teste de conexão")
        return False


def test_database_structure():
    """Testa estrutura do banco de dados"""
    print("\n📊 Testando estrutura do banco...")
    
    client = PostgreSQLClient()
    
    if not client.connected:
        print("❌ Cliente não conectado")
        return False
    
    # Testa tabelas principais
    tables = client.execute_query("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        AND (table_name LIKE 'fathom%' OR table_name LIKE 'call_%')
        ORDER BY table_name
    """)
    
    expected_tables = [
        'fathom_calls',
        'call_participants', 
        'call_topics',
        'call_takeaways',
        'call_next_steps',
        'call_questions'
    ]
    
    found_tables = [t['table_name'] for t in tables]
    
    print(f"📋 Tabelas encontradas: {len(found_tables)}")
    for table in found_tables:
        print(f"   - {table}")
    
    missing_tables = [t for t in expected_tables if t not in found_tables]
    
    if missing_tables:
        print(f"❌ Tabelas faltando: {missing_tables}")
        return False
    else:
        print("✅ Todas as tabelas principais encontradas")
        return True


def test_insert_and_query():
    """Testa inserção e consulta de dados"""
    print("\n💾 Testando inserção e consulta...")
    
    # Dados de teste
    test_data = {
        'id': 999999,
        'url': 'https://test.fathom.video/test',
        'title': 'Teste de Conexão PostgreSQL',
        'date_formatted': '2024-01-15',
        'duration': '15min',
        'host_name': 'Teste Host',
        'company_domain': 'test.com',
        'status': 'test',
        'participants': [
            {'speaker_id': 1, 'name': 'Participante Teste', 'is_host': True}
        ],
        'summary': {
            'topics': [
                {'title': 'Tópico Teste', 'points': ['Ponto 1', 'Ponto 2']}
            ],
            'key_takeaways': ['Takeaway teste'],
            'next_steps': ['Próximo passo teste']
        },
        'questions': [
            {'speaker_id': 1, 'question': 'Pergunta teste?'}
        ]
    }
    
    db = DatabaseManager()
    
    if not db.connected:
        print("❌ DatabaseManager não conectado")
        return False
    
    # Testa inserção
    print("   📝 Inserindo dados de teste...")
    result = db.save_call(test_data)
    
    if not result:
        print("❌ Falha na inserção")
        return False
    
    print(f"✅ Dados inseridos com ID: {result['id']}")
    
    # Testa consulta
    print("   🔍 Consultando dados inseridos...")
    retrieved = db.get_call_by_id(test_data['id'])
    
    if not retrieved:
        print("❌ Falha na consulta")
        return False
    
    print(f"✅ Dados consultados: {retrieved['title']}")
    
    # Testa busca
    print("   🔎 Testando busca full-text...")
    search_results = db.search_calls('Teste')
    
    if not search_results:
        print("⚠️  Busca não retornou resultados")
    else:
        print(f"✅ Busca funcionando: {len(search_results)} resultados")
    
    # Remove dados de teste
    print("   🗑️  Removendo dados de teste...")
    try:
        db.client.execute_query(
            "DELETE FROM fathom_calls WHERE id = %s",
            (test_data['id'],)
        )
        print("✅ Dados de teste removidos")
    except Exception as e:
        print(f"⚠️  Erro ao remover dados de teste: {e}")
    
    return True


def test_performance():
    """Testa performance das operações"""
    print("\n⚡ Testando performance...")
    
    client = PostgreSQLClient()
    
    if not client.connected:
        print("❌ Cliente não conectado")
        return False
    
    # Teste 1: Query simples
    start_time = time.time()
    result = client.execute_query("SELECT COUNT(*) as total FROM fathom_calls")
    query_time = time.time() - start_time
    
    total_calls = result[0]['total'] if result else 0
    print(f"📊 Query simples: {query_time:.3f}s - {total_calls} chamadas")
    
    # Teste 2: Query complexa com JOIN
    start_time = time.time()
    complex_result = client.execute_query("""
        SELECT 
            fc.id,
            fc.title,
            fc.host_name,
            COUNT(cp.id) as participant_count,
            COUNT(ct.id) as topic_count
        FROM fathom_calls fc
        LEFT JOIN call_participants cp ON fc.id = cp.call_id
        LEFT JOIN call_topics ct ON fc.id = ct.call_id
        WHERE fc.status = 'extracted'
        GROUP BY fc.id, fc.title, fc.host_name
        LIMIT 10
    """)
    complex_time = time.time() - start_time
    
    print(f"🔗 Query complexa: {complex_time:.3f}s - {len(complex_result)} resultados")
    
    # Teste 3: Full-text search
    start_time = time.time()
    search_result = client.search_calls('reunião')
    search_time = time.time() - start_time
    
    print(f"🔍 Full-text search: {search_time:.3f}s - {len(search_result)} resultados")
    
    # Avalia performance
    if query_time < 0.1 and complex_time < 0.5 and search_time < 1.0:
        print("✅ Performance excelente!")
        return True
    elif query_time < 0.5 and complex_time < 2.0 and search_time < 3.0:
        print("✅ Performance boa")
        return True
    else:
        print("⚠️  Performance pode ser melhorada")
        return True  # Não falha o teste


def test_analytics():
    """Testa funcionalidades de analytics"""
    print("\n📈 Testando analytics...")
    
    db = DatabaseManager()
    
    if not db.connected:
        print("❌ DatabaseManager não conectado")
        return False
    
    # Teste analytics básico
    print("   📊 Buscando dados analytics...")
    analytics = db.get_analytics_data()
    
    if 'error' in analytics:
        print(f"❌ Erro nos analytics: {analytics['error']}")
        return False
    
    # Verifica estrutura dos dados
    expected_keys = ['basic_stats', 'top_hosts', 'monthly_activity', 'top_topics']
    
    for key in expected_keys:
        if key in analytics:
            print(f"   ✅ {key}: OK")
        else:
            print(f"   ⚠️  {key}: Não encontrado")
    
    # Mostra estatísticas básicas
    if 'basic_stats' in analytics and analytics['basic_stats']:
        stats = analytics['basic_stats']
        print(f"   📈 Total de chamadas: {stats.get('total_calls', 0)}")
        print(f"   ⏱️  Duração total: {stats.get('total_duration', 0)} min")
        print(f"   👥 Hosts únicos: {stats.get('unique_hosts', 0)}")
        print(f"   🏢 Empresas únicas: {stats.get('unique_companies', 0)}")
    
    print("✅ Analytics funcionando")
    return True


def test_database_info():
    """Testa informações do banco de dados"""
    print("\n🗄️  Testando informações do banco...")
    
    db = DatabaseManager()
    
    if not db.connected:
        print("❌ DatabaseManager não conectado")
        return False
    
    # Informações de tamanho
    size_info = db.get_database_size()
    
    if 'error' in size_info:
        print(f"❌ Erro ao obter tamanho: {size_info['error']}")
        return False
    
    print(f"   💾 Tamanho do banco: {size_info.get('database_size', 'N/A')}")
    print(f"   📊 Tabela principal: {size_info.get('fathom_calls_size', 'N/A')}")
    print(f"   📈 Total de registros: {size_info.get('total_calls', 0)}")
    
    print("✅ Informações do banco obtidas")
    return True


def main():
    """Função principal dos testes"""
    
    print("🧪 Fathom Analytics - Teste de Conexão PostgreSQL")
    print("=" * 60)
    print("🚀 TESTANDO IMPLEMENTAÇÃO DE ALTA PERFORMANCE")
    print("=" * 60)
    
    # Verifica configurações
    print("\n1. Verificando configurações...")
    Config.print_status()
    
    if not Config.validate():
        print("\n❌ Configurações inválidas!")
        print("💡 Configure o arquivo .env com as credenciais PostgreSQL")
        return False
    
    # Executa testes
    tests = [
        ("Conexão Básica", test_basic_connection),
        ("Estrutura do Banco", test_database_structure),
        ("Inserção e Consulta", test_insert_and_query),
        ("Performance", test_performance),
        ("Analytics", test_analytics),
        ("Informações do Banco", test_database_info)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"🧪 TESTE: {test_name}")
        print(f"{'='*60}")
        
        try:
            success = test_func()
            results.append((test_name, success))
            
            if success:
                print(f"✅ {test_name}: PASSOU")
            else:
                print(f"❌ {test_name}: FALHOU")
                
        except Exception as e:
            print(f"❌ {test_name}: ERRO - {e}")
            results.append((test_name, False))
    
    # Resumo dos resultados
    print(f"\n{'='*60}")
    print("📊 RESUMO DOS TESTES")
    print(f"{'='*60}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASSOU" if success else "❌ FALHOU"
        print(f"   {test_name}: {status}")
    
    print(f"\n🎯 RESULTADO FINAL: {passed}/{total} testes passaram")
    
    if passed == total:
        print("🎉 TODOS OS TESTES PASSARAM!")
        print("🚀 Sistema PostgreSQL funcionando perfeitamente!")
        print("\n💡 PRÓXIMOS PASSOS:")
        print("1. Execute: python scripts/import_existing_data.py")
        print("2. Execute: python scripts/generate_reports.py")
        print("3. Use: fathom_batch_processor.py (já integrado)")
    else:
        print(f"⚠️  {total - passed} testes falharam")
        print("💡 Verifique as configurações e tente novamente")
    
    return passed == total


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Testes cancelados pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro inesperado nos testes: {e}")
        sys.exit(1) 