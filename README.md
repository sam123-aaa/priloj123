# Maintenance API

Maintenance API - это учебный проект для автоматизации процесса технического обслуживания оборудования. В проект входит FastAPI backend, web-интерфейс, мобильный клиент, desktop-клиент, очередь фоновых задач, аудит действий, RBAC-доступ по ролям и защитные механизмы для демонстрации безопасности приложения.

Проект показывает полный цикл работы: сбор измерений, появление отказов, работа технического эксперта, создание рекомендаций, планирование работ диспетчером, выполнение задач механиком, контроль качества и формирование отчетов.

## Состав проекта

- `main.py` - основное FastAPI-приложение, HTTP endpoints, BFF endpoints, middleware, security headers, CSRF и rate limit.
- `schemas.py` - DTO-схемы Pydantic. Лишние поля запрещены через `extra="forbid"`, что защищает от mass assignment.
- `services/commands.py` - командная часть CQRS: создание измерений, отказов, рекомендаций, планов, задач и отчетов.
- `services/queries.py` - query-часть CQRS: чтение дашбордов, списков, отчетов, мониторинга и задач.
- `services/cache.py` - read-cache для быстрых GET/BFF-ответов с инвалидацией после изменений.
- `services/security.py` - CSRF-токены и безопасные имена файлов для скачивания отчетов.
- `services/login_protection.py` - защита входа от перебора пароля.
- `services/admin_security.py` - защита админских операций: смена роли, блокировка аккаунта, last admin guard.
- `dependencies.py` - получение пользователя из токена, кеширование токена, проверка ролей.
- `rbac.py` - простая ролевая проверка доступа.
- `supabase_auth.py` - вход и refresh через Supabase Auth.
- `workers.py` - Celery worker для фонового формирования отчетов.
- `queue_app.py` - настройка Celery/Redis.
- `audit.py` - запись действий пользователей и команд в журнал транзакций.
- `observability.py` - метрики запросов, длительности, ошибок и hot points.
- `clients/desktop_pyside/` - desktop-клиент на PySide6.
- `clients/mobile_kivy/` и `clients/mobile_app/` - мобильные клиенты.
- `clients/web/` и `frontend/` - web/static frontend.
- `presentation_workspace/output/` - итоговые материалы: презентация, SAD и отчет.

## Роли пользователей

В проекте используется RBAC-модель. Основные роли:

- `admin` - администрирование пользователей, ролей, метрик и системных данных.
- `manager` - просмотр web-дашборда, шаблонов и отчетов.
- `metrologist` - отправка измерений оборудования.
- `tech_expert` - просмотр отказов, подтверждение отказов, создание рекомендаций.
- `dispatcher_specialist` - работа с рекомендациями и создание планов обслуживания.
- `mechanic` - получение, старт, завершение и отмена задач.
- `quality_engineer` - контроль качества выполненных задач.

## Архитектура

Проект построен вокруг backend на FastAPI. Клиенты не работают напрямую с базой данных, а обращаются к API.

```text
Web / Mobile / Desktop
        |
        v
FastAPI API + BFF endpoints
        |
        v
Services: commands / queries / cache / audit
        |
        v
Supabase Postgres + Redis/Celery
```

### CQRS

Проект разделяет операции чтения и записи:

- command-слой изменяет состояние системы;
- query-слой читает подготовленные данные для экранов и списков;
- после команд read-cache инвалидируется, чтобы пользователь видел актуальные данные.

### Очереди

Формирование отчетов вынесено в фоновые задачи:

- API создает задачу;
- Celery worker обрабатывает ее через Redis;
- статус задачи хранится в Redis и read-model таблицах;
- готовый документ доступен через endpoint отчета.

## Быстрый запуск backend

1. Создать `.env` на основе `.env.example`.

```powershell
copy .env.example .env
```

2. Заполнить значения базы данных, Supabase и Redis.

3. Установить зависимости.

```powershell
.\.venv_win\Scripts\python.exe -m pip install -r requirements.txt
```

4. Применить SQL-схему.

```powershell
psql "postgresql://%DB_USER%:%DB_PASSWORD%@%DB_HOST%:%DB_PORT%/%DB_NAME%" -f setup_rbac_cqrs_queue.sql
```

5. Запустить API локально.

```powershell
.\.venv_win\Scripts\uvicorn.exe main:app --host 127.0.0.1 --port 8000
```

6. Для доступа из локальной сети запускать backend так:

```powershell
.\.venv_win\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000
```

Swagger UI доступен по адресу:

```text
http://127.0.0.1:8000/docs
```

## Запуск Celery worker

Для фонового формирования отчетов нужен Redis и worker:

```powershell
.\.venv_win\Scripts\celery.exe -A workers.celery_app worker --loglevel=info
```

Если Redis внешний, его адрес задается через:

```text
REDIS_URL
CELERY_BROKER_URL
CELERY_RESULT_BACKEND
```

## Запуск desktop-клиента

Desktop-клиент находится в:

```text
clients/desktop_pyside/main.py
```

Запуск:

```powershell
cd "D:\куцебо апи\PythonProject1"
.\.venv_win\Scripts\pythonw.exe clients\desktop_pyside\main.py
```

На экране входа есть поле `API`. По умолчанию:

```text
http://127.0.0.1:8000
```

Если backend запущен на другом компьютере в локальной сети, нужно указать IP этого компьютера:

```text
http://192.168.1.25:8000
```

Важно: backend при этом должен быть запущен с `--host 0.0.0.0`, а порт `8000` должен быть открыт в firewall.

## Сборка desktop в EXE

Для сборки используется PyInstaller:

```powershell
.\.venv_win\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name MaintenanceDesktop clients\desktop_pyside\main.py
```

Итоговый файл появляется здесь:

```text
dist/MaintenanceDesktop.exe
```

Готовый EXE можно положить в:

```text
D:\куцебо апи\готовые\ексе
```

## Статический frontend

Папка `frontend/` содержит простой статический web-клиент:

- `index.html` - стартовая страница;
- `web.html` - web/manager клиент;
- `mobile.html` - мобильный web-экран;
- `desktop.html` - desktop web-мониторинг;
- `app.js` - общая логика;
- `styles.css` - стили.

Frontend можно открыть как статические файлы или загрузить на хостинг. Backend URL задается в интерфейсе и сохраняется в `localStorage`.

## Основные API endpoints

### Auth

- `POST /login` - вход пользователя.
- `POST /auth/refresh` - обновление токена.
- `GET /csrf-token` - получение CSRF-токена для browser-запросов.

### Metrologist

- `POST /metrolog/collect-data` - отправка измерений.

### Tech expert

- `GET /expert/faults` - список отказов.
- `POST /expert/confirm` - подтверждение отказов.
- `POST /expert/recommendation` - создание рекомендации.

### Dispatcher

- `GET /specialist/recommendations` - список рекомендаций.
- `POST /specialist/create-plan` - создание плана обслуживания.

### Mechanic

- `GET /mechanic/tasks` - список задач механика.
- `POST /mechanic/start/{task_id}` - старт задачи.
- `POST /mechanic/finish/{task_id}` - завершение задачи.
- `POST /mechanic/cancel/{task_id}` - отмена задачи.

### Quality

- `GET /quality/tasks` - задачи для контроля качества.
- `POST /quality/check/{task_id}` - результат проверки качества.

### Reports

- `POST /reports/generate` - формирование отчета.
- `POST /reports/generate-delayed` - отложенное формирование отчета.
- `GET /reports/status/{task_id}` - статус задачи отчета.
- `GET /reports/jobs` - очередь отчетов.
- `GET /reports/document/{task_id}` - скачивание готового документа.

### BFF

- `/bff/web/*` - endpoints для web-клиента.
- `/bff/mobile/*` - endpoints для мобильного клиента.
- `/bff/desktop/*` - endpoints для desktop-клиента.

### Observability

- `GET /observability/metrics` - метрики запросов.
- `GET /observability/hot-points` - горячие точки по ошибкам, нагрузке и длительности.

### Admin security

- `GET /api/users` - список пользователей.
- `GET /api/roles` - список ролей.
- `POST /api/users/{user_id}/account-status` - блокировка/разблокировка аккаунта.
- `POST /api/users/{user_id}/role` - изменение роли пользователя.

## Безопасность

В проект добавлены основные механизмы защиты web/API:

- JWT/Supabase token auth.
- RBAC-проверка ролей через `require_role`.
- Strict DTO validation через Pydantic.
- Запрет лишних полей в request body.
- Защита от mass assignment.
- SQL-запросы выполняются через bound parameters.
- CORS whitelist через `ALLOWED_CORS_ORIGINS`.
- Security headers: CSP, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`.
- `Cache-Control: no-store` для `/login` и `/auth/refresh`.
- Rate limit через `SECURITY_RATE_LIMIT_PER_MINUTE`.
- Brute force protection для `/login` через `LOGIN_BRUTEFORCE_MAX_ATTEMPTS` и `LOGIN_BRUTEFORCE_BLOCK_SECONDS`.
- CSRF-защита для browser-запросов через `/csrf-token`, cookie и `X-CSRF-Token`.
- Проверка `Origin` и `Referer` для unsafe HTTP-методов.
- Защита от XSS/CSS-инъекций через validators в `schemas.py`.
- Safe filename для отчетов: запрещены remote URLs, абсолютные пути, `..` и null bytes.
- IDOR-защита: данные читаются и меняются с учетом пользователя из токена, а не из тела запроса.
- Audit logging важных действий и отказов доступа.
- Admin actions требуют пароль администратора и защищены от потери последнего активного admin.
- Production config validation: запрещены wildcard CORS, localhost origins и слабый `LOCAL_JWT_SECRET`.

## Проверки безопасности для демонстрации

Эти сценарии удобно показывать через Swagger или HTTP-клиент:

1. Mass assignment:

   Отправить лишние поля вроде `is_admin`, `role`, `owner_id` в body. API должен вернуть `422`.

2. XSS:

   Отправить `<script>alert(1)</script>` или `javascript:alert(1)` в текстовое поле. API должен вернуть `422`.

3. CSRF:

   Отправить unsafe-запрос с чужим `Origin`. API должен вернуть `403`.

4. CSRF double submit:

   Получить `/csrf-token`, затем отправить unsafe-запрос с cookie, но без `X-CSRF-Token`. API должен вернуть `403`.

5. IDOR:

   Обычный пользователь пытается получить чужой отчет или задачу. API должен вернуть `403` или `404`.

6. RBAC:

   Пользователь без роли `admin` вызывает `/observability/metrics` или `/api/users`. API должен вернуть `403`.

7. Last admin guard:

   Попытаться отключить последнего активного администратора. API должен вернуть `409`.

8. Brute force:

   Несколько раз отправить неверный пароль на `/login`. После лимита API должен вернуть `429`.

9. RFI/LFI:

   Проверить имена файлов `../../.env`, `C:\Windows\win.ini`, `https://evil.example/file`. API должен отклонить unsafe filename.

## Переменные окружения

Основные переменные:

- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSLMODE` - подключение к Supabase Postgres.
- `DATABASE_URL` - SQLAlchemy URL, если используется.
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` - Supabase Auth.
- `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` - Redis/Celery.
- `ALLOWED_CORS_ORIGINS` - разрешенные frontend origins.
- `CSRF_TRUSTED_ORIGINS` - origins, разрешенные для browser-запросов.
- `LOCAL_JWT_SECRET` - секрет для local fallback JWT.
- `SECURITY_RATE_LIMIT_PER_MINUTE` - общий лимит запросов.
- `LOGIN_BRUTEFORCE_MAX_ATTEMPTS` - число неверных попыток входа до блокировки.
- `LOGIN_BRUTEFORCE_BLOCK_SECONDS` - длительность блокировки входа.
- `ALLOW_LOCAL_AUTH_FALLBACK` - разрешение локального fallback-входа при недоступном Supabase.

## Observability

Система собирает:

- количество запросов;
- статусы ответов;
- длительность запросов;
- количество записей в ответах;
- hot points по ошибкам, медленным endpoint-ам и высокой нагрузке.

Это помогает показать, где приложение работает медленно, где чаще возникают ошибки и какие endpoint-ы самые активные.

## Материалы проекта

Итоговые документы лежат в:

```text
presentation_workspace/output/
```

Там находятся:

- презентация проекта;
- SAD-документ;
- итоговый отчет.

## Git workflow

Рекомендуемый процесс:

- `main` - стабильная ветка.
- `develop` - интеграционная ветка.
- `feature/<task-name>` - ветка для отдельной задачи.

Примеры commit message:

- `feat: add desktop client`
- `fix: handle invalid token`
- `security: harden login protection`
- `docs: update project documentation`

## Проверка перед сдачей

```powershell
.\.venv_win\Scripts\python.exe -m compileall .
.\.venv_win\Scripts\uvicorn.exe main:app --host 127.0.0.1 --port 8000
.\.venv_win\Scripts\celery.exe -A workers.celery_app worker --loglevel=info
```

После запуска проверить:

- `/docs`;
- вход через `/login`;
- работу desktop-клиента;
- работу mobile/web endpoints;
- генерацию отчета;
- `/observability/hot-points`;
- security-сценарии из `SECURITY_CHECKLIST.md`.

## Кратко для защиты

Проект демонстрирует backend и клиентские приложения для процесса обслуживания оборудования. В нем реализованы RBAC, CQRS, Redis/Celery очередь, аудит действий, BFF endpoints для разных клиентов, генерация отчетов и набор защитных механизмов: JWT/Supabase auth, CORS whitelist, CSP/security headers, CSRF, rate limit, brute force protection, строгая валидация DTO, IDOR-проверки и защита скачивания файлов.
