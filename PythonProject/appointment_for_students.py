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

# Расписание по дням недели (длительность приема 10 минут)
SCHEDULE = {
    "Monday": {"start": "14:00", "end": "16:30", "slot_minutes": 10},
    "Tuesday": {"start": "14:00", "end": "16:30", "slot_minutes": 10},
    "Wednesday": {"start": None, "end": None, "slot_minutes": 10},  # Среда - выходной
    "Thursday": {"start": "14:00", "end": "16:30", "slot_minutes": 10},
    "Friday": {"start": "13:00", "end": "15:00", "slot_minutes": 10},
    "Saturday": {"start": None, "end": None, "slot_minutes": 10},  # Суббота - выходной
    "Sunday": {"start": None, "end": None, "slot_minutes": 10}  # Воскресенье - выходной
}

WORKER_EMAILS = [
    "valeraforumsch@gmail.com"
]

# ===== ФУНКЦИИ РАБОТЫ С БАЗОЙ =====
def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def generate_time_slots_for_day(date):
    """Генерирует временные слоты для конкретной даты"""
    day_name = date.strftime("%A")
    day_schedule = SCHEDULE.get(day_name)
    
    if not day_schedule or day_schedule["start"] is None:
        return []
    
    start_time = datetime.strptime(day_schedule["start"], "%H:%M")
    end_time = datetime.strptime(day_schedule["end"], "%H:%M")
    slot_minutes = day_schedule["slot_minutes"]
    
    slots = []
    current = start_time
    while current < end_time:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=slot_minutes)
    
    return slots

def get_booked_slots_for_date(date):
    """Получает уже забронированные слоты на дату"""
    try:
        supabase = get_supabase()
        date_str = date.strftime("%Y-%m-%d")
        response = supabase.table('appointments').select('time').eq('date', date_str).execute()
        if response.data:
            return [appt['time'] for appt in response.data]
        return []
    except Exception:
        return []

def get_available_time_slots(date):
    """Возвращает доступные временные слоты на дату"""
    all_slots = generate_time_slots_for_day(date)
    booked_slots = get_booked_slots_for_date(date)
    available = [slot for slot in all_slots if slot not in booked_slots]
    return available

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

def cancel_appointment(appointment_id, user_email):
    """Отменяет запись"""
    try:
        supabase = get_supabase()
        response = supabase.table('appointments').select('*').eq('id', appointment_id).eq('email', user_email).execute()
        if response.data:
            appointment = response.data[0]
            supabase.table('appointments').delete().eq('id', appointment_id).execute()
            return True, appointment
        return False, None
    except Exception:
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

# ===== ОСНОВНОЕ ПРИЛОЖЕНИЕ =====
def main():
    st.title("🏠 ЖБУ СПбГЭУ | Электронная запись на прием")
    
    # Показываем расписание
    with st.expander("📅 Режим работы ЖБУ", expanded=True):
        st.markdown("""
        **Время приема студентов:**
        - **Понедельник:** 14:00 — 16:30 (перерыв каждые 10 минут)
        - **Вторник:** 14:00 — 16:30 (перерыв каждые 10 минут)
        - **Среда:** Выходной
        - **Четверг:** 14:00 — 16:30 (перерыв каждые 10 минут)
        - **Пятница:** 13:00 — 15:00 (перерыв каждые 10 минут)
        - **Суббота:** Выходной
        - **Воскресенье:** Выходной
        """)
    
    # Создаем вкладки
    tab1, tab2 = st.tabs(["📝 Записаться на прием", "🗑️ Мои записи"])
    
    # ===== ВКЛАДКА 1: ЗАПИСЬ НА ПРИЕМ =====
    with tab1:
        st.markdown("Заполните форму ниже, чтобы записаться на прием в Жилищно-бытовое управление.")
        
        with st.form("appointment_form"):
            fio = st.text_input("Ваше ФИО *")
            email = st.text_input("Email для связи *", 
                                  placeholder="example@mail.ru",
                                  help="На этот email придет подтверждение записи")
            
            dormitory = st.selectbox("Выберите общежитие *", DORMITORIES)
            room = st.text_input("Номер блока/комнаты *")
            
            # Выбор даты (только будущие даты)
            min_date = datetime.now().date() + timedelta(days=1)
            selected_date = st.date_input("Выберите дату приема *", min_value=min_date, value=min_date)
            
            # Проверяем, рабочий ли день
            day_name = selected_date.strftime("%A")
            day_schedule = SCHEDULE.get(day_name)
            
            if day_schedule and day_schedule["start"] is None:
                st.error(f"❌ {selected_date.strftime('%A')} - выходной день. Выберите другой день.")
                available_slots = []
                selected_time = None
            else:
                # Получаем доступное время
                available_slots = get_available_time_slots(selected_date)
                
                if not available_slots:
                    st.warning(f"⚠️ На {selected_date.strftime('%d.%m.%Y')} нет свободного времени. Пожалуйста, выберите другую дату.")
                    selected_time = None
                else:
                    selected_time = st.selectbox("Выберите время *", available_slots)
            
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
            
            submitted = st.form_submit_button("📅 Записаться на прием")
            
            if submitted:
                if not fio or not email or not room or not description:
                    st.error("❌ Пожалуйста, заполните все поля")
                elif not validate_email(email):
                    st.error("❌ Пожалуйста, введите корректный email адрес")
                elif not available_slots or not selected_time:
                    st.error("❌ На выбранную дату нет свободного времени")
                else:
                    appointment_data = {
                        "date": selected_date.strftime("%Y-%m-%d"),
                        "time": selected_time,
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
                            send_confirmation_to_student(email, fio, new_id, selected_date.strftime("%d.%m.%Y"), selected_time, dormitory, type_map[issue_type_display])
                            send_notification_to_workers(fio, email, dormitory, room, selected_date.strftime("%d.%m.%Y"), selected_time, type_map[issue_type_display], description, new_id)
                            
                            st.success(f"✅ Запись №{new_id} успешно создана! Подтверждение придет на вашу почту.")
                            st.balloons()
                        else:
                            st.error("❌ Ошибка при сохранении записи. Попробуйте еще раз.")
                    except Exception as e:
                        st.error(f"❌ Ошибка: {e}")
    
    # ===== ВКЛАДКА 2: МОИ ЗАПИСИ =====
    with tab2:
        st.markdown("### Мои записи на прием")
        
        view_email = st.text_input("Введите ваш email для просмотра записей", key="view_email")
        
        if st.button("🔍 Показать мои записи", key="show_my_appointments"):
            if view_email and validate_email(view_email):
                appointments = get_appointments_by_email(view_email)
                if appointments:
                    st.success(f"Найдено {len(appointments)} записей")
                    
                    df = pd.DataFrame(appointments)
                    df_display = df[['id', 'date', 'time', 'issue_type', 'dormitory', 'room', 'status']]
                    df_display.columns = ['ID', 'Дата', 'Время', 'Вопрос', 'Общежитие', 'Комната', 'Статус']
                    st.dataframe(df_display, use_container_width=True)
                    
                    st.markdown("---")
                    st.markdown("### Отмена записи")
                    cancel_id = st.text_input("Введите ID записи для отмены")
                    
                    if st.button("❌ Отменить запись"):
                        if cancel_id:
                            try:
                                appointment_id_int = int(cancel_id)
                                success, appointment = cancel_appointment(appointment_id_int, view_email)
                                
                                if success and appointment:
                                    send_cancellation_notification(view_email, appointment['fio'], appointment_id_int, appointment['date'], appointment['time'])
                                    for worker_email in WORKER_EMAILS:
                                        send_email(worker_email, f"❌ Отмена записи №{appointment_id_int}", f"Запись №{appointment_id_int} была отменена студентом {appointment['fio']}")
                                    st.success(f"✅ Запись №{appointment_id_int} успешно отменена")
                                    st.rerun()
                                else:
                                    st.error(f"❌ Запись не найдена или у вас нет прав")
                            except ValueError:
                                st.error("❌ ID должен быть числом")
                        else:
                            st.error("❌ Введите ID записи")
                else:
                    st.warning("Записи не найдены")
            else:
                st.error("Введите корректный email")

if __name__ == "__main__":
    main()
