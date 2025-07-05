#!/usr/bin/env python3
"""
Script para importar dados existentes do Fathom para o banco de dados
"""

import sys
import os
from pathlib import Path
import json
from datetime import datetime

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database_manager import DatabaseManager
from config import Config
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Função principal do script de importação"""
    
    print("📥 Fathom Analytics - Importação de Dados Existentes")
    print("=" * 60)
    
    # Verifica configurações
    print("\n1. Verificando configurações...")
    Config.print_status()
    
    if not Config.validate():
        print("\n❌ Configurações inválidas. Configure o arquivo .env")
        return False
    
    # Inicializa DatabaseManager
    print("\n2. Inicializando DatabaseManager...")
    db_manager = DatabaseManager()
    
    # Verifica status
    status = db_manager.get_status()
    print(f"   Inicializado: {status['initialized']}")
    print(f"   Conectado: {status['supabase_status']['connected']}")
    
    if not db_manager.connected:
        print("❌ Não foi possível conectar ao banco de dados")
        print("💡 Execute primeiro: python scripts/migrate_database.py")
        return False
    
    # Testa conexão
    print("\n3. Testando conexão com banco...")
    if db_manager.test_connection():
        print("✅ Conexão testada com sucesso")
    else:
        print("❌ Falha no teste de conexão")
        return False
    
    # Localiza diretório de downloads
    print("\n4. Localizando arquivos de dados...")
    downloads_dir = Path(Config.DOWNLOADS_DIR)
    
    if not downloads_dir.exists():
        print(f"❌ Diretório não encontrado: {downloads_dir}")
        return False
    
    # Busca arquivos _final.json
    json_files = list(downloads_dir.glob('*_final.json'))
    
    if not json_files:
        print(f"⚠️  Nenhum arquivo _final.json encontrado em {downloads_dir}")
        print("💡 Certifique-se de que os dados foram processados pelo fathom_batch_processor.py")
        return False
    
    print(f"📁 Encontrados {len(json_files)} arquivos para importar:")
    for i, file in enumerate(json_files[:5], 1):  # Mostra apenas os primeiros 5
        print(f"   {i}. {file.name}")
    
    if len(json_files) > 5:
        print(f"   ... e mais {len(json_files) - 5} arquivos")
    
    # Pergunta confirmação
    print(f"\n🤔 Deseja importar {len(json_files)} arquivo(s) para o banco de dados?")
    response = input("   Digite 'sim' para continuar ou 'não' para cancelar: ").lower().strip()
    
    if response not in ['sim', 's', 'yes', 'y']:
        print("⏹️  Importação cancelada pelo usuário")
        return False
    
    # Executa importação
    print("\n5. Iniciando importação...")
    print("=" * 40)
    
    start_time = datetime.now()
    
    try:
        results = db_manager.import_all_existing_data()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Mostra resultados
        print("\n" + "=" * 60)
        print("📊 RESULTADOS DA IMPORTAÇÃO:")
        print("=" * 60)
        
        if results['success']:
            print(f"✅ Importação concluída com sucesso!")
            print(f"   📈 Processados: {results['processed']}")
            print(f"   ❌ Falharam: {results['failed']}")
            print(f"   📁 Total: {results['processed'] + results['failed']}")
            print(f"   ⏱️  Tempo: {duration:.2f} segundos")
            
            if results['failed'] > 0:
                print(f"\n⚠️  {results['failed']} arquivo(s) falharam:")
                for error in results.get('errors', []):
                    print(f"   • {error['file']}: {error['error']}")
            
            # Mostra detalhes dos arquivos processados
            if results['files']:
                print(f"\n📄 Detalhes dos arquivos:")
                for file_info in results['files']:
                    status_icon = "✅" if file_info['status'] == 'success' else "❌"
                    print(f"   {status_icon} {file_info['file']}")
        else:
            print(f"❌ Importação falhou: {results.get('error', 'Erro desconhecido')}")
            return False
        
    except Exception as e:
        print(f"❌ Erro durante importação: {e}")
        return False
    
    # Verifica dados importados
    print("\n6. Verificando dados importados...")
    try:
        all_calls = db_manager.get_all_calls(limit=10)
        print(f"✅ {len(all_calls)} chamada(s) encontrada(s) no banco")
        
        if all_calls:
            print("\n📋 Primeiras chamadas importadas:")
            for i, call in enumerate(all_calls[:3], 1):
                print(f"   {i}. {call.get('title', 'Sem título')} ({call.get('call_date', 'Sem data')})")
        
    except Exception as e:
        print(f"⚠️  Erro ao verificar dados: {e}")
    
    # Próximos passos
    print("\n" + "=" * 60)
    print("🎯 PRÓXIMOS PASSOS:")
    print("=" * 60)
    print("1. Gerar relatórios:")
    print("   python scripts/generate_reports.py")
    print("\n2. Testar busca de dados:")
    print("   python scripts/test_queries.py")
    print("\n3. Integrar com o processador existente:")
    print("   # Adicione esta linha no final do save_unified_output() em fathom_batch_processor.py:")
    print("   # from database_manager import get_database_manager")
    print("   # get_database_manager().save_call_data(paths['final'])")
    print("=" * 60)
    
    return True


def show_file_preview(file_path: Path, max_lines: int = 10):
    """Mostra preview de um arquivo JSON"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\n📄 Preview: {file_path.name}")
        print(f"   ID: {data.get('id', 'N/A')}")
        print(f"   Título: {data.get('title', 'N/A')}")
        print(f"   Data: {data.get('date', 'N/A')}")
        print(f"   Host: {data.get('host_name', 'N/A')}")
        print(f"   Participantes: {len(data.get('participants', []))}")
        print(f"   Duração: {data.get('duration', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Erro ao ler {file_path.name}: {e}")


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Operação cancelada pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")
        sys.exit(1) 