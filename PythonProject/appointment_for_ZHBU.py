import streamlit as st
from datetime import datetime, timedelta
from supabase import create_client
import pandas as pd
from io import BytesIO
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ===== НАСТРОЙКИ ИЗ СЕКРЕТОВ =====
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
SMTP_EMAIL = st.secrets["SMTP_EMAIL"]
SMTP_PASSWORD = st.secrets["SMTP_PASSWORD"]

PASSWORD = "admin123"

# Доступное время для записи (по умолчанию)
DEFAULT_TIME_SLOTS = [
    "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"
]

# ===== ФУНКЦИИ РАБОТЫ С БАЗОЙ =====
def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def get_all_appointments():
    """Получает все записи"""
    try:
        supabase = get_supabase()
        response = supabase.table('appointments').select('*').order('date', asc=True).order('time', asc=True).execute()
        if response.data:
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Ошибка подключения к таблице appointments: {e}")
        st.info("Убедитесь, что таблица 'appointments' создана в Supabase")
        return pd.DataFrame()

def get_time_slots():
    """Получает доступное время из настроек"""
    try:
        supabase = get_supabase()
        response = supabase.table('settings').select('value').eq('key', 'time_slots').execute()
        if response.data:
            return response.data[0]['value'].split(',')
        return DEFAULT_TIME_SLOTS
    except Exception:
        return DEFAULT_TIME_SLOTS

def update_time_slots(new_slots):
    """Обновляет доступное время"""
    try:
        supabase = get_supabase()
        response = supabase.table('settings').select('*').eq('key', 'time_slots').execute()
        if response.data:
            supabase.table('settings').update({'value': ','.join(new_slots)}).eq('key', 'time_slots').execute()
        else:
            supabase.table('settings').insert({'key': 'time_slots', 'value': ','.join(new_slots)}).execute()
        return True
    except Exception as e:
        st.error(f"Ошибка при сохранении настроек: {e}")
        return False

def update_appointment_status(appointment_id, new_status):
    """Обновляет статус записи"""
    try:
        supabase = get_supabase()
        supabase.table('appointments').update({'status': new_status}).eq('id', appointment_id).execute()
        
        # Получаем данные записи для уведомления
        response = supabase.table('appointments').select('*').eq('id', appointment_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        st.error(f"Ошибка при обновлении статуса: {e}")
        return None

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

# ===== ФУНКЦИЯ ЭКСПОРТА В EXCEL =====
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Записи')
    return output.getvalue()

# ===== ОСНОВНОЕ ПРИЛОЖЕНИЕ =====
def main():
    st.title("🔐 Панель сотрудника ЖБУ | Управление записью на прием")

    # Авторизация
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

    st.success("✅ Вы вошли как сотрудник ЖБУ")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚪 Выйти"):
            st.session_state.authenticated = False
            st.rerun()
    with col2:
        if st.button("🔄 Обновить сейчас"):
            st.rerun()

    # ===== НАСТРОЙКА ВРЕМЕНИ ПРИЕМА =====
    with st.expander("⚙️ Настройка времени приема", expanded=False):
        st.markdown("### Редактирование доступного времени")
        
        current_slots = get_time_slots()
        st.info(f"Текущее доступное время: {', '.join(current_slots)}")
        
        new_slots_text = st.text_area(
            "Введите доступное время (каждое время с новой строки)",
            value="\n".join(current_slots),
            help="Пример:\n10:00\n11:00\n12:00"
        )
        
        if st.button("💾 Сохранить настройки времени"):
            new_slots = [slot.strip() for slot in new_slots_text.split("\n") if slot.strip()]
            if new_slots:
                if update_time_slots(new_slots):
                    st.success(f"✅ Время обновлено: {', '.join(new_slots)}")
                    st.rerun()
                else:
                    st.error("❌ Ошибка при сохранении")
            else:
                st.error("❌ Введите хотя бы одно время")

    # ===== ПРОСМОТР ВСЕХ ЗАПИСЕЙ =====
    st.markdown("### Все записи на прием")
    
    appointments_df = get_all_appointments()
    
    if appointments_df.empty:
        st.info("Пока нет ни одной записи")
        return
    
    # Переименовываем колонки
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
    
    # ===== ФИЛЬТРЫ =====
    col1, col2, col3 = st.columns(3)
    with col1:
        date_filter = st.selectbox("Фильтр по дате", ["Все", "Сегодня", "Завтра", "Выбрать дату"])
    with col2:
        status_filter = st.selectbox("Фильтр по статусу", ["Все", "Запланировано", "Подтверждено", "Выполнено", "Отменено"])
    with col3:
        type_options = ["Все"] + display_df["Вопрос"].unique().tolist()
        type_filter = st.selectbox("Фильтр по типу вопроса", type_options)
    
    # Применяем фильтры
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
    
    # Статистика
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Всего в фильтре", len(filtered_df))
    with col2:
        st.metric("Запланировано", len(filtered_df[filtered_df["Статус"] == "Запланировано"]))
    with col3:
        st.metric("Подтверждено", len(filtered_df[filtered_df["Статус"] == "Подтверждено"]))
    with col4:
        st.metric("Выполнено", len(filtered_df[filtered_df["Статус"] == "Выполнено"]))
    
    st.dataframe(filtered_df, use_container_width=True)
    
    # ===== ИЗМЕНЕНИЕ СТАТУСА ЗАПИСИ =====
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
    
    # ===== ЭКСПОРТ В EXCEL =====
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
