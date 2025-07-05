# 🗄️ Fathom Analytics - Sistema de Banco de Dados

Sistema completo de persistência e analytics para dados do Fathom usando **Supabase + PostgreSQL**.

## 📋 Visão Geral

Este sistema adiciona uma camada de banco de dados ao seu processador Fathom existente, permitindo:

- ✅ **Persistência automática** dos dados processados
- 📊 **Analytics avançados** e relatórios
- 🔍 **Busca full-text** nas transcrições
- 📈 **Dashboards** e visualizações
- 🔄 **Backup automático** dos dados

## 🚀 Instalação e Configuração

### 1. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 2. Configurar Supabase

1. **Criar projeto no Supabase:**
   - Acesse [supabase.com](https://supabase.com)
   - Crie um novo projeto
   - Anote a URL e as chaves

2. **Configurar variáveis de ambiente:**
   
   Copie o arquivo de exemplo e configure suas chaves:
   ```bash
   cp env.example .env
   ```
   
   Edite o arquivo `.env` com suas chaves reais:
   ```env
   # AssemblyAI (existente)
   ASSEMBLYAI_API_KEY=sua_chave_assemblyai
   
   # Supabase (novo)
   SUPABASE_URL=https://seu-projeto.supabase.co
   SUPABASE_KEY=sua_chave_anon_aqui
   SUPABASE_SERVICE_ROLE_KEY=sua_chave_service_role_aqui
   ```

### 3. Criar Estrutura do Banco

```bash
# 1. Execute o script de migração
python scripts/migrate_database.py

# 2. Copie o SQL gerado e execute no Supabase Dashboard
# (O script mostrará as instruções detalhadas)

# 3. Teste a conexão
python scripts/test_connection.py
```

### 4. Importar Dados Existentes

```bash
# Importa todos os arquivos _final.json existentes
python scripts/import_existing_data.py
```

## 📊 Gerando Relatórios

### Relatório no Console (Rápido)
```bash
python scripts/generate_reports.py
```

### Relatório HTML (Completo)
```bash
python scripts/generate_reports.py --format html
```

### Relatório JSON (Dados)
```bash
python scripts/generate_reports.py --format json
```

## 🔄 Integração Automática

O sistema foi integrado ao seu `fathom_batch_processor.py` existente. Agora, sempre que você processar novos vídeos, os dados serão **automaticamente salvos no banco**.

```bash
# Seu comando normal continua funcionando
python fathom_batch_processor.py

# Agora com persistência automática! 💾
```

## 📁 Estrutura do Projeto

```
teste_download/
├── fathom_batch_processor.py    # ✅ Seu processador (com hook integrado)
├── database_manager.py          # 🆕 Gerenciador principal
├── config.py                    # 🆕 Configurações
├── database/                    # 🆕 Módulos de banco
│   ├── __init__.py
│   ├── supabase_client.py       # Cliente Supabase
│   ├── models.py                # Modelos de dados
│   └── migrations.sql           # SQL das tabelas
├── scripts/                     # 🆕 Scripts utilitários
│   ├── migrate_database.py      # Migração
│   ├── import_existing_data.py  # Import de dados
│   ├── generate_reports.py      # Relatórios
│   └── test_connection.py       # Teste de conexão
├── reports/                     # 🆕 Relatórios gerados
└── downloads_batch/             # ✅ Seus dados existentes
```

## 🗄️ Estrutura do Banco de Dados

### Tabela Principal: `fathom_calls`
- Dados estruturados + JSONB flexível
- Índices otimizados para analytics
- Busca full-text em português

### Tabelas Normalizadas:
- `call_participants` - Participantes
- `call_topics` - Tópicos discutidos
- `call_takeaways` - Key takeaways
- `call_next_steps` - Próximos passos
- `call_questions` - Perguntas detectadas

### Views Otimizadas:
- `call_stats` - Estatísticas por período
- `participant_activity` - Atividade de participantes
- `topic_frequency` - Frequência de tópicos

## 📊 Tipos de Relatórios

### 1. Estatísticas Gerais
- Total de chamadas
- Duração total/média
- Participantes únicos
- Hosts mais ativos

### 2. Análise Temporal
- Chamadas por mês
- Padrões de atividade
- Evolução da duração

### 3. Análise de Conteúdo
- Tópicos mais discutidos
- Key takeaways frequentes
- Análise de participação

### 4. Análise de Participantes
- Participantes mais ativos
- Hosts por atividade
- Rede de colaboração

## 🔍 Funcionalidades Avançadas

### Busca Full-Text
```python
from database_manager import get_database_manager

db = get_database_manager()
results = db.search_calls("integração CRM")
```

### Analytics Customizados
```python
analytics = db.get_analytics_data()
print(f"Total: {analytics['total_calls']} chamadas")
```

### Estatísticas por Período
```python
from datetime import date
stats = db.get_call_stats(
    start_date=date(2024, 1, 1),
    end_date=date(2024, 12, 31)
)
```

## 🛠️ Scripts Utilitários

| Script | Função |
|--------|--------|
| `migrate_database.py` | Cria estrutura do banco |
| `import_existing_data.py` | Importa dados existentes |
| `generate_reports.py` | Gera relatórios |
| `test_connection.py` | Testa conexão |

## ⚡ Fluxo Completo

1. **Processar vídeos** (como sempre):
   ```bash
   python fathom_batch_processor.py
   ```

2. **Dados salvos automaticamente** no banco 💾

3. **Gerar relatórios**:
   ```bash
   python scripts/generate_reports.py --format html
   ```

4. **Analisar insights** nos dashboards gerados 📊

## 🔧 Solução de Problemas

### Erro de Conexão
```bash
# Teste a conexão
python scripts/test_connection.py

# Verifique as configurações
python -c "from config import Config; Config.print_status()"
```

### Dados Não Aparecem
```bash
# Re-importe os dados
python scripts/import_existing_data.py

# Verifique no banco
python scripts/generate_reports.py
```

### Migração Não Funcionou
1. Acesse o Supabase Dashboard
2. Vá para SQL Editor
3. Execute o conteúdo de `database/migrations.sql`

## 🎯 Próximos Passos

1. **Configure o Supabase** seguindo as instruções
2. **Execute a migração** do banco
3. **Importe seus dados** existentes
4. **Gere seu primeiro relatório**
5. **Processe novos vídeos** e veja a magia acontecer! ✨

---

## 💡 Dicas

- **Backup**: Os dados ficam seguros no Supabase
- **Performance**: Índices otimizados para queries rápidas
- **Escalabilidade**: Suporta milhares de chamadas
- **Flexibilidade**: JSONB permite dados não estruturados
- **Busca**: Full-text search em português

## 🆘 Suporte

Se encontrar problemas:

1. Verifique as configurações: `python -c "from config import Config; Config.print_status()"`
2. Teste a conexão: `python scripts/test_connection.py`
3. Verifique os logs do sistema
4. Consulte a documentação do Supabase

---

**🎉 Agora você tem um sistema completo de analytics para seus dados do Fathom!** 