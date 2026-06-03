import streamlit as st
from datetime import datetime, timedelta
from supabase import create_client
import pandas as pd
from io import BytesIO
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
SMTP_EMAIL = st.secrets["SMTP_EMAIL"]
SMTP_PASSWORD = st.secrets["SMTP_PASSWORD"]

PASSWORD = "admin123"

SCHEDULE = {
    "Monday": {"start": "14:00", "end": "16:30", "slot_minutes": 10, "name": "Понедельник"},
    "Tuesday": {"start": "14:00", "end": "16:30", "slot_minutes": 10, "name": "Вторник"},
    "Wednesday": {"start": None, "end": None, "slot_minutes": 10, "name": "Среда"},
    "Thursday": {"start": "14:00", "end": "16:30", "slot_minutes": 10, "name": "Четверг"},
    "Friday": {"start": "13:00", "end": "15:00", "slot_minutes": 10, "name": "Пятница"},
    "Saturday": {"start": None, "end": None, "slot_minutes": 10, "name": "Суббота"},
    "Sunday": {"start": None, "end": None, "slot_minutes": 10, "name": "Воскресенье"}
}

def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def get_all_appointments():
    try:
        supabase = get_supabase()
        response = supabase.table('appointments').select('*').order('date', desc=False).order('time', desc=False).execute()
        if response.data:
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Ошибка подключения к таблице appointments: {e}")
        return pd.DataFrame()

def update_appointment_status(appointment_id, new_status):
    try:
        supabase = get_supabase()
        supabase.table('appointments').update({'status': new_status}).eq('id', appointment_id).execute()
        
        response = supabase.table('appointments').select('*').eq('id', appointment_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        st.error(f"Ошибка при обновлении статуса: {e}")
        return None

def update_schedule(new_schedule):
    global SCHEDULE
    SCHEDULE = new_schedule

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

def send_status_notification(student_email, student_name, appointment_id, date, time, new_status):
    subject = f"📝 Изменение статуса записи №{appointment_id}"
    body = f"""
Здравствуйте, {student_name}!

Статус вашей записи на прием изменился.

📅 Дата: {date}
⏰ Время: {time}
📌 Новый статус: {new_status}

С уважением,
Администрация Жилищно-бытового управления СПбГЭУ
"""
    return send_email(student_email, subject, body)

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Записи')
    return output.getvalue()

def main():
    st.title("🔐 Панель сотрудника ЖБУ | Управление записью на прием")

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        with st.form("login_form"):
            password_input = st.text_input("Введите пароль для доступа", type="password")
            submitted = st.form_submit_button("Войти")

            if submitted:
                if password_input == PASSWORD:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("❌ Неверный пароль!")
        return

    col, col0 = st.columns([2, 1])
    with col:
        st.success("✅ Вы вошли как сотрудник ЖБУ")

    with col0:
        if st.button("🚪 Выйти"):
            st.session_state.authenticated = False
            st.rerun()

    with st.expander("📅 Текущее расписание приема", expanded=True):
        schedule_text = ""
        for day_key, day_info in SCHEDULE.items():
            if day_info["start"]:
                schedule_text += f"- **{day_info['name']}:** {day_info['start']} — {day_info['end']} (каждые {day_info['slot_minutes']} мин)\n"
        st.markdown(schedule_text)

    st.markdown("### Все записи на прием")
    
    appointments_df = get_all_appointments()
    
    if appointments_df.empty:
        st.info("Пока нет ни одной записи")
        return
    
    display_df = appointments_df.rename(columns={
        "id": "ID",
        "date": "Дата",
        "time": "Время",
        "fio": "ФИО",
        "email": "Email",
        "dormitory": "Общежитие",
        "room": "Комната",
        "issue_type": "Вопрос",
        "description": "Описание",
        "status": "Статус"
    })
    
    col1, col2, col3 = st.columns(3)
    with col1:
        date_filter = st.selectbox("Фильтр по дате", ["Все", "Сегодня", "Завтра", "Выбрать дату"])
    with col2:
        status_filter = st.selectbox("Фильтр по статусу", ["Все", "Запланировано", "Подтверждено", "Выполнено", "Отменено"])
    with col3:
        type_options = ["Все"] + display_df["Вопрос"].unique().tolist()
        type_filter = st.selectbox("Фильтр по типу вопроса", type_options)
    
    filtered_df = display_df.copy()
    
    today = datetime.now().date()
    if date_filter == "Сегодня":
        filtered_df = filtered_df[filtered_df["Дата"] == today.strftime("%Y-%m-%d")]
    elif date_filter == "Завтра":
        tomorrow = today + timedelta(days=1)
        filtered_df = filtered_df[filtered_df["Дата"] == tomorrow.strftime("%Y-%m-%d")]
    elif date_filter == "Выбрать дату":
        selected_date_filter = st.date_input("Выберите дату", value=today)
        filtered_df = filtered_df[filtered_df["Дата"] == selected_date_filter.strftime("%Y-%m-%d")]
    
    if status_filter != "Все":
        filtered_df = filtered_df[filtered_df["Статус"] == status_filter]
    
    if type_filter != "Все":
        filtered_df = filtered_df[filtered_df["Вопрос"] == type_filter]
    
    st.info(f"📊 Найдено записей: {len(filtered_df)} из {len(display_df)}")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Всего в фильтре", len(filtered_df))
    with col2:
        st.metric("Запланировано", len(filtered_df[filtered_df["Статус"] == "Запланировано"]))
    with col3:
        st.metric("Подтверждено", len(filtered_df[filtered_df["Статус"] == "Подтверждено"]))
    with col4:
        st.metric("Выполнено", len(filtered_df[filtered_df["Статус"] == "Выполнено"]))

    if st.button("🔄 Обновить сейчас"):
            st.rerun()
        
    st.dataframe(filtered_df, use_container_width=True)
    
    st.markdown("---")
    st.markdown("### Изменить статус записи")
    
    col1, col2 = st.columns(2)
    with col1:
        if not filtered_df.empty:
            selected_id = st.selectbox("Выберите ID записи", filtered_df["ID"].tolist())
        else:
            selected_id = None
            st.warning("Нет записей для изменения")
    
    with col2:
        new_status = st.selectbox("Новый статус", ["Запланировано", "Подтверждено", "Выполнено", "Отменено"])
    
    if st.button("📝 Обновить статус") and selected_id:
        appointment = update_appointment_status(selected_id, new_status)
        if appointment:
            send_status_notification(
                appointment["email"], 
                appointment["fio"], 
                selected_id, 
                appointment["date"], 
                appointment["time"], 
                new_status
            )
            st.success(f"✅ Статус записи #{selected_id} изменен на '{new_status}', студент уведомлен")
            st.rerun()
        else:
            st.error("❌ Ошибка при обновлении статуса")
    
    st.markdown("---")
    st.markdown("### 📥 Экспорт данных")
    
    export_type = st.radio(
        "Что экспортировать?",
        ["Все записи", "Только отфильтрованные"],
        horizontal=True
    )
    
    export_df = filtered_df if export_type == "Только отфильтрованные" else display_df
    
    excel_data = to_excel(export_df)
    st.download_button(
        label="📊 Скачать в Excel формате",
        data=excel_data,
        file_name=f"zapis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

if __name__ == "__main__":
    main()
