import { Presentation, PresentationFile, row, column, grid, panel, text, rule, fill, hug, fixed, wrap, grow, fr } from '@oai/artifact-tool';

const W = 1920;
const H = 1080;
const C = {
  bg: '#F6F8FB',
  ink: '#172033',
  muted: '#65738A',
  blue: '#2563EB',
  blue2: '#DBEAFE',
  green: '#059669',
  green2: '#D1FAE5',
  orange: '#EA580C',
  orange2: '#FFEDD5',
  line: '#D8E0EC',
  dark: '#111827',
  white: '#FFFFFF',
};

const titleStyle = { fontSize: 54, bold: true, color: C.ink, fontFace: 'Calibri' };
const h2 = { fontSize: 34, bold: true, color: C.ink, fontFace: 'Calibri' };
const body = { fontSize: 25, color: C.muted, fontFace: 'Calibri' };
const small = { fontSize: 20, color: C.muted, fontFace: 'Calibri' };
const caption = { fontSize: 20, italic: true, color: '#475569', fontFace: 'Calibri' };

function bgRoot(child) {
  return panel({ name: 'slide-bg', width: fill, height: fill, fill: C.bg, padding: { x: 88, y: 68 } }, child);
}

function heading(num, title, subtitle) {
  return column({ name: `heading-${num}`, width: fill, height: hug, gap: 10 }, [
    text(num, { width: fill, height: hug, style: { fontSize: 18, bold: true, color: C.blue, fontFace: 'Calibri' } }),
    text(title, { width: fill, height: hug, style: titleStyle }),
    subtitle ? text(subtitle, { width: wrap(1280), height: hug, style: body }) : null,
    rule({ width: fixed(180), stroke: C.blue, weight: 5 }),
  ].filter(Boolean));
}

function bullet(label, detail, color = C.blue2) {
  return row({ width: fill, height: hug, gap: 18, alignItems: 'center' }, [
    panel({ width: fixed(18), height: fixed(18), fill: color, borderRadius: 999 }, text('', { width: fixed(1), height: fixed(1), style: { fontSize: 1 } })),
    column({ width: fill, height: hug, gap: 4 }, [
      text(label, { width: fill, height: hug, style: { fontSize: 25, bold: true, color: C.ink, fontFace: 'Calibri' } }),
      text(detail, { width: fill, height: hug, style: small }),
    ]),
  ]);
}

function chip(label, fillColor, color = C.ink) {
  return panel({ width: hug, height: hug, fill: fillColor, padding: { x: 16, y: 8 }, borderRadius: 999 },
    text(label, { width: hug, height: hug, style: { fontSize: 18, bold: true, color, fontFace: 'Calibri' } }));
}

function uiTopBar(title, color = C.blue) {
  return row({ width: fill, height: fixed(54), gap: 12, alignItems: 'center' }, [
    panel({ width: fixed(14), height: fixed(14), fill: '#EF4444', borderRadius: 999 }, text('', { width: fixed(1), height: fixed(1), style: { fontSize: 1 } })),
    panel({ width: fixed(14), height: fixed(14), fill: '#F59E0B', borderRadius: 999 }, text('', { width: fixed(1), height: fixed(1), style: { fontSize: 1 } })),
    panel({ width: fixed(14), height: fixed(14), fill: '#10B981', borderRadius: 999 }, text('', { width: fixed(1), height: fixed(1), style: { fontSize: 1 } })),
    text(title, { width: fill, height: hug, style: { fontSize: 19, bold: true, color, fontFace: 'Calibri' } }),
  ]);
}

function simpleTable(headers, rowsData) {
  const rowNodes = rowsData.map((r, idx) => row({ width: fill, height: fixed(46), gap: 0 }, r.map((cell, i) =>
    panel({ width: i === 0 ? fixed(135) : fill, height: fill, fill: idx % 2 ? '#F8FAFC' : '#FFFFFF', padding: { x: 12, y: 10 }, stroke: C.line, strokeWidth: 1 },
      text(cell, { width: fill, height: hug, style: { fontSize: 17, color: C.ink, fontFace: 'Calibri' } }))
  )));
  return column({ width: fill, height: hug, gap: 0 }, [
    row({ width: fill, height: fixed(46), gap: 0 }, headers.map((cell, i) =>
      panel({ width: i === 0 ? fixed(135) : fill, height: fill, fill: '#EAF2FF', padding: { x: 12, y: 10 }, stroke: C.line, strokeWidth: 1 },
        text(cell, { width: fill, height: hug, style: { fontSize: 17, bold: true, color: C.ink, fontFace: 'Calibri' } }))
    )),
    ...rowNodes,
  ]);
}

function addSlide(presentation, content) {
  const slide = presentation.slides.add();
  slide.compose(bgRoot(content), { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 });
  return slide;
}

const p = Presentation.create({ slideSize: { width: W, height: H } });

// 1. Title
addSlide(p,
  grid({ width: fill, height: fill, columns: [fr(1.05), fr(0.95)], rows: [fr(1)], columnGap: 72 }, [
    column({ width: fill, height: fill, gap: 30, justifyContent: 'center' }, [
      chip('Учебный проект', C.blue2, C.blue),
      text('Maintenance API', { width: wrap(760), height: hug, style: { fontSize: 76, bold: true, color: C.ink, fontFace: 'Calibri' } }),
      text('Система обслуживания оборудования с API, очередью задач и защитой backend-части.', { width: wrap(780), height: hug, style: { fontSize: 30, color: C.muted, fontFace: 'Calibri' } }),
      row({ width: fill, height: hug, gap: 14 }, [chip('FastAPI', '#E0F2FE', '#0369A1'), chip('PostgreSQL', C.green2, C.green), chip('Redis/Celery', C.orange2, C.orange)]),
      text('Презентация по проекту • 2026', { width: fill, height: hug, style: small }),
    ]),
    panel({ width: fill, height: fill, fill: C.white, borderRadius: 30, padding: 40, stroke: C.line, strokeWidth: 2 },
      column({ width: fill, height: fill, gap: 24, justifyContent: 'center' }, [
        text('Основной смысл проекта', { width: fill, height: hug, style: h2 }),
        bullet('Сбор данных', 'Метрололог передает измерения по компонентам оборудования.', '#BFDBFE'),
        bullet('Обработка неисправностей', 'Эксперт подтверждает fault и создает рекомендации.', '#BBF7D0'),
        bullet('Планирование работ', 'Диспетчер формирует план, механик выполняет задачу.', '#FED7AA'),
        bullet('Контроль и отчеты', 'Проверка качества, очередь отчетов, аудит действий.', '#E9D5FF'),
      ]))
  ])
);

// 2. App description
addSlide(p,
  column({ width: fill, height: fill, gap: 34 }, [
    heading('02', 'Описание работы приложения', 'Приложение автоматизирует цепочку обслуживания: от измерения до отчета.'),
    row({ width: fill, height: fill, gap: 26 }, [
      panel({ width: fill, height: fill, fill: C.white, borderRadius: 22, padding: 30, stroke: C.line, strokeWidth: 2 }, column({ width: fill, height: fill, gap: 22 }, [
        bullet('1. Измерение', 'Метрололог отправляет параметр, значение и единицы измерения.', '#BFDBFE'),
        bullet('2. Fault', 'Система фиксирует неисправность и показывает ее эксперту.', '#FDE68A'),
        bullet('3. Recommendation', 'Эксперт подтверждает проблему и пишет рекомендацию.', '#BBF7D0'),
        bullet('4. Plan и task', 'Диспетчер создает план, механик берет задачу в работу.', '#FED7AA'),
        bullet('5. Quality и report', 'Проверка качества, генерация отчета через очередь.', '#DDD6FE'),
      ])),
      panel({ width: fixed(620), height: fill, fill: '#EEF6FF', borderRadius: 22, padding: 30, stroke: '#B7D5FF', strokeWidth: 2 }, column({ width: fill, height: fill, gap: 20 }, [
        text('Роли в системе', { width: fill, height: hug, style: h2 }),
        simpleTable(['Роль', 'Что делает'], [
          ['admin', 'управляет доступом'],
          ['manager', 'смотрит отчеты'],
          ['expert', 'подтверждает faults'],
          ['dispatcher', 'создает планы'],
          ['mechanic', 'выполняет задачи'],
          ['quality', 'проверяет результат'],
        ]),
      ])),
    ]),
  ])
);

// 3. Architecture
addSlide(p,
  column({ width: fill, height: fill, gap: 34 }, [
    heading('03', 'На чем написано и архитектура', 'Backend построен вокруг FastAPI, базы данных, очереди и отдельных клиентов.'),
    grid({ width: fill, height: fill, columns: [fr(1), fr(1), fr(1)], rows: [fr(1), fr(1)], columnGap: 24, rowGap: 24 }, [
      panel({ fill: C.white, borderRadius: 20, padding: 26, stroke: C.line, strokeWidth: 2 }, column({ gap: 12, width: fill, height: fill }, [text('FastAPI backend', { style: h2, width: fill, height: hug }), text('Маршруты, DTO, авторизация, RBAC, CSRF и security headers.', { style: body, width: fill, height: hug })])),
      panel({ fill: C.white, borderRadius: 20, padding: 26, stroke: C.line, strokeWidth: 2 }, column({ gap: 12, width: fill, height: fill }, [text('PostgreSQL / Supabase', { style: h2, width: fill, height: hug }), text('Основные таблицы: users, roles, faults, tasks, reports, transactions.', { style: body, width: fill, height: hug })])),
      panel({ fill: C.white, borderRadius: 20, padding: 26, stroke: C.line, strokeWidth: 2 }, column({ gap: 12, width: fill, height: fill }, [text('Redis + Celery', { style: h2, width: fill, height: hug }), text('Очередь фоновой генерации отчетов и статусы worker-задач.', { style: body, width: fill, height: hug })])),
      panel({ fill: C.white, borderRadius: 20, padding: 26, stroke: C.line, strokeWidth: 2 }, column({ gap: 12, width: fill, height: fill }, [text('CQRS', { style: h2, width: fill, height: hug }), text('commands.py меняет данные, queries.py читает списки и dashboard.', { style: body, width: fill, height: hug })])),
      panel({ fill: C.white, borderRadius: 20, padding: 26, stroke: C.line, strokeWidth: 2 }, column({ gap: 12, width: fill, height: fill }, [text('Security layer', { style: h2, width: fill, height: hug }), text('IDOR, mass assignment, XSS/CSS, CSRF, CORS, rate limit, last admin guard.', { style: body, width: fill, height: hug })])),
      panel({ fill: C.white, borderRadius: 20, padding: 26, stroke: C.line, strokeWidth: 2 }, column({ gap: 12, width: fill, height: fill }, [text('Clients', { style: h2, width: fill, height: hug }), text('Веб, мобильный и десктопный интерфейсы работают с одним API.', { style: body, width: fill, height: hug })])),
    ]),
  ])
);

// 4. Web UI
addSlide(p,
  column({ width: fill, height: fill, gap: 26 }, [
    heading('04', 'Веб-интерфейс', 'Одно окно веб-клиента для менеджера, эксперта, диспетчера и администратора.'),
    panel({ width: fill, height: fixed(650), fill: '#0F172A', borderRadius: 28, padding: 22 }, column({ width: fill, height: fill, gap: 12 }, [
      uiTopBar('clients/web/index.html', '#93C5FD'),
      row({ width: fill, height: fill, gap: 18 }, [
        panel({ width: fixed(250), height: fill, fill: '#111827', borderRadius: 18, padding: 22 }, column({ width: fill, height: fill, gap: 18 }, [
          text('Web Client', { width: fill, height: hug, style: { fontSize: 24, bold: true, color: C.white, fontFace: 'Calibri' } }),
          text('Dashboard\nReports\nFaults\nPlans\nAdmin Security', { width: fill, height: hug, style: { fontSize: 22, color: '#CBD5E1', fontFace: 'Calibri' } }),
        ])),
        column({ width: fill, height: fill, gap: 18 }, [
          row({ width: fill, height: fixed(120), gap: 18 }, [
            panel({ width: fill, height: fill, fill: C.blue2, borderRadius: 16, padding: 18 }, text('Open faults\n12', { width: fill, height: hug, style: { fontSize: 27, bold: true, color: C.blue, fontFace: 'Calibri' } })),
            panel({ width: fill, height: fill, fill: C.green2, borderRadius: 16, padding: 18 }, text('Reports\nReady', { width: fill, height: hug, style: { fontSize: 27, bold: true, color: C.green, fontFace: 'Calibri' } })),
            panel({ width: fill, height: fill, fill: C.orange2, borderRadius: 16, padding: 18 }, text('Rate limit\nEnabled', { width: fill, height: hug, style: { fontSize: 27, bold: true, color: C.orange, fontFace: 'Calibri' } })),
          ]),
          panel({ width: fill, height: fill, fill: C.white, borderRadius: 18, padding: 18 }, column({ width: fill, height: fill, gap: 14 }, [
            text('Report queue', { width: fill, height: hug, style: h2 }),
            simpleTable(['Job', 'Status', 'Owner'], [['R-104', 'queued', 'manager'], ['R-105', 'completed', 'admin'], ['R-106', 'worker', 'dispatcher']]),
          ])),
        ]),
      ]),
    ])),
    text('Рисунок 1. Веб-интерфейс: dashboard, очередь отчетов и админские проверки.', { width: fill, height: hug, style: caption }),
  ])
);

// 5. Mobile UI
addSlide(p,
  column({ width: fill, height: fill, gap: 24 }, [
    heading('05', 'Мобильный интерфейс', 'Мобильный клиент нужен для полевых ролей: механика, метролога и проверки качества.'),
    row({ width: fill, height: fixed(660), gap: 42, alignItems: 'center' }, [
      panel({ width: fixed(430), height: fill, fill: '#111827', borderRadius: 46, padding: 22 },
        panel({ width: fill, height: fill, fill: '#F8FAFC', borderRadius: 32, padding: 26 }, column({ width: fill, height: fill, gap: 20 }, [
          row({ width: fill, height: hug, gap: 10 }, [chip('Mobile Client', C.blue2, C.blue), chip('JWT', C.green2, C.green)]),
          text('Задачи механика', { width: fill, height: hug, style: { fontSize: 32, bold: true, color: C.ink, fontFace: 'Calibri' } }),
          panel({ width: fill, height: fixed(130), fill: C.white, borderRadius: 18, padding: 18, stroke: C.line, strokeWidth: 2 }, text('#42 Замена узла\nstatus: active\nequipment: Pump-7', { width: fill, height: hug, style: { fontSize: 21, color: C.ink, fontFace: 'Calibri' } })),
          panel({ width: fill, height: fixed(130), fill: C.white, borderRadius: 18, padding: 18, stroke: C.line, strokeWidth: 2 }, text('Сбор измерения\nparameter: temperature\nvalue: 55 C', { width: fill, height: hug, style: { fontSize: 21, color: C.ink, fontFace: 'Calibri' } })),
          panel({ width: fill, height: fixed(58), fill: C.blue, borderRadius: 14, padding: { x: 20, y: 14 } }, text('Отправить статус', { width: fill, height: hug, style: { fontSize: 21, bold: true, color: C.white, fontFace: 'Calibri' } })),
        ]))),
      column({ width: fill, height: hug, gap: 22 }, [
        bullet('Работа с задачами', 'Механик видит свои задачи и меняет статус: start, finish, cancel.', '#BFDBFE'),
        bullet('Сбор измерений', 'Метрололог отправляет данные по компонентам оборудования.', '#BBF7D0'),
        bullet('Контроль качества', 'Инженер качества фиксирует результат проверки.', '#FED7AA'),
        bullet('Безопасность', 'Клиент не решает права сам: backend проверяет роль и владельца.', '#DDD6FE'),
      ]),
    ]),
    text('Рисунок 2. Мобильный интерфейс: задачи, измерения и отправка статусов с телефона.', { width: fill, height: hug, style: caption }),
  ])
);

// 6. Desktop UI
addSlide(p,
  column({ width: fill, height: fill, gap: 24 }, [
    heading('06', 'Десктопный интерфейс', 'Десктопное окно используется как рабочая консоль мониторинга и обработки заявок.'),
    panel({ width: fill, height: fixed(660), fill: '#1F2937', borderRadius: 28, padding: 24 }, column({ width: fill, height: fill, gap: 16 }, [
      uiTopBar('Desktop Client • Monitoring Console', '#BFDBFE'),
      row({ width: fill, height: fill, gap: 18 }, [
        column({ width: fixed(330), height: fill, gap: 18 }, [
          panel({ width: fill, height: fixed(105), fill: '#374151', borderRadius: 16, padding: 18 }, text('Fault Feed\nLive', { width: fill, height: hug, style: { fontSize: 25, bold: true, color: C.white, fontFace: 'Calibri' } })),
          panel({ width: fill, height: fixed(105), fill: '#374151', borderRadius: 16, padding: 18 }, text('Queue Sync\n5 sec', { width: fill, height: hug, style: { fontSize: 25, bold: true, color: C.white, fontFace: 'Calibri' } })),
          panel({ width: fill, height: fixed(105), fill: '#374151', borderRadius: 16, padding: 18 }, text('Audit Mode\nEnabled', { width: fill, height: hug, style: { fontSize: 25, bold: true, color: C.white, fontFace: 'Calibri' } })),
        ]),
        panel({ width: fill, height: fill, fill: C.white, borderRadius: 18, padding: 22 }, column({ width: fill, height: fill, gap: 16 }, [
          text('Monitoring', { width: fill, height: hug, style: h2 }),
          simpleTable(['ID', 'Event', 'Result'], [['101', 'security_idor_denied', '403'], ['102', 'report_enqueued', 'queued'], ['103', 'admin_users_viewed', 'audit']]),
          row({ width: fill, height: hug, gap: 14 }, [chip('IDOR checks', C.blue2, C.blue), chip('Audit logs', C.green2, C.green), chip('Hot points', C.orange2, C.orange)]),
        ])),
      ]),
    ])),
    text('Рисунок 3. Десктопный интерфейс: мониторинг, очередь событий и audit-журнал.', { width: fill, height: hug, style: caption }),
  ])
);

await (await PresentationFile.exportPptx(p)).save('output/maintenance_api_presentation.pptx');
console.log('output/maintenance_api_presentation.pptx');
