import streamlit as st
from datetime import datetime, timedelta, timezone
from supabase import create_client
import pandas as pd
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

st.set_page_config(
    page_title="Электронная запись в ЖБУ | Общежития СПбГЭУ",
    page_icon="📆",
    layout="wide",
    initial_sidebar_state="expanded"
)

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
SMTP_EMAIL = st.secrets["SMTP_EMAIL"]
SMTP_PASSWORD = st.secrets["SMTP_PASSWORD"]

DORMITORIES = [
    "Общежитие №2 | Чкаловский пр-т, д. 27",
    "Общежитие №3 | пр-т Косыгина, д. 19, к. 2",
    "Общежитие №4 | ул. Воронежская, д. 69",
    "Общежитие №7 | ул. Воронежская, д. 38"
]

AVAILABLE_DAYS = {
    "ПН": {
        "day_code": 0, 
        "display": "Понедельник", 
        "active": True,
        "time_slots": [
            "14:00", "14:10", "14:20", "14:30", "14:40", "14:50",
            "15:00", "15:10", "15:20", "15:30", "15:40", "15:50",
            "16:00", "16:10", "16:20"
        ]
    },
    "ВТ": {
        "day_code": 1, 
        "display": "Вторник", 
        "active": True,
        "time_slots": [
            "14:00", "14:10", "14:20", "14:30", "14:40", "14:50",
            "15:00", "15:10", "15:20", "15:30", "15:40", "15:50",
            "16:00", "16:10", "16:20"
        ]
    },
    "ЧТ": {
        "day_code": 3, 
        "display": "Четверг", 
        "active": True,
        "time_slots": [
            "14:00", "14:10", "14:20", "14:30", "14:40", "14:50",
            "15:00", "15:10", "15:20", "15:30", "15:40", "15:50",
            "16:00", "16:10", "16:20"
        ]
    },
    "ПТ": {
        "day_code": 4, 
        "display": "Пятница", 
        "active": True,
        "time_slots": [
            "13:00", "13:10", "13:20", "13:30", "13:40", "13:50",
            "14:00", "14:10", "14:20", "14:30", "14:40", "14:50"
        ]
    }
}

WORKER_EMAILS = [
    "valeraforumsch@gmail.com"
]

def get_last_update_time():
    utc_now = datetime.now(timezone.utc)
    local_now = utc_now + timedelta(hours=3)
    return local_now.strftime("%H:%M"), local_now.strftime("%d.%m.%Y")

def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def get_booked_slots_for_date(date_str):
    try:
        supabase = get_supabase()
        response = supabase.table('appointments').select('time').eq('date', date_str).execute()
        if response.data:
            return [appt['time'] for appt in response.data]
        return []
    except Exception:
        return []

def save_appointment(data):
    supabase = get_supabase()
    result = supabase.table('appointments').insert({
        "date": data["date"],
        "time": data["time"],
        "fio": data["fio"],
        "email": data["email"],
        "dormitory": data["dormitory"],
        "room": data["room"],
        "issue_type": data["issue_type"],
        "description": data["description"],
        "status": "Запланировано"
    }).execute()
    if result.data:
        return result.data[0]['id']
    return None

def get_appointments_by_email(email):
    try:
        supabase = get_supabase()
        response = supabase.table('appointments').select('*').eq('email', email).order('date', desc=False).order('time', desc=False).execute()
        if response.data:
            return response.data
        return []
    except Exception as e:
        st.error(f"Ошибка при получении записей: {e}")
        return []

def delete_appointment(appointment_id, appointment_email=None):
    """Удаление записи по ID"""
    try:
        supabase = get_supabase()
        
        # Если указан email, проверяем, что запись принадлежит этому email
        if appointment_email:
            result = supabase.table('appointments').delete().eq('id', appointment_id).eq('email', appointment_email).execute()
        else:
            result = supabase.table('appointments').delete().eq('id', appointment_id).execute()
        
        if result.data:
            return True, "Запись успешно удалена"
        else:
            return False, "Запись не найдена или у вас нет прав на её удаление"
    except Exception as e:
        return False, f"Ошибка при удалении: {str(e)}"

def send_email(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Ошибка: {e}")
        return False

def get_check_in_message(student_name, appointment_id, date, time, dormitory):
    consent_form_url = "https://unecon.ru/wp-content/uploads/2022/05/obrazec_soglasiya_dlya_roditeley_opekunov_0.pdf"
    info_url = "https://kosigina19k2.streamlit.app/settling"
    
    return f"""
Здравствуйте, {student_name}!

Ваша запись на заселение в общежитие успешно создана.

📅 Дата: {date}
⏰ Время: {time}
🏠 {dormitory}
📋 Вопрос: Заселение в общежитие

Статус: Запланировано

Для заселения при себе необходимо иметь:

1. Для граждан Российской Федерации:
• Копия паспорта с регистрацией по месту жительства;
• Копия медицинской справки с результатами флюорографического обследования;
• 1 фото формата 3х4;
• Для несовершеннолетних студентов: оригинал нотариально заверенного согласия родителей (опекунов) на заключение договора найма жилого помещения в общежитии (образец заявления : {consent_form_url});
• Документы и копии документов, подтверждающих льготы, указанные в ч. 5 ст. 36 Федерального закона от 29 декабря 2012 г. №273-ФЗ "Об образовании в Российской Федерации" (при наличии).

2. Для граждан иностранных государств:
• Для несовершеннолетних студентов: оригинал нотариально заверенного согласия родителей (опекунов) на заключение договора найма жилого помещения в общежитии (образец заявления);
• Паспорт (с нотариально заверенным переводом на русский язык либо переводом, заверенным подписью руководителя Управления международного сотрудничества и печатью);
• Копия медицинской справки с результатами флюорографического обследования.

Дополнительная информация доступна по ссылке: {info_url}.

Ждем вас в кабинете №5.

С уважением,
Администрация Жилищно-бытового управления СПбГЭУ
"""

def get_relocation_message(student_name, appointment_id, date, time, dormitory):
    consent_form_url = "https://unecon.ru/wp-content/uploads/2022/05/obrazec_soglasiya_dlya_roditeley_opekunov_0.pdf"
    info_url = "https://kosigina19k2.streamlit.app/settling"
    
    return f"""
Здравствуйте, {student_name}!

Ваша запись на переселение в другое общежитие успешно создана.

📅 Дата: {date}
⏰ Время: {time}
🏠 {dormitory}
📋 Вопрос: Переселение 

Статус: Запланировано

Для рассмотрения вопроса о переселении внутри своего общежития обратитесь к заведующему общежитием, в котором вы проживаете.

Для рассмотрения вопроса о переселении из одного общежития в другое общежитие, при себе необходимо иметь:

1. Для граждан Российской Федерации:
• Копия паспорта с регистрацией по месту жительства;
• Копия медицинской справки с результатами флюорографического обследования;
• 1 фото формата 3х4;
• Для несовершеннолетних студентов: оригинал нотариально заверенного согласия родителей (опекунов) на заключение договора найма жилого помещения в общежитии (образец заявления: {consent_form_url});
• Документы и копии документов, подтверждающих льготы, указанные в ч. 5 ст. 36 Федерального закона от 29 декабря 2012 г. №273-ФЗ "Об образовании в Российской Федерации" (при наличии).

2. Для граждан иностранных государств:
• Для несовершеннолетних студентов: оригинал нотариально заверенного согласия родителей (опекунов) на заключение договора найма жилого помещения в общежитии (образец заявления);
• Паспорт (с нотариально заверенным переводом на русский язык либо переводом, заверенным подписью руководителя Управления международного сотрудничества и печатью);
• Копия медицинской справки с результатами флюорографического обследования.

Дополнительная информация доступна по ссылке: {info_url}.

Ждем вас в кабинете №5.

С уважением,
Администрация Жилищно-бытового управления СПбГЭУ
"""

def get_check_out_message(student_name, appointment_id, date, time, dormitory):
    return f"""
Здравствуйте, {student_name}!

Ваша запись на выселение из общежития успешно создана.

📅 Дата: {date}
⏰ Время: {time}
🏠 {dormitory}
📋 Вопрос: Выселение из общежития

Статус: Запланировано

Для выселения необходимо:
1. Написать заявление на выезд у заведующего студенческим общежитием;
2. Погасить задолженность за проживание в общежитии;
3. Получить и заполнить обходной лист;
4. Заполненный обходной лист отдать заведующему студенческим общежитием вместе с ключами от комнаты.

Выезд из общежития БЕЗ ОБХОДНОГО ЛИСТА не осуществляется. Оплата за проживание в общежитии будет также накапливаться.

Ждем вас в кабинете №5.

Если у вас не осталось никаких вопросов, то приходить по записи в ЖБУ не нужно. В ином случае, если вопросы возникнут, ваша запись будет актуальна.

С уважением,
Администрация Жилищно-бытового управления СПбГЭУ
"""

def get_msg_settlement_message(student_name, appointment_id, date, time, dormitory):
    return f"""
Здравствуйте, {student_name}!

Ваша запись по вопросу заселения в МСГ (в т. ч. СПО) успешно создана.

📅 Дата: {date}
⏰ Время: {time}
🏠 {dormitory}
📋 Вопрос: Заселение в МСГ (в т. ч. СПО)

Статус: Запланировано

Ждем вас в кабинете №5.

С уважением,
Администрация Жилищно-бытового управления СПбГЭУ
"""

def get_registration_message(student_name, appointment_id, date, time, dormitory):
    return f"""
Здравствуйте, {student_name}!

Ваша запись по вопросу временной регистрации успешно создана.

📅 Дата: {date}
⏰ Время: {time}
🏠 {dormitory}
📋 Вопрос: Временная регистрация

Статус: Запланировано

Если вы проживаете не в общежитии №3 (пр-т Косыгина, д. 19, к.2), то обратитесь к паспортисту в своем общежитии.

Для студентов, проживающих в общежитии №3 (пр-т Косыгина, д. 19, к. 2), по решению вопроса о временной регистрации при себе необходимо иметь:
• Паспорт
• Студенческий билет
• Договор найма

Ждем вас в кабинете №5.

С уважением,
Администрация Жилищно-бытового управления СПбГЭУ
"""

def get_benefits_message(student_name, appointment_id, date, time, dormitory):
    return f"""
Здравствуйте, {student_name}!

Ваша запись по вопросу льгот успешно создана.

📅 Дата: {date}
⏰ Время: {time}
🏠 {dormitory}
📋 Вопрос: Льготы

Статус: Запланировано

Для рассмотрения вопроса о льготах при себе необходимо иметь документы и/или копии документов, подтверждающих льготы, 
указанные в ч. 5 ст. 36 Федерального закона от 29 декабря 2012 г. №273-ФЗ "Об образовании в Российской Федерации" (при наличии).

Ждем вас в кабинете №5.

С уважением,
Администрация Жилищно-бытового управления СПбГЭУ
"""

def get_certificate_message(student_name, appointment_id, date, time, dormitory):
    return f"""
Здравствуйте, {student_name}!

Ваша запись на получение необходимой справки успешно создана.

📅 Дата: {date}
⏰ Время: {time}
🏠 {dormitory}
📋 Вопрос: Справки

Статус: Запланировано

Ждем вас в кабинете №5.

С уважением,
Администрация Жилищно-бытового управления СПбГЭУ
"""

def get_other_message(student_name, appointment_id, date, time, dormitory, description):
    return f"""
Здравствуйте, {student_name}!

Ваша запись на прием в Жилищно-бытовое управление успешно создана.

📅 Дата: {date}
⏰ Время: {time}
🏠 {dormitory}
📋 Вопрос: Другое

Статус: Запланировано

Ваш вопрос: {description[:200]}{'...' if len(description) > 200 else ''}

Ждем вас в кабинете №5.

С уважением,
Администрация Жилищно-бытового управления СПбГЭУ
"""

def send_confirmation_to_student(student_email, student_name, appointment_id, date, time, dormitory, issue_type, description=""):
    if issue_type == "Заселение в общежитие":
        body = get_check_in_message(student_name, appointment_id, date, time, dormitory)
    elif issue_type == "Переселение в другое общежитие":
        body = get_relocation_message(student_name, appointment_id, date, time, dormitory)
    elif issue_type == "Выселение из общежития":
        body = get_check_out_message(student_name, appointment_id, date, time, dormitory)
    elif issue_type == "Заселение в МСГ (в т. ч. СПО)":
        body = get_msg_settlement_message(student_name, appointment_id, date, time, dormitory)
    elif issue_type == "Временная регистрация":
        body = get_registration_message(student_name, appointment_id, date, time, dormitory)
    elif issue_type == "Льготы":
        body = get_benefits_message(student_name, appointment_id, date, time, dormitory)
    elif issue_type == "Справки":
        body = get_certificate_message(student_name, appointment_id, date, time, dormitory)
    else:  
        body = get_other_message(student_name, appointment_id, date, time, dormitory, description)
    
    subject = f"✅ Запись на прием №{appointment_id} подтверждена"
    return send_email(student_email, subject, body)

def get_worker_check_in_message(student_name, student_email, dormitory, room, date, time, description, appointment_id):
    return f"""
📋 НОВАЯ ЗАПИСЬ НА ЗАСЕЛЕНИЕ №{appointment_id}

📅 Дата: {date}
⏰ Время: {time}

👤 СТУДЕНТ
• ФИО: {student_name}
• Email: {student_email}
• Общежитие: {dormitory}
• Комната: {room}

📋 ВОПРОС: Заселение в общежитие

📝 ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ:
{description if description else "Не указана"}
"""

def get_worker_relocation_message(student_name, student_email, dormitory, room, date, time, description, appointment_id):
    return f"""
📋 НОВАЯ ЗАПИСЬ НА ПЕРЕСЕЛЕНИЕ №{appointment_id}

📅 Дата: {date}
⏰ Время: {time}

👤 СТУДЕНТ
• ФИО: {student_name}
• Email: {student_email}
• Текущее общежитие: {dormitory}
• Комната: {room}

📋 ВОПРОС: Переселение в другое общежитие

📝 ПРИЧИНА ПЕРЕСЕЛЕНИЯ:
{description if description else "Не указана"}
"""

def get_worker_check_out_message(student_name, student_email, dormitory, room, date, time, description, appointment_id):
    return f"""
📋 НОВАЯ ЗАПИСЬ НА ВЫСЕЛЕНИЕ №{appointment_id}

📅 Дата: {date}
⏰ Время: {time}

👤 СТУДЕНТ
• ФИО: {student_name}
• Email: {student_email}
• Общежитие: {dormitory}
• Комната: {room}

📋 ВОПРОС: Выселение из общежития

📝 ПРИЧИНА ВЫСЕЛЕНИЯ:
{description if description else "Не указана"}
"""

def get_worker_msg_settlement_message(student_name, student_email, dormitory, room, date, time, description, appointment_id):
    return f"""
📋 НОВАЯ ЗАПИСЬ В МСГ №{appointment_id}

📅 Дата: {date}
⏰ Время: {time}

👤 СТУДЕНТ
• ФИО: {student_name}
• Email: {student_email}
• Общежитие: {dormitory}
• Комната: {room}

📋 ВОПРОС: Заселение в МСГ (в т. ч. СПО)

📝 ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ:
{description if description else "Не указана"}
"""

def get_worker_registration_message(student_name, student_email, dormitory, room, date, time, description, appointment_id):
    return f"""
📋 НОВАЯ ЗАПИСЬ НА ВРЕМЕННУЮ РЕГИСТРАЦИЮ №{appointment_id}

📅 Дата: {date}
⏰ Время: {time}

👤 СТУДЕНТ
• ФИО: {student_name}
• Email: {student_email}
• Общежитие: {dormitory}
• Комната: {room}

📋 ВОПРОС: Временная регистрация

📝 ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ:
{description if description else "Не указана"}
"""

def get_worker_benefits_message(student_name, student_email, dormitory, room, date, time, description, appointment_id):
    return f"""
📋 НОВАЯ ЗАПИСЬ ПО ЛЬГОТАМ №{appointment_id}

📅 Дата: {date}
⏰ Время: {time}

👤 СТУДЕНТ
• ФИО: {student_name}
• Email: {student_email}
• Общежитие: {dormitory}
• Комната: {room}

📋 ВОПРОС: Льготы

📝 ТИП ЛЬГОТЫ/ПОДРОБНОСТИ:
{description if description else "Не указаны"}
"""

def get_worker_certificate_message(student_name, student_email, dormitory, room, date, time, description, appointment_id):
    return f"""
📋 НОВАЯ ЗАПИСЬ НА СПРАВКУ №{appointment_id}

📅 Дата: {date}
⏰ Время: {time}

👤 СТУДЕНТ
• ФИО: {student_name}
• Email: {student_email}
• Общежитие: {dormitory}
• Комната: {room}

📋 ВОПРОС: Справки

📝 ТРЕБУЕМАЯ СПРАВКА:
{description if description else "Не указана"}
"""

def get_worker_other_message(student_name, student_email, dormitory, room, date, time, description, appointment_id):
    return f"""
📋 НОВАЯ ЗАПИСЬ №{appointment_id}

📅 Дата: {date}
⏰ Время: {time}

👤 СТУДЕНТ
• ФИО: {student_name}
• Email: {student_email}
• Общежитие: {dormitory}
• Комната: {room}

📋 ВОПРОС: Другое

📝 ОПИСАНИЕ ВОПРОСА:
{description if description else "Не указано"}
"""

def send_notification_to_workers(student_name, student_email, dormitory, room, date, time, issue_type, description, appointment_id):
    if issue_type == "Заселение в общежитие":
        body = get_worker_check_in_message(student_name, student_email, dormitory, room, date, time, description, appointment_id)
    elif issue_type == "Переселение в другое общежитие":
        body = get_worker_relocation_message(student_name, student_email, dormitory, room, date, time, description, appointment_id)
    elif issue_type == "Выселение из общежития":
        body = get_worker_check_out_message(student_name, student_email, dormitory, room, date, time, description, appointment_id)
    elif issue_type == "Заселение в МСГ (в т. ч. СПО)":
        body = get_worker_msg_settlement_message(student_name, student_email, dormitory, room, date, time, description, appointment_id)
    elif issue_type == "Временная регистрация":
        body = get_worker_registration_message(student_name, student_email, dormitory, room, date, time, description, appointment_id)
    elif issue_type == "Льготы":
        body = get_worker_benefits_message(student_name, student_email, dormitory, room, date, time, description, appointment_id)
    elif issue_type == "Справки":
        body = get_worker_certificate_message(student_name, student_email, dormitory, room, date, time, description, appointment_id)
    else: 
        body = get_worker_other_message(student_name, student_email, dormitory, room, date, time, description, appointment_id)
    
    subject = f"🔔 НОВАЯ ЗАПИСЬ №{appointment_id}"
    
    for worker_email in WORKER_EMAILS:
        send_email(worker_email, subject, body)
    return True

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def get_next_available_date(target_day_code):
    today = datetime.now().date()
    current_day = today.weekday()
    
    if target_day_code == current_day:
        return today
    
    days_ahead = (target_day_code - current_day + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)

def main():
    last_update_time, last_update_date = get_last_update_time()
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("🏠 ЖБУ СПбГЭУ | Электронная запись на прием")
    with col2:
        st.metric("🕐 Последнее обновление", last_update_time)
        st.caption(f"📅 {last_update_date}")
    
    if "selected_day" not in st.session_state:
        st.session_state.selected_day = None
    if "selected_time" not in st.session_state:
        st.session_state.selected_time = None
    if "show_form" not in st.session_state:
        st.session_state.show_form = False
    
    with st.expander("📅 Режим работы ЖБУ", expanded=True):
        st.markdown("""
        **Время приема студентов:**
        - **Понедельник:** 14:00 — 16:30
        - **Вторник:** 14:00 — 16:30
        - **Среда:** Приема нет
        - **Четверг:** 14:00 — 16:30
        - **Пятница:** 13:00 — 15:00
        """)
    
    tab1, tab2 = st.tabs(["📝 Записаться на прием", "🗑️ Управление записями"])
    
    with tab1:
        st.markdown("### Шаг 1: Выберите день недели")
        
        day_cols = st.columns(4)
        
        for i, (day_key, day_info) in enumerate(AVAILABLE_DAYS.items()):
            with day_cols[i]:
                if st.button(f"📅 {day_info['display']}", key=f"day_{day_key}", use_container_width=True):
                    st.session_state.selected_day = day_key
                    st.session_state.selected_time = None
                    st.session_state.show_form = False
                    st.rerun()
        
        if st.session_state.selected_day:
            day_info = AVAILABLE_DAYS[st.session_state.selected_day]
            st.markdown(f"### Шаг 2: Выберите время")
            
            selected_date = get_next_available_date(day_info["day_code"])
            selected_date_str = selected_date.strftime("%Y-%m-%d")  # ✅ Для БД
            selected_date_display = selected_date.strftime("%d.%m.%Y")  # ✅ Для отображения
            
            if selected_date == datetime.now().date():
                st.info(f"📅 Вы выбрали: **{day_info['display']}** СЕГОДНЯ ({selected_date_display})")
            else:
                st.info(f"📅 Вы выбрали: **{day_info['display']}** {selected_date_display}")
            
            booked_slots = get_booked_slots_for_date(selected_date_str)
            
            st.markdown("**Доступное время:**")
            
            time_slots = day_info["time_slots"]
            time_cols = st.columns(5)
            for idx, time_slot in enumerate(time_slots):
                col_idx = idx % 5
                with time_cols[col_idx]:
                    if time_slot in booked_slots:
                        st.button(f"❌ {time_slot}", disabled=True, key=f"time_{day_key}_{time_slot}", use_container_width=True)
                    else:
                        if st.button(f"🟢 {time_slot}", key=f"time_{day_key}_{time_slot}", use_container_width=True):
                            st.session_state.selected_time = time_slot
                            st.session_state.show_form = True
                            st.rerun()
            
            if st.session_state.show_form and st.session_state.selected_time:
                st.markdown(f"### Шаг 3: Заполните данные для записи на {st.session_state.selected_time}")
                
                with st.form("appointment_form"):
                    fio = st.text_input("Ваше ФИО *")
                    email = st.text_input("Email для связи *", 
                                          placeholder="example@mail.ru",
                                          help="На этот email придет подтверждение записи")
                    
                    dormitory = st.selectbox("Выберите общежитие *", DORMITORIES)
                    room = st.text_input("Номер блока/комнаты *")
                    
                    type_map = {
                        "Заселение в общежитие": "Заселение в общежитие",
                        "Переселение в другое общежитие": "Переселение в другое общежитие",
                        "Выселение из общежития": "Выселение из общежития",
                        "Заселение в МСГ (в т. ч. СПО)": "Заселение в МСГ (в т. ч. СПО)",
                        "Временная регистрация": "Временная регистрация",
                        "Льготы": "Льготы",
                        "Справки": "Справки",
                        "Другое": "Другое"
                    }
                    issue_type_display = st.selectbox("Тип вопроса *", list(type_map.keys()))
                    
                    description = st.text_area("Подробное описание вопроса *", height=150)
                    
                    submitted = st.form_submit_button("✅ Подтвердить запись")
                    
                    if submitted:
                        if not fio or not email or not room or not description:
                            st.error("❌ Пожалуйста, заполните все поля")
                        elif not validate_email(email):
                            st.error("❌ Пожалуйста, введите корректный email адрес")
                        else:
                            appointment_data = {
                                "date": selected_date_str,
                                "time": st.session_state.selected_time,
                                "fio": fio,
                                "email": email,
                                "dormitory": dormitory,
                                "room": room,
                                "issue_type": type_map[issue_type_display],
                                "description": description
                            }
                            try:
                                new_id = save_appointment(appointment_data)
                                
                                if new_id:
                                    send_confirmation_to_student(email, fio, new_id, selected_date_display, st.session_state.selected_time, dormitory, type_map[issue_type_display], description)
                                    send_notification_to_workers(fio, email, dormitory, room, selected_date_display, st.session_state.selected_time, type_map[issue_type_display], description, new_id)
                                    
                                    st.success(f"✅ Запись №{new_id} успешно создана! Подтверждение придет на вашу почту.")
                                    st.balloons()
                                    
                                    st.session_state.selected_day = None
                                    st.session_state.selected_time = None
                                    st.session_state.show_form = False
                                else:
                                    st.error("❌ Ошибка при сохранении записи. Попробуйте еще раз.")
                            except Exception as e:
                                st.error(f"❌ Ошибка: {e}")
        
        else:
            st.info("👆 Выберите дату и время записи")
    
    with tab2:
        st.markdown("### Удаление записи")
        st.markdown("Введите ваш email и ID записи, чтобы удалить её")
        
        col1, col2 = st.columns(2)
        
        with col1:
            delete_email = st.text_input("Ваш email", key="delete_email")
        
        with col2:
            delete_appointment_id = st.text_input("Номер записи", key="delete_id")
        
        if st.button("🔍 Показать мои записи", key="show_appointments"):
            if delete_email and validate_email(delete_email):
                user_appointments = get_appointments_by_email(delete_email)
                if user_appointments:
                    st.success(f"Найдено {len(user_appointments)} записей")
                    
                    # Создаем DataFrame для отображения
                    df = pd.DataFrame(user_appointments)
                    df_display = df[['id', 'date', 'time', 'issue_type', 'dormitory', 'room', 'status', 'description']]
                    df_display.columns = ['ID', 'Дата', 'Время', 'Вопрос', 'Общежитие', 'Комната', 'Статус', 'Описание']
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                else:
                    st.warning("Записи не найдены")
            else:
                st.error("Введите корректный email")
        
        if st.button("🗑️ Удалить запись", key="delete_button"):
            if delete_email and delete_appointment_id:
                if not validate_email(delete_email):
                    st.error("❌ Неверный формат email")
                else:
                    try:
                        appointment_id_int = int(delete_appointment_id)
                        success, message = delete_appointment(appointment_id_int, delete_email)
                        if success:
                            st.success(f"✅ {message}")
                            st.balloons()
                            # Отправляем уведомление работникам об удалении
                            notification_body = f"Запись №{appointment_id_int} была удалена пользователем {delete_email}"
                            for worker_email in WORKER_EMAILS:
                                send_email(worker_email, f"🗑️ Запись №{appointment_id_int} удалена", notification_body)
                        else:
                            st.error(f"❌ {message}")
                    except ValueError:
                        st.error("❌ ID записи должен быть числом")
            else:
                st.error("❌ Введите email и ID записи для удаления")

if __name__ == "__main__":
    main()
