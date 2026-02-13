-- ARIS Agent Database Schema
-- PostgreSQL 16+ with JSONB support

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search

-- Core session management
CREATE TABLE chats (
    id VARCHAR(50) PRIMARY KEY,           -- e.g., "1758852782787-xig8s"
    user_id VARCHAR(100) NOT NULL,       -- "Nemanja"
    agent_type VARCHAR(50) DEFAULT 'manufacturing',
    model_id VARCHAR(100),               -- "us.anthropic.claude-3-7-sonnet..."
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'active', -- active, archived, expired
    extra_data JSONB DEFAULT '{}'::jsonb   -- Additional session data
);

-- User requests within a chat (execution plans)
CREATE TABLE plans (
    id VARCHAR(50) PRIMARY KEY,          -- UUID from agent
    chat_id VARCHAR(50) NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,               -- Plan description
    status VARCHAR(20) NOT NULL,         -- new, in_progress, completed, failed
    user_query TEXT NOT NULL,            -- Original user question
    model_id VARCHAR(100),               -- Model used for this plan
    temperature DECIMAL(3,2),            -- LLM temperature setting
    total_actions INTEGER DEFAULT 0,     -- Count of actions in plan
    completed_actions INTEGER DEFAULT 0, -- Count of completed actions
    failed_actions INTEGER DEFAULT 0,    -- Count of failed actions
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    execution_duration_ms INTEGER,       -- Total execution time
    extra_data JSONB DEFAULT '{}'::jsonb   -- Additional plan data
);

-- Individual actions within a plan
CREATE TABLE actions (
    id VARCHAR(50) PRIMARY KEY,          -- UUID from plan
    plan_id VARCHAR(50) NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,          -- "Create PDF with ARIS description"
    description TEXT,                    -- Detailed description
    type VARCHAR(20) NOT NULL,           -- tool_call, analysis, response, clarification
    tool_name VARCHAR(100),              -- create_pdf, search_memory, etc.
    arguments JSONB,                     -- Tool arguments
    depends_on JSONB DEFAULT '[]'::jsonb, -- Array of dependency action IDs
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, starting, in_progress, completed, failed
    result JSONB,                        -- Tool execution result
    error_message TEXT,                  -- If failed
    execution_order INTEGER,             -- Order of execution within plan
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    execution_duration_ms INTEGER,       -- Action execution time
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Session memory for tool results and persistent data
CREATE TABLE session_memory (
    id BIGSERIAL PRIMARY KEY,
    chat_id VARCHAR(50) NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    memory_key VARCHAR(255) NOT NULL,    -- "tool_result_action_id", "current_execution_plan"
    tool_name VARCHAR(100),              -- create_pdf, get_fake_data, etc.
    tags JSONB DEFAULT '[]'::jsonb,      -- ["pdf", "file", "manufacturing"]
    value JSONB NOT NULL,                -- Actual stored data
    size_bytes INTEGER,                  -- Data size for monitoring
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE, -- For automatic cleanup
    access_count INTEGER DEFAULT 0,      -- Usage tracking
    last_accessed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for optimal performance
CREATE INDEX idx_chats_user_activity ON chats(user_id, last_activity_at DESC);
CREATE INDEX idx_chats_status ON chats(status) WHERE status = 'active';

CREATE INDEX idx_plans_chat_created ON plans(chat_id, created_at DESC);
CREATE INDEX idx_plans_status ON plans(status);
CREATE INDEX idx_plans_user_query_fts_english ON plans USING gin(to_tsvector('english', user_query));

CREATE INDEX idx_actions_plan_order ON actions(plan_id, execution_order);
CREATE INDEX idx_actions_tool_status ON actions(tool_name, status);
CREATE INDEX idx_actions_type_status ON actions(type, status);
CREATE INDEX idx_actions_depends_on ON actions USING gin(depends_on);

CREATE INDEX idx_memory_chat_key ON session_memory(chat_id, memory_key);
CREATE INDEX idx_memory_tool_created ON session_memory(tool_name, created_at DESC);
CREATE INDEX idx_memory_tags ON session_memory USING gin(tags);
CREATE INDEX idx_memory_expires ON session_memory(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_memory_value_file_search ON session_memory USING gin((value->'file_url')) WHERE value ? 'file_url';

-- Add unique constraint for memory keys per chat
ALTER TABLE session_memory ADD CONSTRAINT uk_chat_memory_key UNIQUE (chat_id, memory_key);

-- Add check constraints
ALTER TABLE chats ADD CONSTRAINT chk_chats_status 
    CHECK (status IN ('active', 'archived', 'expired'));

ALTER TABLE plans ADD CONSTRAINT chk_plans_status 
    CHECK (status IN ('new', 'in_progress', 'completed', 'failed', 'cancelled'));

ALTER TABLE actions ADD CONSTRAINT chk_actions_status 
    CHECK (status IN ('pending', 'starting', 'in_progress', 'completed', 'failed', 'cancelled'));

ALTER TABLE actions ADD CONSTRAINT chk_actions_type 
    CHECK (type IN ('tool_call', 'analysis', 'response', 'clarification'));

-- Add triggers for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_chats_updated_at 
    BEFORE UPDATE ON chats 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_plans_updated_at 
    BEFORE UPDATE ON plans 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_memory_updated_at 
    BEFORE UPDATE ON session_memory 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to update chat activity timestamp
CREATE OR REPLACE FUNCTION update_chat_activity()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE chats SET last_activity_at = NOW() WHERE id = NEW.chat_id;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_chat_activity_on_plan 
    AFTER INSERT OR UPDATE ON plans 
    FOR EACH ROW EXECUTE FUNCTION update_chat_activity();

CREATE TRIGGER update_chat_activity_on_memory 
    AFTER INSERT OR UPDATE ON session_memory 
    FOR EACH ROW EXECUTE FUNCTION update_chat_activity();

-- Create views for common queries
CREATE VIEW active_chats AS
SELECT 
    c.*,
    COUNT(p.id) as total_plans,
    MAX(p.created_at) as latest_plan_at
FROM chats c
LEFT JOIN plans p ON c.id = p.chat_id
WHERE c.status = 'active'
GROUP BY c.id, c.user_id, c.agent_type, c.model_id, 
         c.created_at, c.updated_at, c.last_activity_at, c.status, c.extra_data;

CREATE VIEW plan_summary AS
SELECT 
    p.id,
    p.chat_id,
    p.summary,
    p.status,
    p.user_query,
    p.model_id,
    p.temperature,
    p.created_at,
    p.started_at,
    p.completed_at,
    p.execution_duration_ms,
    p.extra_data,
    COUNT(a.id) as actual_total_actions,
    COUNT(CASE WHEN a.status = 'completed' THEN 1 END) as actual_completed_actions,
    COUNT(CASE WHEN a.status = 'failed' THEN 1 END) as actual_failed_actions,
    AVG(a.execution_duration_ms) as avg_action_duration_ms
FROM plans p
LEFT JOIN actions a ON p.id = a.plan_id
GROUP BY p.id, p.chat_id, p.summary, p.status, p.user_query, p.model_id, 
         p.temperature, p.created_at, p.started_at, p.completed_at, 
         p.execution_duration_ms, p.extra_data;

-- Add table and column comments for documentation
COMMENT ON TABLE chats IS 'Core chat sessions with user information and metadata';
COMMENT ON TABLE plans IS 'Execution plans representing user requests within chats';
COMMENT ON TABLE actions IS 'Individual actions/steps within execution plans';
COMMENT ON TABLE session_memory IS 'Persistent session memory for tool results and data storage';

COMMENT ON COLUMN session_memory.memory_key IS 'Unique key for memory item within chat session';
COMMENT ON COLUMN session_memory.tags IS 'JSONB array of tags for categorization and search';
COMMENT ON COLUMN session_memory.value IS 'JSONB storage for any tool result or session data';
COMMENT ON COLUMN actions.depends_on IS 'JSONB array of action IDs that must complete before this action';
COMMENT ON COLUMN actions.arguments IS 'JSONB storage for tool arguments and parameters';

-- Create a function for cleanup of expired sessions
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Delete expired memory entries
    DELETE FROM session_memory WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    -- Archive old inactive chats (older than 90 days)
    UPDATE chats 
    SET status = 'archived' 
    WHERE status = 'active' 
      AND last_activity_at < NOW() - INTERVAL '90 days';
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions (if needed for specific user)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO aris;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO aris;
