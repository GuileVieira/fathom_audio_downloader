import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente
load_dotenv()

class Config:
    """Configurações do projeto"""
    
    # AssemblyAI (existente)
    ASSEMBLYAI_API_KEY = os.getenv('ASSEMBLYAI_API_KEY', 'sua_chave_aqui')
    
    # Supabase (opcional, para dashboard)
    SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://seu-projeto.supabase.co')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'sua_chave_anon_aqui')
    SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY', 'sua_chave_service_role_aqui')
    
    # PostgreSQL direto (principal)
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'db.seu-projeto.supabase.co')
    POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', '5432'))
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'postgres')
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'sua_senha_postgres')
    
    # Database
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'fathom_analytics')
    DATABASE_SCHEMA = os.getenv('DATABASE_SCHEMA', 'public')
    
    # Application
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
    DEBUG = os.getenv('DEBUG', 'true').lower() == 'true'
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # Paths
    DOWNLOADS_DIR = 'downloads_batch'
    COOKIES_DIR = 'cookies'
    
    @classmethod
    def validate(cls):
        """Valida se as configurações necessárias estão presentes"""
        missing = []
        
        # Valida PostgreSQL (principal)
        if cls.POSTGRES_HOST == 'db.seu-projeto.supabase.co':
            missing.append('POSTGRES_HOST')
        
        if cls.POSTGRES_PASSWORD == 'sua_senha_postgres':
            missing.append('POSTGRES_PASSWORD')
        
        # Valida Supabase (opcional)
        supabase_missing = []
        if cls.SUPABASE_URL == 'https://seu-projeto.supabase.co':
            supabase_missing.append('SUPABASE_URL')
        
        if cls.SUPABASE_KEY == 'sua_chave_anon_aqui':
            supabase_missing.append('SUPABASE_KEY')
            
        if missing:
            print(f"❌ Configurações PostgreSQL faltando no .env: {', '.join(missing)}")
            print("📝 Configure as variáveis obrigatórias:")
            print("   POSTGRES_HOST=db.seu-projeto.supabase.co")
            print("   POSTGRES_PASSWORD=sua_senha_postgres")
            return False
        
        if supabase_missing:
            print(f"⚠️  Configurações Supabase opcionais faltando: {', '.join(supabase_missing)}")
            print("💡 Para usar dashboard do Supabase, configure também:")
            print("   SUPABASE_URL=https://seu-projeto.supabase.co")
            print("   SUPABASE_KEY=sua_chave_anon_aqui")
        
        return True
    
    @classmethod
    def print_status(cls):
        """Imprime o status das configurações"""
        print("🔧 Configurações carregadas:")
        print(f"   Environment: {cls.ENVIRONMENT}")
        print(f"   Debug: {cls.DEBUG}")
        print(f"   PostgreSQL Host: {cls.POSTGRES_HOST}")
        print(f"   PostgreSQL DB: {cls.POSTGRES_DB}")
        print(f"   PostgreSQL User: {cls.POSTGRES_USER}")
        print(f"   Supabase URL: {cls.SUPABASE_URL[:30]}...")
        print(f"   AssemblyAI: {'✅ Configurado' if cls.ASSEMBLYAI_API_KEY != 'sua_chave_aqui' else '❌ Não configurado'}")
        print(f"   PostgreSQL: {'✅ Configurado' if cls.POSTGRES_PASSWORD != 'sua_senha_postgres' else '❌ Não configurado'}")
        print(f"   Supabase (opcional): {'✅ Configurado' if cls.SUPABASE_KEY != 'sua_chave_anon_aqui' else '❌ Não configurado'}") 