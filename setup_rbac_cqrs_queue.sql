DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
        CREATE TYPE user_role AS ENUM (
            'dispatcher_specialist',
            'metrologist',
            'quality_engineer',
            'manager',
            'mechanic',
            'tech_expert',
            'admin'
        );
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
        BEGIN
            ALTER TYPE user_role RENAME VALUE 'specialist' TO 'dispatcher_specialist';
        EXCEPTION WHEN invalid_parameter_value THEN
            NULL;
        END;
        BEGIN
            ALTER TYPE user_role RENAME VALUE 'metrolog' TO 'metrologist';
        EXCEPTION WHEN invalid_parameter_value THEN
            NULL;
        END;
        BEGIN
            ALTER TYPE user_role RENAME VALUE 'quality' TO 'quality_engineer';
        EXCEPTION WHEN invalid_parameter_value THEN
            NULL;
        END;
        BEGIN
            ALTER TYPE user_role RENAME VALUE 'reporter' TO 'manager';
        EXCEPTION WHEN invalid_parameter_value THEN
            NULL;
        END;
        BEGIN
            ALTER TYPE user_role RENAME VALUE 'expert' TO 'tech_expert';
        EXCEPTION WHEN invalid_parameter_value THEN
            NULL;
        END;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS auth_users (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL
);

DROP TABLE IF EXISTS user_roles;

CREATE TABLE IF NOT EXISTS user_roles (
    user_id INTEGER NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

INSERT INTO roles (code, name)
VALUES
    ('dispatcher_specialist', 'Специалист по диспетчеризации'),
    ('metrologist', 'Метролог'),
    ('quality_engineer', 'Инженер контроля качества'),
    ('manager', 'Менеджер'),
    ('mechanic', 'Механик'),
    ('tech_expert', 'Техник-эксперт'),
    ('admin', 'Администратор')
ON CONFLICT (code) DO UPDATE
SET name = EXCLUDED.name;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_class WHERE oid = to_regclass('public.users') AND relkind = 'r') THEN
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS role user_role;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_class WHERE oid = to_regclass('public.users') AND relkind = 'r') AND EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'users'
          AND column_name = 'role_id'
    ) THEN
        EXECUTE $update_roles$
            UPDATE users
            SET role = CASE role_id
                WHEN 1 THEN 'dispatcher_specialist'::user_role
                WHEN 2 THEN 'metrologist'::user_role
                WHEN 3 THEN 'quality_engineer'::user_role
                WHEN 4 THEN 'manager'::user_role
                WHEN 5 THEN 'mechanic'::user_role
                WHEN 6 THEN 'tech_expert'::user_role
                WHEN 7 THEN 'admin'::user_role
                ELSE 'mechanic'::user_role
            END
            WHERE role IS NULL
        $update_roles$;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_class WHERE oid = to_regclass('public.users') AND relkind = 'r') THEN
        ALTER TABLE users
            ALTER COLUMN role SET DEFAULT 'mechanic';

        ALTER TABLE users
            DROP CONSTRAINT IF EXISTS fk_users_role_id;

        ALTER TABLE users
            DROP COLUMN IF EXISTS role_id;

        INSERT INTO auth_users (id, email, password_hash, full_name, created_at)
        SELECT id, email, password_hash, NULL::text, NOW()
        FROM users
        ON CONFLICT (id) DO UPDATE
        SET email = EXCLUDED.email,
            password_hash = EXCLUDED.password_hash,
            full_name = EXCLUDED.full_name;

        INSERT INTO user_roles (user_id, role_id)
        SELECT u.id, r.id
        FROM users u
        JOIN roles r ON r.code = COALESCE(u.role::text, 'mechanic')
        ON CONFLICT (user_id, role_id) DO NOTHING;
    END IF;
END $$;

DO $$
DECLARE
    users_relkind CHAR;
BEGIN
    SELECT relkind INTO users_relkind
    FROM pg_class
    WHERE oid = to_regclass('public.users');

    IF users_relkind = 'v' THEN
        DROP VIEW users;
    ELSIF users_relkind = 'r' THEN
        DROP TABLE users CASCADE;
    END IF;
END $$;

CREATE VIEW users AS
SELECT
    au.id,
    au.email,
    au.full_name,
    r.code AS role,
    au.created_at
FROM auth_users au
LEFT JOIN user_roles ur ON ur.user_id = au.id
LEFT JOIN roles r ON r.id = ur.role_id;

ALTER TABLE measurements ADD COLUMN IF NOT EXISTS owner_id INTEGER;
ALTER TABLE faults ADD COLUMN IF NOT EXISTS owner_id INTEGER;
ALTER TABLE maintenance_recommendations ADD COLUMN IF NOT EXISTS owner_id INTEGER;
ALTER TABLE maintenance_recommendations ADD COLUMN IF NOT EXISTS created_by INTEGER;
ALTER TABLE maintenance_plan ADD COLUMN IF NOT EXISTS owner_id INTEGER;
ALTER TABLE maintenance_tasks ADD COLUMN IF NOT EXISTS owner_id INTEGER;
ALTER TABLE quality_checks ADD COLUMN IF NOT EXISTS owner_id INTEGER;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS owner_id INTEGER;

UPDATE measurements SET owner_id = COALESCE(owner_id, recorded_by);
UPDATE faults SET owner_id = COALESCE(owner_id, confirmed_by);
UPDATE maintenance_recommendations SET owner_id = COALESCE(owner_id, created_by);
UPDATE maintenance_plan SET owner_id = COALESCE(owner_id, created_by);
UPDATE maintenance_tasks SET owner_id = COALESCE(owner_id, mechanic_id);
UPDATE quality_checks SET owner_id = COALESCE(owner_id, inspector_id);
UPDATE reports SET owner_id = COALESCE(owner_id, created_by);

CREATE INDEX IF NOT EXISTS idx_faults_owner_id ON faults(owner_id);
CREATE INDEX IF NOT EXISTS idx_measurements_owner_id ON measurements(owner_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_owner_id ON maintenance_recommendations(owner_id);
CREATE INDEX IF NOT EXISTS idx_plan_owner_id ON maintenance_plan(owner_id);
CREATE INDEX IF NOT EXISTS idx_tasks_owner_id ON maintenance_tasks(owner_id);
CREATE INDEX IF NOT EXISTS idx_reports_owner_id ON reports(owner_id);

ALTER TABLE transactions
    ADD COLUMN IF NOT EXISTS role_code TEXT;

UPDATE transactions t
SET role_code = r.code
FROM auth_users au
JOIN user_roles ur ON ur.user_id = au.id
JOIN roles r ON r.id = ur.role_id
WHERE t.user_id = au.id
  AND t.role_code IS NULL;

ALTER TABLE transactions
    DROP COLUMN IF EXISTS role_id;

CREATE TABLE IF NOT EXISTS background_jobs (
    id UUID PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    owner_id INTEGER NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    result JSONB NULL,
    started_at TIMESTAMP NULL,
    finished_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS domain_events (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS idx_domain_events_status_created_at
    ON domain_events(status, created_at);

CREATE TABLE IF NOT EXISTS report_read_model (
    job_id UUID PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    report_type TEXT NOT NULL,
    status TEXT NOT NULL,
    generated_at TIMESTAMP NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_report_read_model_owner_id
    ON report_read_model(owner_id);

CREATE TABLE IF NOT EXISTS report_documents (
    job_id UUID PRIMARY KEY REFERENCES report_read_model(job_id) ON DELETE CASCADE,
    owner_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    file_name TEXT NOT NULL DEFAULT 'report.docx',
    content_type TEXT NOT NULL DEFAULT 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    html_content TEXT NOT NULL,
    file_content BYTEA NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE report_documents
    ADD COLUMN IF NOT EXISTS file_name TEXT NOT NULL DEFAULT 'report.docx';

ALTER TABLE report_documents
    ALTER COLUMN content_type
    SET DEFAULT 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

ALTER TABLE report_documents
    ADD COLUMN IF NOT EXISTS file_content BYTEA NULL;

CREATE INDEX IF NOT EXISTS idx_report_documents_owner_id
    ON report_documents(owner_id);

CREATE TABLE IF NOT EXISTS report_templates (
    id BIGSERIAL PRIMARY KEY,
    template_name TEXT NOT NULL UNIQUE,
    report_type TEXT NOT NULL,
    description TEXT NOT NULL,
    default_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO report_templates (template_name, report_type, description, default_payload)
VALUES
    ('Ежедневный сводный отчёт', 'daily-overview', 'Сводка по оборудованию, fault и задачам за день', '{"period":"day"}'::jsonb),
    ('Отчёт по качеству', 'quality-summary', 'Сводка по проверкам качества и завершённым задачам', '{"scope":"quality"}'::jsonb),
    ('Отчёт по неисправностям', 'fault-analysis', 'Анализ открытых и обработанных неисправностей', '{"scope":"faults"}'::jsonb)
ON CONFLICT (template_name) DO UPDATE
SET report_type = EXCLUDED.report_type,
    description = EXCLUDED.description,
    default_payload = EXCLUDED.default_payload,
    is_active = TRUE;
