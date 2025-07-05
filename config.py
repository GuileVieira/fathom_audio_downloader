import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

class Config:
    """Configurações centralizadas do sistema"""
    
    # PostgreSQL direto
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', '5432'))
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'fathom_analytics')
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'postgres')
    
    # Pool de conexões
    POSTGRES_MIN_CONNECTIONS = int(os.getenv('POSTGRES_MIN_CONNECTIONS', '2'))
    POSTGRES_MAX_CONNECTIONS = int(os.getenv('POSTGRES_MAX_CONNECTIONS', '10'))
    
    # Timeout de conexão
    POSTGRES_TIMEOUT = int(os.getenv('POSTGRES_TIMEOUT', '30'))
    
    @classmethod
    def validate(cls):
        """Valida configurações obrigatórias"""
        required_configs = []
        
        # Valida PostgreSQL obrigatório
        if cls.POSTGRES_HOST == 'localhost' and cls.POSTGRES_PASSWORD == 'postgres':
            required_configs.append('POSTGRES_HOST')
            required_configs.append('POSTGRES_PASSWORD')
        
        if required_configs:
            print("❌ Configurações obrigatórias faltando:")
            for config in required_configs:
                print(f"   {config}")
            print("\n💡 Configure no arquivo .env:")
            print("   POSTGRES_HOST=seu-host.postgres.com")
            print("   POSTGRES_PASSWORD=sua_senha_aqui")
            return False
        
        return True
    
    @classmethod
    def print_config(cls):
        """Imprime configurações atuais"""
        print("\n⚙️  CONFIGURAÇÕES ATUAIS:")
        print("=" * 40)
        print(f"   PostgreSQL Host: {cls.POSTGRES_HOST}")
        print(f"   PostgreSQL Port: {cls.POSTGRES_PORT}")
        print(f"   PostgreSQL DB: {cls.POSTGRES_DB}")
        print(f"   PostgreSQL User: {cls.POSTGRES_USER}")
        print(f"   Pool Min/Max: {cls.POSTGRES_MIN_CONNECTIONS}/{cls.POSTGRES_MAX_CONNECTIONS}")
        print(f"   Timeout: {cls.POSTGRES_TIMEOUT}s")
        print("=" * 40) 