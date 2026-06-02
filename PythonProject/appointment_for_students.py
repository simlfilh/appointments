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

# Доступное время для записи
DEFAULT_TIME_SLOTS = [
    "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"
]

WORKER_EMAILS = [
    "valeraforumsch@gmail.com"
]


# ===== ФУНКЦИИ РАБОТЫ С БАЗОЙ =====
def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


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


def get_appointments_by_date(date):
    supabase = get_supabase()
    response = supabase.table('appointments').select('*').eq('date', date).order('time', asc=True).execute()
    if response.data:
        return response.data
    return []


def get_appointments_by_email(email):
    supabase = get_supabase()
    response = supabase.table('appointments').select('*').eq('email', email).order('date', desc=True).order('time',
                                                                                                            asc=True).execute()
    if response.data:
        return response.data
    return []


def cancel_appointment(appointment_id, user_email):
    supabase = get_supabase()
    response = supabase.table('appointments').select('*').eq('id', appointment_id).eq('email', user_email).execute()
    if response.data:
        appointment = response.data[0]
        supabase.table('appointments').delete().eq('id', appointment_id).execute()
        return True, appointment
    return False, None


def get_available_time_slots(date):
    booked = get_appointments_by_date(date)
    booked_times = [b['time'] for b in booked]
    available = [slot for slot in DEFAULT_TIME_SLOTS if slot not in booked_times]
    return available


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


def send_notification_to_workers(student_name, student_email, dormitory, room, date, time, issue_type, description,
                                 appointment_id):
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
            selected_date_str = selected_date.strftime("%Y-%m-%d")

            # Получаем доступное время
            available_slots = get_available_time_slots(selected_date_str)

            if not available_slots:
                st.warning("⚠️ На выбранную дату нет свободного времени. Пожалуйста, выберите другую дату.")
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
                        "date": selected_date_str,
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
                            send_confirmation_to_student(email, fio, new_id, selected_date_str, selected_time,
                                                         dormitory, type_map[issue_type_display])
                            send_notification_to_workers(fio, email, dormitory, room, selected_date_str, selected_time,
                                                         type_map[issue_type_display], description, new_id)

                            st.success(f"✅ Запись №{new_id} успешно создана! Подтверждение придет на вашу почту.")
                            st.balloons()
                        else:
                            st.error("❌ Ошибка при сохранении записи. Попробуйте еще раз.")
                    except Exception as e:
                        st.error(f"❌ Ошибка: {e}")

    # ===== ВКЛАДКА 2: МОИ ЗАПИСИ (ОТМЕНА) =====
    with tab2:
        st.markdown("### Мои записи на прием")

        view_email = st.text_input("Введите ваш email для просмотра записей", key="view_email")

        if st.button("🔍 Показать мои записи", key="show_my_appointments"):
            if view_email and validate_email(view_email):
                appointments = get_appointments_by_email(view_email)
                if appointments:
                    st.success(f"Найдено {len(appointments)} записей")

                    # Показываем таблицу
                    df = pd.DataFrame(appointments)
                    df_display = df[['id', 'date', 'time', 'issue_type', 'dormitory', 'room', 'status']]
                    df_display.columns = ['ID', 'Дата', 'Время', 'Вопрос', 'Общежитие', 'Комната', 'Статус']
                    st.dataframe(df_display, use_container_width=True)

                    # Отмена записи
                    st.markdown("---")
                    st.markdown("### Отмена записи")
                    cancel_id = st.text_input("Введите ID записи для отмены")

                    if st.button("❌ Отменить запись"):
                        if cancel_id:
                            try:
                                appointment_id_int = int(cancel_id)
                                success, appointment = cancel_appointment(appointment_id_int, view_email)

                                if success and appointment:
                                    send_cancellation_notification(view_email, appointment['fio'], appointment_id_int,
                                                                   appointment['date'], appointment['time'])
                                    # Уведомляем работников об отмене
                                    worker_body = f"Запись №{appointment_id_int} была отменена студентом {appointment['fio']}"
                                    for worker_email in WORKER_EMAILS:
                                        send_email(worker_email, f"❌ Отмена записи №{appointment_id_int}", worker_body)
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