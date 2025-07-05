-- ============================================
-- Fathom Analytics Database Schema
-- ============================================

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================
-- Main Calls Table
-- ============================================
CREATE TABLE IF NOT EXISTS fathom_calls (
    -- Primary identifiers
    id BIGINT PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    
    -- Basic call information
    url TEXT NOT NULL,
    share_url TEXT,
    title TEXT NOT NULL,
    call_date DATE NOT NULL,
    date_formatted TEXT NOT NULL,
    duration_raw TEXT,
    duration_minutes INTEGER,
    
    -- Host and company info
    host_name TEXT,
    company_domain TEXT,
    
    -- Calculated fields for quick queries
    participant_count INTEGER DEFAULT 0,
    topics_count INTEGER DEFAULT 0,
    questions_count INTEGER DEFAULT 0,
    key_takeaways_count INTEGER DEFAULT 0,
    next_steps_count INTEGER DEFAULT 0,
    
    -- JSON data for flexibility
    raw_data JSONB NOT NULL,
    summary_data JSONB,
    participants_data JSONB,
    transcript_data JSONB,
    
    -- Full text search
    search_vector tsvector,
    
    -- Metadata
    extracted_at TIMESTAMP WITH TIME ZONE,
    status TEXT DEFAULT 'extracted',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- Participants Table (Normalized)
-- ============================================
CREATE TABLE IF NOT EXISTS call_participants (
    id SERIAL PRIMARY KEY,
    call_id BIGINT REFERENCES fathom_calls(id) ON DELETE CASCADE,
    speaker_id TEXT NOT NULL,
    name TEXT NOT NULL,
    is_host BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(call_id, speaker_id)
);

-- ============================================
-- Topics Table (Normalized)
-- ============================================
CREATE TABLE IF NOT EXISTS call_topics (
    id SERIAL PRIMARY KEY,
    call_id BIGINT REFERENCES fathom_calls(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    points TEXT[] DEFAULT '{}',
    topic_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- Key Takeaways Table
-- ============================================
CREATE TABLE IF NOT EXISTS call_takeaways (
    id SERIAL PRIMARY KEY,
    call_id BIGINT REFERENCES fathom_calls(id) ON DELETE CASCADE,
    takeaway TEXT NOT NULL,
    takeaway_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- Next Steps Table
-- ============================================
CREATE TABLE IF NOT EXISTS call_next_steps (
    id SERIAL PRIMARY KEY,
    call_id BIGINT REFERENCES fathom_calls(id) ON DELETE CASCADE,
    step TEXT NOT NULL,
    step_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- Questions Table
-- ============================================
CREATE TABLE IF NOT EXISTS call_questions (
    id SERIAL PRIMARY KEY,
    call_id BIGINT REFERENCES fathom_calls(id) ON DELETE CASCADE,
    speaker_id TEXT,
    question TEXT NOT NULL,
    question_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- Indexes for Performance
-- ============================================

-- Primary indexes
CREATE INDEX IF NOT EXISTS idx_fathom_calls_date ON fathom_calls(call_date);
CREATE INDEX IF NOT EXISTS idx_fathom_calls_host ON fathom_calls(host_name);
CREATE INDEX IF NOT EXISTS idx_fathom_calls_company ON fathom_calls(company_domain);
CREATE INDEX IF NOT EXISTS idx_fathom_calls_status ON fathom_calls(status);
CREATE INDEX IF NOT EXISTS idx_fathom_calls_created ON fathom_calls(created_at);

-- JSON indexes (GIN for complex queries)
CREATE INDEX IF NOT EXISTS idx_fathom_calls_raw_data ON fathom_calls USING GIN(raw_data);
CREATE INDEX IF NOT EXISTS idx_fathom_calls_summary ON fathom_calls USING GIN(summary_data);
CREATE INDEX IF NOT EXISTS idx_fathom_calls_participants ON fathom_calls USING GIN(participants_data);

-- Full text search index
CREATE INDEX IF NOT EXISTS idx_fathom_calls_search ON fathom_calls USING GIN(search_vector);

-- Participant indexes
CREATE INDEX IF NOT EXISTS idx_participants_call_id ON call_participants(call_id);
CREATE INDEX IF NOT EXISTS idx_participants_name ON call_participants(name);
CREATE INDEX IF NOT EXISTS idx_participants_is_host ON call_participants(is_host);

-- Topic indexes
CREATE INDEX IF NOT EXISTS idx_topics_call_id ON call_topics(call_id);
CREATE INDEX IF NOT EXISTS idx_topics_title ON call_topics(title);

-- Takeaway indexes
CREATE INDEX IF NOT EXISTS idx_takeaways_call_id ON call_takeaways(call_id);

-- Next steps indexes
CREATE INDEX IF NOT EXISTS idx_next_steps_call_id ON call_next_steps(call_id);

-- Questions indexes
CREATE INDEX IF NOT EXISTS idx_questions_call_id ON call_questions(call_id);
CREATE INDEX IF NOT EXISTS idx_questions_speaker ON call_questions(speaker_id);

-- ============================================
-- Triggers for Automatic Updates
-- ============================================

-- Function to update search vector
CREATE OR REPLACE FUNCTION update_search_vector() RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := 
        setweight(to_tsvector('portuguese', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('portuguese', COALESCE(NEW.host_name, '')), 'B') ||
        setweight(to_tsvector('portuguese', COALESCE(NEW.summary_data->>'purpose', '')), 'C') ||
        setweight(to_tsvector('portuguese', COALESCE(NEW.raw_data->>'transcript_text', '')), 'D');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for search vector update
DROP TRIGGER IF EXISTS trigger_update_search_vector ON fathom_calls;
CREATE TRIGGER trigger_update_search_vector
    BEFORE INSERT OR UPDATE ON fathom_calls
    FOR EACH ROW EXECUTE FUNCTION update_search_vector();

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for updated_at
DROP TRIGGER IF EXISTS trigger_update_updated_at ON fathom_calls;
CREATE TRIGGER trigger_update_updated_at
    BEFORE UPDATE ON fathom_calls
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Useful Views for Analytics
-- ============================================

-- View for quick call statistics
CREATE OR REPLACE VIEW call_stats AS
SELECT 
    DATE_TRUNC('month', call_date) as month,
    COUNT(*) as total_calls,
    AVG(duration_minutes) as avg_duration_minutes,
    AVG(participant_count) as avg_participants,
    COUNT(DISTINCT host_name) as unique_hosts,
    COUNT(DISTINCT company_domain) as unique_companies
FROM fathom_calls 
WHERE status = 'extracted'
GROUP BY DATE_TRUNC('month', call_date)
ORDER BY month DESC;

-- View for participant activity
CREATE OR REPLACE VIEW participant_activity AS
SELECT 
    p.name,
    COUNT(*) as call_count,
    COUNT(CASE WHEN p.is_host THEN 1 END) as hosted_calls,
    MIN(fc.call_date) as first_call,
    MAX(fc.call_date) as last_call,
    AVG(fc.duration_minutes) as avg_call_duration
FROM call_participants p
JOIN fathom_calls fc ON p.call_id = fc.id
WHERE fc.status = 'extracted'
GROUP BY p.name
ORDER BY call_count DESC;

-- View for topic frequency
CREATE OR REPLACE VIEW topic_frequency AS
SELECT 
    ct.title,
    COUNT(*) as frequency,
    COUNT(DISTINCT ct.call_id) as unique_calls,
    AVG(array_length(ct.points, 1)) as avg_points_per_topic
FROM call_topics ct
JOIN fathom_calls fc ON ct.call_id = fc.id
WHERE fc.status = 'extracted'
GROUP BY ct.title
ORDER BY frequency DESC;

-- ============================================
-- Functions for Analytics
-- ============================================

-- Function to get call summary by date range
CREATE OR REPLACE FUNCTION get_calls_summary(
    start_date DATE DEFAULT NULL,
    end_date DATE DEFAULT NULL
) RETURNS TABLE (
    total_calls BIGINT,
    total_duration_minutes BIGINT,
    avg_duration_minutes NUMERIC,
    unique_participants BIGINT,
    unique_hosts BIGINT,
    unique_companies BIGINT,
    most_active_host TEXT,
    most_discussed_topic TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH call_data AS (
        SELECT fc.*, 
               cp.name as participant_name,
               ct.title as topic_title
        FROM fathom_calls fc
        LEFT JOIN call_participants cp ON fc.id = cp.call_id
        LEFT JOIN call_topics ct ON fc.id = ct.call_id
        WHERE fc.status = 'extracted'
        AND (start_date IS NULL OR fc.call_date >= start_date)
        AND (end_date IS NULL OR fc.call_date <= end_date)
    ),
    stats AS (
        SELECT 
            COUNT(DISTINCT id) as total_calls,
            SUM(duration_minutes) as total_duration_minutes,
            AVG(duration_minutes) as avg_duration_minutes,
            COUNT(DISTINCT participant_name) as unique_participants,
            COUNT(DISTINCT host_name) as unique_hosts,
            COUNT(DISTINCT company_domain) as unique_companies
        FROM call_data
    ),
    top_host AS (
        SELECT host_name, COUNT(*) as call_count
        FROM call_data
        WHERE host_name IS NOT NULL
        GROUP BY host_name
        ORDER BY call_count DESC
        LIMIT 1
    ),
    top_topic AS (
        SELECT topic_title, COUNT(*) as topic_count
        FROM call_data
        WHERE topic_title IS NOT NULL
        GROUP BY topic_title
        ORDER BY topic_count DESC
        LIMIT 1
    )
    SELECT 
        s.total_calls,
        s.total_duration_minutes,
        s.avg_duration_minutes,
        s.unique_participants,
        s.unique_hosts,
        s.unique_companies,
        th.host_name,
        tt.topic_title
    FROM stats s
    CROSS JOIN top_host th
    CROSS JOIN top_topic tt;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Initial Data Validation
-- ============================================

-- Comment for documentation
COMMENT ON TABLE fathom_calls IS 'Tabela principal das chamadas do Fathom com dados estruturados e JSON flexível';
COMMENT ON COLUMN fathom_calls.search_vector IS 'Vetor de busca full-text para pesquisas rápidas';
COMMENT ON COLUMN fathom_calls.raw_data IS 'Dados JSON completos da chamada';
COMMENT ON COLUMN fathom_calls.summary_data IS 'Resumo estruturado da chamada';

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✅ Fathom Analytics Database Schema criado com sucesso!';
    RAISE NOTICE '📊 Tabelas: fathom_calls, call_participants, call_topics, call_takeaways, call_next_steps, call_questions';
    RAISE NOTICE '🔍 Índices otimizados para analytics criados';
    RAISE NOTICE '🎯 Views para relatórios disponíveis: call_stats, participant_activity, topic_frequency';
    RAISE NOTICE '⚡ Funções utilitárias criadas: get_calls_summary()';
END $$; 