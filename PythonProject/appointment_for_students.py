import streamlit as st
from datetime import datetime, timedelta, timezone
from supabase import create_client
import pandas as pd
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ===== НАСТРОЙКИ ИЗ СЕКРЕТОВ =====
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
SMTP_EMAIL = st.secrets["SMTP_EMAIL"]
SMTP_PASSWORD = st.secrets["SMTP_PASSWORD"]

# Список общежитий
DORMITORIES = [
    "Общежитие №2 | Чкаловский пр-т, д. 27",
    "Общежитие №3 | пр-т Косыгина, д. 19, к. 2",
    "Общежитие №4 | ул. Воронежская, д. 69",
    "Общежитие №7 | ул. Воронежская, д. 38"
]

# Доступные дни для записи с разными временными слотами
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

# ===== ФУНКЦИИ =====
def get_last_update_time():
    utc_now = datetime.now(timezone.utc)
    local_now = utc_now + timedelta(hours=3)  # Для часового пояса UTC+3
    return local_now.strftime("%H:%M"), local_now.strftime("%d.%m.%Y")

def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def get_booked_slots_for_date(date_str):
    """Получает уже забронированные слоты на дату"""
    try:
        supabase = get_supabase()
        response = supabase.table('appointments').select('time').eq('date', date_str).execute()
        if response.data:
            return [appt['time'] for appt in response.data]
        return []
    except Exception:
        return []

def save_appointment(data):
    """Сохраняет запись в базу"""
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
    """Получает все записи пользователя по email"""
    try:
        supabase = get_supabase()
        response = supabase.table('appointments').select('*').eq('email', email).order('date', desc=False).order('time', desc=False).execute()
        if response.data:
            return response.data
        return []
    except Exception as e:
        st.error(f"Ошибка при получении заявок: {e}")
        return []

ddef cancel_appointment(appointment_id, user_email):
    """Отменяет запись"""
    try:
        supabase = get_supabase()
        # Ищем запись с таким ID и email
        response = supabase.table('appointments').select('*').eq('id', appointment_id).eq('email', user_email).execute()
        
        if response.data:
            appointment = response.data[0]
            # Удаляем запись
            delete_response = supabase.table('appointments').delete().eq('id', appointment_id).execute()
            if delete_response.data:
                return True, appointment
            else:
                return False, None
        else:
            st.error(f"❌ Запись №{appointment_id} не найдена или принадлежит другому email")
            return False, None
    except Exception as e:
        st.error(f"Ошибка при отмене: {e}")
        return False, None

# ===== EMAIL УВЕДОМЛЕНИЯ =====
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

def send_confirmation_to_student(student_email, student_name, appointment_id, date, time, dormitory, issue_type):
    subject = f"✅ Запись на прием №{appointment_id} подтверждена"
    body = f"""
Здравствуйте, {student_name}!

Ваша запись на прием в Жилищно-бытовое управление успешно создана.

📅 Дата: {date}
⏰ Время: {time}
🏠 {dormitory}
📋 Вопрос: {issue_type}

Статус: Запланировано

При себе необходимо иметь студенческий билет.

С уважением,
Администрация Жилищно-бытового управления СПбГЭУ
"""
    return send_email(student_email, subject, body)

def send_notification_to_workers(student_name, student_email, dormitory, room, date, time, issue_type, description, appointment_id):
    subject = f"🔔 НОВАЯ ЗАПИСЬ №{appointment_id}"
    body = f"""
📋 НОВАЯ ЗАПИСЬ НА ПРИЕМ

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 Дата: {date}
⏰ Время: {time}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 СТУДЕНТ
• ФИО: {student_name}
• Email: {student_email}
• Общежитие: {dormitory}
• Комната: {room}

📋 ВОПРОС: {issue_type}

📝 ОПИСАНИЕ:
{description}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Зайдите в панель управления для обработки записи.
"""
    for worker_email in WORKER_EMAILS:
        send_email(worker_email, subject, body)
    return True

def send_cancellation_notification(student_email, student_name, appointment_id, date, time):
    subject = f"❌ Отмена записи №{appointment_id}"
    body = f"""
Здравствуйте, {student_name}!

Ваша запись на прием №{appointment_id} была отменена.

📅 Дата: {date}
⏰ Время: {time}

Вы можете создать новую запись в любое удобное время.

С уважением,
Администрация Жилищно-бытового управления СПбГЭУ
"""
    return send_email(student_email, subject, body)

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def get_next_available_date(target_day_code):
    """Получает следующую доступную дату (включая сегодня)"""
    today = datetime.now().date()
    current_day = today.weekday()
    
    # Если сегодня нужный день недели
    if target_day_code == current_day:
        return today
    
    # Иначе ищем следующий день
    days_ahead = (target_day_code - current_day + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)

# ===== ОСНОВНОЕ ПРИЛОЖЕНИЕ =====
def main():
    # Время последнего обновления
    last_update_time, last_update_date = get_last_update_time()
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("🏠 ЖБУ СПбГЭУ | Электронная запись на прием")
    with col2:
        st.metric("🕐 Последнее обновление", last_update_time)
        st.caption(f"📅 {last_update_date}")
    
    # Инициализация состояния
    if "selected_day" not in st.session_state:
        st.session_state.selected_day = None
    if "selected_time" not in st.session_state:
        st.session_state.selected_time = None
    if "show_form" not in st.session_state:
        st.session_state.show_form = False
    
    # Показываем расписание
    with st.expander("📅 Режим работы ЖБУ", expanded=True):
        st.markdown("""
        **Время приема студентов:**
        - **Понедельник:** 14:00 — 16:30
        - **Вторник:** 14:00 — 16:30
        - **Среда:** Приема нет
        - **Четверг:** 14:00 — 16:30
        - **Пятница:** 13:00 — 15:00
        """)
    
    # Кнопка обновления
    if st.button("🔄 Обновить данные"):
        st.rerun()
    
    # Создаем вкладки
    tab1, tab2 = st.tabs(["📝 Записаться на прием", "🗑️ Мои записи"])
    
    # ===== ВКЛАДКА 1: ЗАПИСЬ НА ПРИЕМ =====
    with tab1:
        # Шаг 1: Выбор дня недели
        st.markdown("### Шаг 1: Выберите день недели")
        
        # 4 кнопки для 4 дней
        day_cols = st.columns(4)
        
        for i, (day_key, day_info) in enumerate(AVAILABLE_DAYS.items()):
            with day_cols[i]:
                if st.button(f"📅 {day_info['display']}", key=f"day_{day_key}", use_container_width=True):
                    st.session_state.selected_day = day_key
                    st.session_state.selected_time = None
                    st.session_state.show_form = False
                    st.rerun()
        
        # Шаг 2: Выбор времени (если выбран день)
        if st.session_state.selected_day:
            day_info = AVAILABLE_DAYS[st.session_state.selected_day]
            st.markdown(f"### Шаг 2: Выберите время на {day_info['display']}")
            
            # Получаем дату (может быть сегодня или следующая)
            selected_date = get_next_available_date(day_info["day_code"])
            selected_date_str = selected_date.strftime("%Y-%m-%d")
            selected_date_display = selected_date.strftime("%d.%m.%Y")
            
            # Показываем выбранную дату
            if selected_date == datetime.now().date():
                st.info(f"📅 Вы выбрали: **{day_info['display']}** - СЕГОДНЯ ({selected_date_display})")
            else:
                st.info(f"📅 Вы выбрали: **{day_info['display']}** - {selected_date_display}")
            
            # Получаем забронированные слоты
            booked_slots = get_booked_slots_for_date(selected_date_str)
            
            # Показываем кнопки с временем
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
            
            # Шаг 3: Форма для заполнения данных
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
                        "🔧 Вопрос по сантехнике": "Сантехника",
                        "⚡ Вопрос по электрике": "Электрика",
                        "🧹 Вопрос по уборке": "Уборка",
                        "📄 Вопрос по документам": "Документы",
                        "🏠 Вопрос по заселению": "Заселение",
                        "❓ Другое": "Другое"
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
                                    send_confirmation_to_student(email, fio, new_id, selected_date_display, st.session_state.selected_time, dormitory, type_map[issue_type_display])
                                    send_notification_to_workers(fio, email, dormitory, room, selected_date_display, st.session_state.selected_time, type_map[issue_type_display], description, new_id)
                                    
                                    st.success(f"✅ Запись №{new_id} успешно создана! Подтверждение придет на вашу почту.")
                                    st.balloons()
                                    
                                    # Сбрасываем состояние
                                    st.session_state.selected_day = None
                                    st.session_state.selected_time = None
                                    st.session_state.show_form = False
                                    st.rerun()
                                else:
                                    st.error("❌ Ошибка при сохранении записи. Попробуйте еще раз.")
                            except Exception as e:
                                st.error(f"❌ Ошибка: {e}")
        
        else:
            st.info("👆 Нажмите на день недели, чтобы выбрать дату записи")
    
    # ===== ВКЛАДКА 2: МОИ ЗАПИСИ =====
    with tab2:
        st.markdown("### Мои записи на прием")
        
        view_email = st.text_input("Введите ваш email для просмотра записей", key="view_email")
        
        if st.button("🔍 Показать мои записи", key="show_my_appointments"):
            if view_email and validate_email(view_email):
                appointments = get_appointments_by_email(view_email)
                if appointments:
                    st.success(f"Найдено {len(appointments)} записей")
                    
                    appointments_sorted = sorted(appointments, key=lambda x: (x['date'], x['time']))
                    
                    for app in appointments_sorted:
                        with st.container():
                            col1, col2, col3 = st.columns([3, 2, 1])
                            with col1:
                                st.markdown(f"**№{app['id']}** | 📅 {app['date']} | ⏰ {app['time']}")
                                st.markdown(f"🏠 {app['dormitory']} | Комната: {app['room']}")
                                st.markdown(f"📋 {app['issue_type']}")
                            with col2:
                                status_color = {
                                    "Запланировано": "🟡",
                                    "Подтверждено": "🟢",
                                    "Выполнено": "✅",
                                    "Отменено": "❌"
                                }.get(app['status'], "⚪")
                                st.markdown(f"{status_color} **Статус:** {app['status']}")
                            with col3:
                                if st.button("❌ Отменить", key=f"cancel_{app['id']}"):
                                    success, appointment = cancel_appointment(app['id'], view_email)
                                    if success and appointment:
                                        send_cancellation_notification(view_email, appointment['fio'], app['id'], appointment['date'], appointment['time'])
                                        for worker_email in WORKER_EMAILS:
                                            send_email(worker_email, f"❌ Отмена записи №{app['id']}", f"Запись №{app['id']} была отменена студентом {appointment['fio']}")
                                        st.success(f"✅ Запись №{app['id']} отменена")
                                        st.rerun()
                                    else:
                                        st.error("❌ Ошибка при отмене")
                            st.divider()
                else:
                    st.warning("Записи не найдены")
            else:
                st.error("Введите корректный email")

if __name__ == "__main__":
    main()
