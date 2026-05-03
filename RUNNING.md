1. Check `.env` and update credentials if needed.

2. Apply SQL schema:
   `psql "postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME" -f setup_rbac_cqrs_queue.sql`

3. Install dependencies:
   `./.venv/bin/pip install -r requirements.txt`

4. Start Redis:
   `redis-server`

5. Start API:
   `./.venv/bin/uvicorn main:app --reload`

6. Start worker:
   `./.venv/bin/celery -A workers.celery_app worker --loglevel=info`
