import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
import random

# ---------------- SETTINGS ----------------

st.set_page_config(
    page_title="Отгрузка маршрутов",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Применяем пользовательский CSS
st.markdown("""
    <style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
    }
    .stButton button {
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
        font-size: 16px;
        padding: 10px 20px;
        border-radius: 8px;
        border: none;
        width: 100%;
    }
    .stButton button:hover {
        background-color: #45a049;
    }
    </style>
""", unsafe_allow_html=True)

SHEET_ID = "1hKZ8ggNLW-OY1bV8xAW7PKl50Fof2co86oxGK92YPAA"
SHEET_NAME = "Маршруты"

# ---------------- GOOGLE SHEETS ----------------

def connect_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"],
        scope
    )

    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    return sheet

def get_data():
    sheet = connect_sheet()
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    required_columns = ["Статус отгрузки", "Дата отгрузки факт", "Номер машины", "Водитель", "№ пломбы"]
    for col in required_columns:
        if col not in df.columns:
            df[col] = ""
    
    if "кол-во штук в заказе" in df.columns:
        df["кол-во штук в заказе"] = pd.to_numeric(df["кол-во штук в заказе"], errors='coerce').fillna(0)
    
    return df

def update_route(route_name, car_number, driver, plomb):
    sheet = connect_sheet()
    data = sheet.get_all_records()
    headers = sheet.row_values(1)
    
    extra_columns = ["Номер машины", "Водитель", "№ пломбы"]
    current_headers = headers.copy()
    
    for col_name in extra_columns:
        if col_name not in current_headers:
            sheet.update_cell(1, len(current_headers) + 1, col_name)
            current_headers.append(col_name)
    
    headers = sheet.row_values(1)
    
    status_col = headers.index("Статус отгрузки") + 1
    fact_col = headers.index("Дата отгрузки факт") + 1
    car_col = headers.index("Номер машины") + 1
    driver_col = headers.index("Водитель") + 1
    plomb_col = headers.index("№ пломбы") + 1
    
    for idx, row in enumerate(data, start=2):
        if str(row.get("Номер маршрута", "")) == str(route_name):
            sheet.update_cell(idx, status_col, "ОТГРУЖЕН")
            sheet.update_cell(idx, fact_col, datetime.now().strftime("%d.%m.%Y %H:%M"))
            sheet.update_cell(idx, car_col, car_number)
            sheet.update_cell(idx, driver_col, driver)
            sheet.update_cell(idx, plomb_col, plomb)
            break

# ---------------- PDF GENERATION ----------------

def generate_pdf(route_df, route, driver, car, plomb):
    buffer = BytesIO()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=15*mm,
        bottomMargin=15*mm
    )
    
    styles = getSampleStyleSheet()
    
    # Стили для нормального отображения
    title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Normal'],
        fontSize=18,
        alignment=1,  # Центр
        spaceAfter=15,
        fontName='Helvetica-Bold'
    )
    
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=11,
        alignment=0,
        spaceAfter=8,
        fontName='Helvetica'
    )
    
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontSize=9,
        alignment=0,
        fontName='Helvetica'
    )
    
    cell_center_style = ParagraphStyle(
        'CellCenterStyle',
        parent=styles['Normal'],
        fontSize=9,
        alignment=1,  # Центр
        fontName='Helvetica'
    )
    
    elements = []
    
    # Случайный номер
    random_num = random.randint(10000, 99999)
    
    total_boxes = int(route_df["кол-во штук в заказе"].sum())
    stores_count = len(route_df)
    
    # Заголовок
    elements.append(Paragraph("МАРШРУТНЫЙ ЛИСТ", title_style))
    elements.append(Spacer(1, 5))
    
    # Номер
    elements.append(Paragraph(f"№ {random_num}", header_style))
    elements.append(Spacer(1, 10))
    
    # Информация о водителе и машине
    info_lines = [
        f"Водитель: {driver}",
        f"А/м гос номер: {car}",
        f"Дата: {datetime.now().strftime('%d.%m.%Y')}",
        f"№ пломбы: {plomb}"
    ]
    
    for line in info_lines:
        elements.append(Paragraph(line, header_style))
    
    elements.append(Spacer(1, 10))
    
    # Строка с коробками
    elements.append(Paragraph(
        f"Водитель {driver} получил всего __________ коробов для {stores_count} магазинов",
        header_style
    ))
    elements.append(Spacer(1, 15))
    
    # Заголовки таблицы
    table_data = []
    
    # Шапка таблицы
    headers = [
        "№ п/п", "Заказ", "Магазин", "Адрес",
        "№ маршрута", "№ пломбы", "Коробов выдано",
        "Коробов получено", "Подпись и печать", "Подпись водителя"
    ]
    
    table_data.append([Paragraph(h, cell_center_style) for h in headers])
    
    # Данные
    for idx, (_, row) in enumerate(route_df.iterrows(), start=1):
        table_data.append([
            Paragraph(str(idx), cell_center_style),
            Paragraph(str(row.get("№ заказа", "")), cell_style),
            Paragraph(str(row.get("Название магазина", ""))[:40], cell_style),
            Paragraph(str(row.get("Адрес магазина", ""))[:50], cell_style),
            Paragraph(str(route), cell_center_style),
            Paragraph(str(plomb), cell_center_style),
            Paragraph(str(int(row.get("кол-во штук в заказе", 0))), cell_center_style),
            Paragraph("________", cell_center_style),
            Paragraph("_________", cell_center_style),
            Paragraph("_________", cell_center_style)
        ])
    
    # Ширина колонок
    col_widths = [
        12*mm, 20*mm, 30*mm, 40*mm,
        18*mm, 18*mm, 20*mm, 22*mm, 22*mm, 22*mm
    ]
    
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # Итого
    elements.append(Paragraph(f"Итого коробов: {total_boxes}", header_style))
    elements.append(Spacer(1, 30))
    
    # Подписи
    signature_lines = [
        "Подпись водителя: ___________________________",
        "Подпись принимающей стороны: ___________________________",
        "Печать: ___________________________"
    ]
    
    for line in signature_lines:
        elements.append(Paragraph(line, header_style))
        elements.append(Spacer(1, 5))
    
    # Строим PDF
    doc.build(elements)
    buffer.seek(0)
    
    return buffer

# ---------------- UI ----------------

st.title("🚚 Система управления отгрузкой маршрутов")
st.markdown("---")

try:
    df = get_data()
except Exception as e:
    st.error(f"❌ Ошибка подключения к Google Sheets: {str(e)}")
    st.stop()

# Фильтрация данных
if "Статус отгрузки" in df.columns:
    not_shipped = df[df["Статус отгрузки"] != "ОТГРУЖЕН"]
    shipped = df[df["Статус отгрузки"] == "ОТГРУЖЕН"]
else:
    not_shipped = df.copy()
    shipped = pd.DataFrame()

# ---------------- METRICS ----------------
st.subheader("📊 Сводная информация")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("🚫 Не отгружено маршрутов", not_shipped["Номер маршрута"].nunique() if len(not_shipped) > 0 else 0)

with col2:
    st.metric("✅ Отгружено маршрутов", shipped["Номер маршрута"].nunique() if len(shipped) > 0 else 0)

with col3:
    st.metric("📍 Всего точек доставки", len(not_shipped))

with col4:
    total_boxes = not_shipped["кол-во штук в заказе"].sum() if len(not_shipped) > 0 else 0
    st.metric("📦 Всего коробок к отгрузке", int(total_boxes))

with col5:
    completion_rate = (shipped["Номер маршрута"].nunique() / df["Номер маршрута"].nunique() * 100) if len(df) > 0 else 0
    st.metric("📈 Прогресс отгрузки", f"{completion_rate:.1f}%")

st.markdown("---")

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.header("🔍 Детальная информация")
    
    view_type = st.radio("Показать:", ["Неотгруженные маршруты", "Отгруженные маршруты", "Все маршруты"])
    
    if view_type == "Неотгруженные маршруты":
        display_df = not_shipped
    elif view_type == "Отгруженные маршруты":
        display_df = shipped
    else:
        display_df = df
    
    if len(display_df) > 0:
        route_summary = display_df.groupby("Номер маршрута").agg({
            "№ заказа": "count",
            "кол-во штук в заказе": "sum"
        }).rename(columns={"№ заказа": "Кол-во заказов", "кол-во штук в заказе": "Коробок"})
        
        st.dataframe(route_summary, use_container_width=True)
        
        if len(route_summary) > 0:
            selected_route = st.selectbox("Выберите маршрут для детализации", route_summary.index)
            if selected_route:
                route_details = display_df[display_df["Номер маршрута"] == selected_route]
                st.markdown("**Состав маршрута:**")
                st.dataframe(
                    route_details[["№ заказа", "Название магазина", "Адрес магазина", "кол-во штук в заказе"]],
                    use_container_width=True,
                    hide_index=True
                )

st.markdown("---")

# ---------------- SHIPMENT FORM ----------------
st.subheader("🚛 Отгрузка маршрутов")

col1, col2, col3 = st.columns(3)

with col1:
    car_number = st.text_input("🚐 Номер машины", placeholder="А123ВС77")

with col2:
    driver = st.text_input("👤 Водитель", placeholder="Фамилия И.О.")

with col3:
    plomb = st.text_input("🔒 № пломбы", placeholder="номер пломбы")

st.markdown("---")

# Выбор маршрутов
not_shipped_routes = sorted(not_shipped["Номер маршрута"].dropna().unique()) if len(not_shipped) > 0 else []

if len(not_shipped_routes) > 0:
    st.subheader("📋 Выберите маршруты для отгрузки")
    
    selected_routes = st.multiselect(
        "Маршруты, готовые к отгрузке:",
        options=not_shipped_routes,
        format_func=lambda x: f"🗺️ Маршрут {x}"
    )
    
    if selected_routes:
        st.markdown("### 📦 Детали выбранных маршрутов")
        
        details_df = not_shipped[not_shipped["Номер маршрута"].isin(selected_routes)]
        
        for route in selected_routes:
            route_data = details_df[details_df["Номер маршрута"] == route]
            total_boxes_route = int(route_data["кол-во штук в заказе"].sum())
            
            with st.expander(f"🗺️ Маршрут {route} - {len(route_data)} магазинов, {total_boxes_route} коробок", expanded=True):
                st.dataframe(
                    route_data[["№ заказа", "Название магазина", "Адрес магазина", "кол-во штук в заказе"]],
                    use_container_width=True,
                    hide_index=True
                )
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            ship_button = st.button("✅ ОТГРУЗИТЬ ВЫБРАННЫЕ МАРШРУТЫ", type="primary", use_container_width=True)
        
        if ship_button:
            if not car_number:
                st.error("❌ Введите номер машины!")
                st.stop()
            
            if not driver:
                st.error("❌ Введите ФИО водителя!")
                st.stop()
            
            success_count = 0
            pdf_files = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, route in enumerate(selected_routes):
                status_text.text(f"Отгрузка маршрута {route}...")
                
                route_df = df[df["Номер маршрута"] == route]
                
                update_route(route, car_number, driver, plomb)
                
                pdf_buffer = generate_pdf(route_df, route, driver, car_number, plomb)
                pdf_files.append((route, pdf_buffer))
                
                success_count += 1
                progress_bar.progress((i + 1) / len(selected_routes))
            
            status_text.text("✅ Отгрузка завершена!")
            
            st.success(f"✅ Успешно отгружено {success_count} маршрутов!")
            
            st.subheader("📄 Скачать маршрутные листы")
            
            cols = st.columns(min(3, len(pdf_files)))
            for idx, (route, pdf_buffer) in enumerate(pdf_files):
                with cols[idx % 3]:
                    st.download_button(
                        label=f"📄 Маршрут {route}",
                        data=pdf_buffer,
                        file_name=f"Маршрутный_лист_{route}.pdf",
                        mime="application/pdf",
                        key=f"pdf_{route}"
                    )
            
            if st.button("🔄 Обновить данные", key="refresh"):
                st.rerun()
else:
    st.info("🎉 Все маршруты отгружены! Отличная работа!")

st.markdown("---")
st.caption(f"Последнее обновление: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
