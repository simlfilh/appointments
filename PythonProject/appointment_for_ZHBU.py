import streamlit as st
from datetime import datetime, timedelta
from supabase import create_client
import pandas as pd
from io import BytesIO
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

st.set_page_config(
    page_title="Управление электронной записью | Общежития СПбГЭУ",
    page_icon="📆",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

def delete_appointment(appointment_id):
    """Удаление записи по ID"""
    try:
        supabase = get_supabase()
        
        # Получаем данные записи перед удалением для уведомления
        response = supabase.table('appointments').select('*').eq('id', appointment_id).execute()
        if response.data:
            appointment_data = response.data[0]
            
            # Удаляем запись
            supabase.table('appointments').delete().eq('id', appointment_id).execute()
            
            # Отправляем уведомление работникам
            send_deletion_notification_to_workers(appointment_data)
            
            return True, f"Запись №{appointment_id} успешно удалена"
        else:
            return False, "Запись не найдена"
    except Exception as e:
        return False, f"Ошибка при удалении: {str(e)}"

def send_deletion_notification_to_workers(appointment_data):
    """Отправка уведомления работникам об удалении записи"""
    subject = f"🗑️ ЗАПИСЬ №{appointment_data['id']} УДАЛЕНА"
    body = f"""
Была удалена следующая запись на прием:

📋 ЗАПИСЬ №{appointment_data['id']}
👤 Студент: {appointment_data['fio']}
📧 Email: {appointment_data['email']}
🏠 Общежитие: {appointment_data['dormitory']}
🚪 Комната: {appointment_data['room']}
📅 Дата: {appointment_data['date']}
⏰ Время: {appointment_data['time']}
❓ Вопрос: {appointment_data['issue_type']}
📝 Описание: {appointment_data['description']}
📌 Статус: УДАЛЕНА

Запись была удалена из системы.
"""
    WORKER_EMAILS = [
        "valeraforumsch@gmail.com"
    ]
    
    for worker_email in WORKER_EMAILS:
        try:
            msg = MIMEMultipart()
            msg["From"] = SMTP_EMAIL
            msg["To"] = worker_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))
            
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()
        except Exception as e:
            print(f"Ошибка отправки уведомления работнику {worker_email}: {e}")

def send_deletion_notification_to_student(appointment_data):
    """Отправка уведомления студенту об удалении записи"""
    subject = f"❌ Ваша запись №{appointment_data['id']} была удалена"
    body = f"""
Здравствуйте, {appointment_data['fio']}!

К сожалению, ваша запись на прием была удалена администратором.

📅 Дата: {appointment_data['date']}
⏰ Время: {appointment_data['time']}
❓ Вопрос: {appointment_data['issue_type']}

Если у вас есть вопросы, пожалуйста, обратитесь в Жилищно-бытовое управление.

С уважением,
Администрация Жилищно-бытового управления СПбГЭУ
"""
    return send_email(appointment_data['email'], subject, body)

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
    
    # Создаем копию DataFrame без столбцов, которые не нужны в Excel
    df_to_export = df.copy()
    # Удаляем столбец "Выбрать", если он есть
    if 'Выбрать' in df_to_export.columns:
        df_to_export = df_to_export.drop(columns=['Выбрать'])
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_to_export.to_excel(writer, index=False, sheet_name='Записи')
        
        workbook = writer.book
        worksheet = writer.sheets['Записи']
        
        from openpyxl.styles import Alignment
        
        # Автоматически определяем ширину столбцов
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if cell.value:
                        text_length = len(str(cell.value))
                        if text_length > max_length:
                            max_length = text_length
                except:
                    pass
            adjusted_width = min(max_length + 2, 60)
            worksheet.column_dimensions[column_letter].width = adjusted_width
        
        # Автоматическая высота строк
        for row_idx in range(2, worksheet.max_row + 1):
            max_height = 25
            for col_letter in worksheet.column_dimensions:
                cell = worksheet[f'{col_letter}{row_idx}']
                if cell.value:
                    text = str(cell.value)
                    col_width = worksheet.column_dimensions[col_letter].width or 10
                    chars_per_line = int(col_width * 1.2)
                    lines = (len(text) // chars_per_line) + 1 if chars_per_line > 0 else 1
                    height_needed = lines * 18
                    if height_needed > max_height:
                        max_height = min(height_needed, 150)
            worksheet.row_dimensions[row_idx].height = max_height
        
        # Выравнивание для всех ячеек
        for row in worksheet.iter_rows():
            for cell in row:
                cell.alignment = Alignment(
                    horizontal='left',
                    vertical='center',
                    wrap_text=True
                )
        
        worksheet.freeze_panes = 'A2'
        
    return output.getvalue()

def main():
    st.title("🔐 Панель сотрудника ЖБУ | Управление записью на прием")

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "show_delete_confirm" not in st.session_state:
        st.session_state.show_delete_confirm = False
    if "delete_id" not in st.session_state:
        st.session_state.delete_id = None
    if "checkbox_state" not in st.session_state:
        st.session_state.checkbox_state = {}
    if "show_bulk_delete_confirm" not in st.session_state:
        st.session_state.show_bulk_delete_confirm = False
    if "bulk_delete_ids" not in st.session_state:
        st.session_state.bulk_delete_ids = []

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
                schedule_text += f"- **{day_info['name']}:** {day_info['start']} — {day_info['end']}\n"
        st.markdown(schedule_text)

    st.markdown("### Все записи на прием")
    
    appointments_df = get_all_appointments()
    
    if appointments_df.empty:
        st.info("Пока нет ни одной записи")
        return
    
    # Подготовка данных для отображения
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
    
    # Приводим даты к формату дд.мм.гггг для отображения
    display_df["Дата"] = pd.to_datetime(display_df["Дата"]).dt.strftime("%d.%m.%Y")
    
    # Фильтры
    st.subheader("🔍 Фильтры")
    col1, col2, col3 = st.columns(3)
    with col1:
        date_filter = st.selectbox("Фильтр по дате", ["Все", "Сегодня", "Завтра", "Выбрать дату"])
    with col2:
        status_filter = st.selectbox("Фильтр по статусу", ["Все", "Запланировано", "Подтверждено", "Выполнено", "Отменено"])
    with col3:
        type_options = ["Все", "Заселение в общежитие", "Переселение в другое общежитие", "Выселение из общежития",
                        "Заселение в МСГ (в т. ч. СПО)", "Временная регистрация", "Льготы", "Справки", "Другое"]
        type_filter = st.selectbox("Фильтр по типу вопроса", type_options)
    
    # Применяем фильтры
    filtered_df = display_df.copy()
    
    today = datetime.now().date()
    if date_filter == "Сегодня":
        filtered_df = filtered_df[filtered_df["Дата"] == today.strftime("%d.%m.%Y")]
    elif date_filter == "Завтра":
        tomorrow = today + timedelta(days=1)
        filtered_df = filtered_df[filtered_df["Дата"] == tomorrow.strftime("%d.%m.%Y")]
    elif date_filter == "Выбрать дату":
        selected_date_filter = st.date_input("Выберите дату", value=today)
        filtered_df = filtered_df[filtered_df["Дата"] == selected_date_filter.strftime("%d.%m.%Y")]
    
    if status_filter != "Все":
        filtered_df = filtered_df[filtered_df["Статус"] == status_filter]
    
    if type_filter != "Все":
        filtered_df = filtered_df[filtered_df["Вопрос"] == type_filter]
    
    # Метрики
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Всего в фильтре", len(filtered_df))
    with col2:
        st.metric("Запланировано", len(filtered_df[filtered_df["Статус"] == "Запланировано"]))
    with col3:
        st.metric("Подтверждено", len(filtered_df[filtered_df["Статус"] == "Подтверждено"]))
    with col4:
        st.metric("Выполнено", len(filtered_df[filtered_df["Статус"] == "Выполнено"]))
    
    st.markdown("---")
    
    # Создаем редактируемую таблицу
    if not filtered_df.empty:
        # Добавляем чекбоксы для выбора
        checkbox_key = "appointments_checkbox_state"
        
        if checkbox_key not in st.session_state:
            st.session_state[checkbox_key] = {i: False for i in range(len(filtered_df))}
        
        edit_df = filtered_df.copy()
        edit_df = edit_df.reset_index(drop=True)
        
        # Получаем значения чекбоксов
        checkbox_values = []
        for i in range(len(edit_df)):
            checkbox_values.append(st.session_state[checkbox_key].get(i, False))
        
        edit_df.insert(0, "Выбрать", checkbox_values)
        
        # Настройка колонок для редактора
        column_config = {
            "Выбрать": st.column_config.CheckboxColumn(
                "Выбрать",
                help="Отметьте записи для массового управления",
                default=False,
            ),
            "ID": st.column_config.NumberColumn("№", width="small"),
            "Статус": st.column_config.TextColumn("Статус", width="small"),
            "Дата": st.column_config.TextColumn("Дата", width="small"),
            "Время": st.column_config.TextColumn("Время", width="small"),
            "ФИО": st.column_config.TextColumn("ФИО", width="medium"),
            "Email": st.column_config.TextColumn("Email", width="medium"),
            "Общежитие": st.column_config.TextColumn("Общежитие", width="medium"),
            "Комната": st.column_config.TextColumn("Комната", width="small"),
            "Вопрос": st.column_config.TextColumn("Тип вопроса", width="medium"),
            "Описание": st.column_config.TextColumn("Описание", width="large"),
        }
        
        # Отображаем редактор
        edited_df = st.data_editor(
            edit_df,
            use_container_width=True,
            hide_index=True,
            column_config=column_config,
            disabled=["ID", "Дата", "Время", "ФИО", "Email", "Общежитие", "Комната", "Вопрос", "Описание", "Статус"],
            key="appointments_data_editor"
        )
        
        # Сохраняем состояние чекбоксов
        for i in range(len(edited_df)):
            st.session_state[checkbox_key][i] = edited_df.loc[i, "Выбрать"]
        
        # Получаем выбранные ID
        selected_ids = []
        for i in range(len(edited_df)):
            if edited_df.loc[i, "Выбрать"]:
                selected_ids.append(int(edit_df.loc[i, "ID"]))
        
        # Кнопки управления
        st.markdown("### 🎯 Массовые операции")
        
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("✅ Выбрать все", use_container_width=True):
                for i in range(len(edit_df)):
                    st.session_state[checkbox_key][i] = True
                st.rerun()
            
            if st.button("❌ Снять все", use_container_width=True):
                for i in range(len(edit_df)):
                    st.session_state[checkbox_key][i] = False
                st.rerun()
        
        with col2:
            if selected_ids:
                st.info(f"Выбрано: {len(selected_ids)} записей")
            else:
                st.info("Выберите записи для операций")
        
        with col3:
            new_status_bulk = st.selectbox(
                "Новый статус для выбранных",
                ["Запланировано", "Подтверждено", "Выполнено", "Отменено"],
                key="bulk_status",
                label_visibility="collapsed"
            )
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button(f"🔄 Изменить статус ({len(selected_ids)})", use_container_width=True):
                if not selected_ids:
                    st.warning("Выберите хотя бы одну запись")
                else:
                    success_count = 0
                    for id in selected_ids:
                        appointment = update_appointment_status(id, new_status_bulk)
                        if appointment:
                            send_status_notification(
                                appointment["email"], 
                                appointment["fio"], 
                                id, 
                                appointment["date"], 
                                appointment["time"], 
                                new_status_bulk
                            )
                            success_count += 1
                    if success_count > 0:
                        st.success(f"✅ Статус изменен для {success_count} записей")
                        # Сбрасываем чекбоксы
                        for i in range(len(edit_df)):
                            st.session_state[checkbox_key][i] = False
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Ошибка при обновлении статусов")
        
        with col2:
            if st.button(f"🗑️ Удалить выбранные ({len(selected_ids)})", use_container_width=True, type="primary"):
                if not selected_ids:
                    st.warning("Выберите хотя бы одну запись")
                else:
                    st.session_state.show_bulk_delete_confirm = True
                    st.session_state.bulk_delete_ids = selected_ids
        
        # Диалог подтверждения массового удаления
        if st.session_state.show_bulk_delete_confirm:
            with st.container():
                st.warning(f"⚠️ Вы уверены, что хотите удалить {len(st.session_state.bulk_delete_ids)} записей? Это действие невозможно отменить.")
                
                col_yes, col_no = st.columns(2)
                
                with col_yes:
                    if st.button("✅ Да, удалить все", key="confirm_bulk_delete"):
                        success_count = 0
                        for id in st.session_state.bulk_delete_ids:
                            success, _ = delete_appointment(id)
                            if success:
                                success_count += 1
                        if success_count > 0:
                            st.success(f"✅ Удалено записей: {success_count}")
                            st.session_state.show_bulk_delete_confirm = False
                            st.session_state.bulk_delete_ids = []
                            # Сбрасываем чекбоксы
                            for i in range(len(edit_df)):
                                st.session_state[checkbox_key][i] = False
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ Ошибка при удалении")
                
                with col_no:
                    if st.button("❌ Отмена", key="cancel_bulk_delete"):
                        st.session_state.show_bulk_delete_confirm = False
                        st.session_state.bulk_delete_ids = []
                        st.rerun()
        
        # Отдельная кнопка для обновления
        if st.button("🔄 Обновить данные", use_container_width=True):
            st.rerun()
        
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
            file_name=f"Электронная запись {datetime.now().strftime('%d.%m.%Y_%H:%M:%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    else:
        st.warning("Нет записей для отображения")

if __name__ == "__main__":
    main()
