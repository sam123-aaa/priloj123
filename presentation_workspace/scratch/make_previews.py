from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import textwrap
out = Path('scratch/previews'); out.mkdir(parents=True, exist_ok=True)
W,H=1280,720; BG=(246,248,251); INK=(23,32,51); MUTED=(101,115,138); BLUE=(37,99,235); LINE=(216,224,236); WHITE=(255,255,255)
font_path = r'C:\Windows\Fonts\arial.ttf'
font_bold_path = r'C:\Windows\Fonts\arialbd.ttf'
font_title=ImageFont.truetype(font_bold_path,48); font_h=ImageFont.truetype(font_bold_path,34); font_b=ImageFont.truetype(font_path,24); font_s=ImageFont.truetype(font_path,18)
def text_wrap(draw, xy, txt, font, fill, width_chars=48, line_gap=8):
    x,y=xy
    for para in txt.split('\n'):
        for line in textwrap.wrap(para, width_chars) or ['']:
            draw.text((x,y), line, font=font, fill=fill)
            y += font.size + line_gap
    return y
def rr(draw, box, fill, outline=None, radius=20, width=2): draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
def slide_base(num,title,subtitle=''):
    im=Image.new('RGB',(W,H),BG); d=ImageDraw.Draw(im); d.text((58,42), num, font=font_s, fill=BLUE); d.text((58,70), title, font=font_title, fill=INK)
    if subtitle: text_wrap(d,(58,132),subtitle,font_b,MUTED,70)
    d.line((58,188,180,188), fill=BLUE, width=5); return im,d
def save(idx,im): im.save(out/f'slide_{idx}.png')
# 1
im=Image.new('RGB',(W,H),BG); d=ImageDraw.Draw(im); d.text((72,190),'Maintenance API',font=font_title,fill=INK); text_wrap(d,(72,260),'Система обслуживания оборудования с API, очередью задач и защитой backend-части.',font_b,MUTED,42)
for i,(t,c) in enumerate([('FastAPI',(219,234,254)),('PostgreSQL',(209,250,229)),('Redis/Celery',(255,237,213))]): rr(d,(72+i*150,370,200+i*150,415),c,None,18); d.text((92+i*150,382),t,font=font_s,fill=INK)
rr(d,(680,90,1200,620),WHITE,LINE,24); d.text((720,135),'Основной смысл проекта',font=font_h,fill=INK)
for j,t in enumerate(['Сбор данных','Обработка неисправностей','Планирование работ','Контроль и отчеты']): d.ellipse((725,205+j*80,742,222+j*80),fill=BLUE); d.text((760,196+j*80),t,font=font_b,fill=INK)
save(1,im)
# 2
im,d=slide_base('02','Описание работы приложения','От измерения до отчета: приложение ведет процесс обслуживания.')
for i,t in enumerate(['Измерение','Fault','Recommendation','Plan и task','Quality и report']): rr(d,(70,235+i*75,650,292+i*75),WHITE,LINE,16); d.text((95,250+i*75),f'{i+1}. {t}',font=font_b,fill=INK)
rr(d,(730,230,1190,620),(238,246,255),(183,213,255),18); d.text((760,260),'Роли в системе',font=font_h,fill=INK); text_wrap(d,(760,325),'admin, manager, expert, dispatcher, mechanic, quality',font_b,MUTED,28); save(2,im)
# 3
im,d=slide_base('03','На чем написано и архитектура','FastAPI + PostgreSQL/Supabase + Redis/Celery + три клиента.')
for i,t in enumerate(['FastAPI backend','PostgreSQL / Supabase','Redis + Celery','CQRS','Security layer','Clients']): x=70+(i%3)*390; y=245+(i//3)*170; rr(d,(x,y,x+350,y+130),WHITE,LINE,18); d.text((x+25,y+28),t,font=font_b,fill=INK)
save(3,im)
# 4
im,d=slide_base('04','Веб-интерфейс','Окно веб-клиента для ролей и отчетов.'); rr(d,(100,220,1180,620),(15,23,42),None,24); rr(d,(130,270,300,585),(17,24,39),None,14); d.text((155,305),'Web Client',font=font_b,fill=WHITE); d.text((155,360),'Dashboard\nReports\nFaults\nPlans',font=font_s,fill=(203,213,225))
for i,t in enumerate(['Open faults\n12','Reports\nReady','Rate limit\nEnabled']): rr(d,(330+i*260,285,560+i*260,370),(219,234,254),None,14); text_wrap(d,(350+i*260,300),t,font_s,BLUE,20)
rr(d,(330,395,1120,565),WHITE,None,14); d.text((360,420),'Report queue',font=font_b,fill=INK); text_wrap(d,(360,470),'R-104 queued   R-105 completed   R-106 worker',font_s,MUTED,70); d.text((100,650),'Рисунок 1. Веб-интерфейс: dashboard, очередь отчетов и админские проверки.',font=font_s,fill=MUTED); save(4,im)
# 5
im,d=slide_base('05','Мобильный интерфейс','Клиент для механика, метролога и проверки качества.'); rr(d,(160,210,460,635),(17,24,39),None,34); rr(d,(180,230,440,615),(248,250,252),None,24); d.text((210,270),'Задачи механика',font=font_b,fill=INK); rr(d,(210,330,410,410),WHITE,LINE,14); d.text((225,350),'#42 Замена узла',font=font_s,fill=INK); rr(d,(210,445,410,505),BLUE,None,12); d.text((235,463),'Отправить статус',font=font_s,fill=WHITE)
for i,t in enumerate(['Работа с задачами','Сбор измерений','Контроль качества','Проверка прав на backend']): d.ellipse((560,270+i*70,578,288+i*70),fill=BLUE); d.text((600,262+i*70),t,font=font_b,fill=INK)
d.text((160,660),'Рисунок 2. Мобильный интерфейс: задачи, измерения и отправка статусов с телефона.',font=font_s,fill=MUTED); save(5,im)
# 6
im,d=slide_base('06','Десктопный интерфейс','Рабочая консоль мониторинга и обработки заявок.'); rr(d,(100,220,1180,620),(31,41,55),None,24)
for i,t in enumerate(['Fault Feed\nLive','Queue Sync\n5 sec','Audit Mode\nEnabled']): rr(d,(140,270+i*100,360,340+i*100),(55,65,81),None,14); text_wrap(d,(160,285+i*100),t,font_s,WHITE,20)
rr(d,(400,270,1120,570),WHITE,None,14); d.text((430,300),'Monitoring',font=font_b,fill=INK); text_wrap(d,(430,360),'101 security_idor_denied 403\n102 report_enqueued queued\n103 admin_users_viewed audit',font_s,MUTED,70); d.text((100,650),'Рисунок 3. Десктопный интерфейс: мониторинг, очередь событий и audit-журнал.',font=font_s,fill=MUTED); save(6,im)
thumbs=[Image.open(out/f'slide_{i}.png').resize((320,180)) for i in range(1,7)]; mont=Image.new('RGB',(680,590),BG); md=ImageDraw.Draw(mont)
for i,t in enumerate(thumbs): x=20+(i%2)*340; y=20+(i//2)*190; mont.paste(t,(x,y)); md.text((x,y+182),f'Слайд {i+1}',font=font_s,fill=MUTED)
mont.save(out/'montage.png'); print(str(out.resolve()))
