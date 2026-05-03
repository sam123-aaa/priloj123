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
