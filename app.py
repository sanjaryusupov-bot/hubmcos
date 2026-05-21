# app.py

import streamlit as st
import pandas as pd
import gspread
import tempfile
import os

from datetime import datetime

from oauth2client.service_account import ServiceAccountCredentials

from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    HRFlowable,
    PageBreak
)

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm

from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase import pdfmetrics

# ---------------- PDF FONT ----------------

pdfmetrics.registerFont(
    UnicodeCIDFont('HYSMyeongJo-Medium')
)

# ---------------- PAGE ----------------

st.set_page_config(
    page_title="🚚 Отгрузка маршрутов",
    layout="wide"
)

# ---------------- SETTINGS ----------------

SHEET_ID = "1hKZ8ggNLW-OY1bV8xAW7PKl50Fof2co86oxGK92YPAA"
SHEET_NAME = "Маршруты"

# Session state для контроля отгрузки
if 'shipment_completed' not in st.session_state:
    st.session_state.shipment_completed = False

if 'pdf_generated' not in st.session_state:
    st.session_state.pdf_generated = False

# ---------------- CSS ----------------

st.markdown("""
<style>

.main {
    background-color: #F3F4F6;
}

div[data-testid="metric-container"] {
    background: white;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.05);
}

.stButton>button {
    background-color: #16A34A;
    color: white;
    border-radius: 12px;
    border: none;
    padding: 14px 22px;
    font-weight: 700;
    width: 100%;
    font-size: 16px;
}

.stButton>button:hover {
    background-color: #15803D;
}

.stButton>button:disabled {
    background-color: #94A3B8;
    cursor: not-allowed;
}

div[data-testid="stDownloadButton"] > button {
    background-color: #3B82F6;
    color: white;
    border-radius: 12px;
    border: none;
    padding: 14px 22px;
    font-weight: 700;
    width: 100%;
    font-size: 16px;
}

div[data-testid="stDownloadButton"] > button:hover {
    background-color: #2563EB;
}

</style>
""", unsafe_allow_html=True)

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

    sheet = client.open_by_key(
        SHEET_ID
    ).worksheet(
        SHEET_NAME
    )

    return sheet

def get_data():
    sheet = connect_sheet()
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def update_route(route_name, car_number, driver, plomb):
    sheet = connect_sheet()
    data = sheet.get_all_records()
    headers = sheet.row_values(1)

    extra_columns = [
        "Номер машины",
        "Водитель",
        "№ пломбы",
        "Дата отгрузки факт"
    ]

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
        if row["Номер маршрута"] == route_name:
            sheet.update_cell(idx, status_col, "ОТГРУЖЕН")
            sheet.update_cell(idx, fact_col, datetime.now().strftime("%d.%m.%Y %H:%M"))
            sheet.update_cell(idx, car_col, car_number)
            sheet.update_cell(idx, driver_col, driver)
            sheet.update_cell(idx, plomb_col, plomb)

# ---------------- PDF GENERATION ----------------

def generate_delivery_pdf(df, route, driver, car, plomb):
    """Генерация PDF для нескольких магазинов"""
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        filename = tmp_file.name
    
    doc = SimpleDocTemplate(
        filename,
        pagesize=landscape(A4),
        leftMargin=10*mm,
        rightMargin=10*mm,
        topMargin=15*mm,
        bottomMargin=15*mm
    )

    styles = getSampleStyleSheet()
    
    # Стили для кириллицы
    styleTitle = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName='HYSMyeongJo-Medium',
        fontSize=16,
        leading=20,
        alignment=1,  # Center
        spaceAfter=10
    )
    
    styleHeader = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontName='HYSMyeongJo-Medium',
        fontSize=11,
        leading=14,
        spaceAfter=5
    )
    
    styleNormal = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontName='HYSMyeongJo-Medium',
        fontSize=9,
        leading=12
    )
    
    styleBold = ParagraphStyle(
        'CustomBold',
        parent=styles['Normal'],
        fontName='HYSMyeongJo-Medium',
        fontSize=9,
        leading=12,
        alignment=0  # Left
    )
    
    styleSmall = ParagraphStyle(
        'CustomSmall',
        parent=styles['Normal'],
        fontName='HYSMyeongJo-Medium',
        fontSize=8,
        leading=10
    )

    elements = []
    
    total_points = len(df)

    # Заголовок
    title = Paragraph("<b>МАРШРУТНЫЙ ЛИСТ ДОСТАВКИ</b>", styleTitle)
    elements.append(title)
    elements.append(Spacer(1, 8))
    
    # Информация о маршруте в 2 колонки
    info_data = [
        ["<b>Маршрут:</b>", route, "<b>Дата:</b>", datetime.now().strftime("%d.%m.%Y")],
        ["<b>Водитель:</b>", driver, "<b>Номер машины:</b>", car],
        ["<b>№ пломбы:</b>", plomb, "<b>Кол-во магазинов:</b>", str(total_points)]
    ]
    
    info_table = Table(info_data, colWidths=[25*mm, 55*mm, 30*mm, 40*mm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'HYSMyeongJo-Medium'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
    ]))
    
    elements.append(info_table)
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    elements.append(Spacer(1, 10))

    # Таблица с заказами
    table_data = [[
        "<b>№ заказа</b>",
        "<b>Магазин</b>",
        "<b>Адрес</b>",
        "<b>Маршрут</b>",
        "<b>№ пломбы</b>",
        "<b>Выдано<br/>коробок</b>",
        "<b>Получено<br/>коробок</b>",
        "<b>Подпись, печать,<br/>комментарии</b>",
        "<b>Подпись<br/>водителя</b>"
    ]]

    for _, row in df.iterrows():
        # Делаем номер заказа жирным
        order_number = f"<b>{row['№ заказа']}</b>"
        
        table_data.append([
            Paragraph(order_number, styleBold),
            Paragraph(str(row["Название магазина"]), styleSmall),
            Paragraph(str(row["Адрес магазина"]), styleSmall),
            Paragraph(str(row["Номер маршрута"]), styleSmall),
            Paragraph(plomb, styleSmall),
            "",  # Выдано коробок - пустое поле
            "",  # Получено коробок - пустое поле
            "",  # Подпись, комментарии - пустое поле
            ""   # Подпись водителя - пустое поле
        ])

    # Ширина колонок для A4 landscape
    table = Table(
        table_data,
        colWidths=[
            18*mm,  # № заказа
            35*mm,  # Магазин
            45*mm,  # Адрес
            20*mm,  # Маршрут
            18*mm,  # № пломбы
            18*mm,  # Выдано коробок
            18*mm,  # Получено коробок
            35*mm,  # Подпись, комментарии
            25*mm   # Подпись водителя
        ],
        repeatRows=1
    )

    table.setStyle(TableStyle([
        # Header styling
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1F2937")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'HYSMyeongJo-Medium'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,0), 'MIDDLE'),
        
        # Body styling
        ('FONTNAME', (0,1), (-1,-1), 'HYSMyeongJo-Medium'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('VALIGN', (0,1), (-1,-1), 'TOP'),
        
        # Borders
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        
        # Padding
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
        
        # Alignment
        ('ALIGN', (0,1), (0,-1), 'CENTER'),  # Order number center
        ('ALIGN', (3,1), (4,-1), 'CENTER'),  # Route and plomb center
        ('ALIGN', (5,1), (8,-1), 'CENTER'),  # Empty fields center
        
        # Left align for text columns
        ('ALIGN', (1,1), (2,-1), 'LEFT'),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 15))
    
    # Примечания внизу
    notes = Paragraph(
        "<b>Примечания:</b><br/>"
        "• Количество коробок заполняется при отгрузке<br/>"
        "• Получение подтверждается подписью и печатью",
        styleSmall
    )
    elements.append(notes)

    doc.build(elements)
    return filename

# ---------------- LOAD DATA ----------------

try:
    df = get_data()
except Exception as e:
    st.error("Ошибка подключения Google Sheets")
    st.exception(e)
    st.stop()

# ---------------- FILTERS ----------------

not_shipped = df[df["Статус отгрузки"] != "ОТГРУЖЕН"]
shipped = df[df["Статус отгрузки"] == "ОТГРУЖЕН"]

# ---------------- TITLE ----------------

st.title("🚚 Система отгрузки маршрутов")

# ---------------- METRICS ----------------

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Не отгружено",
    not_shipped["Номер маршрута"].nunique()
)

col2.metric(
    "Отгружено",
    shipped["Номер маршрута"].nunique()
)

col3.metric(
    "Точек",
    len(not_shipped)
)

col4.metric(
    "Коробок (план)",
    int(not_shipped["кол-во штук в заказе"].sum())
)

st.divider()

# ---------------- SUMMARY NOT SHIPPED ----------------

st.subheader("📊 Итоги по неотгруженным точкам")

summary_not_shipped = not_shipped[[
    "Название магазина",
    "Адрес магазина",
    "кол-во штук в заказе"
]].copy()

summary_not_shipped.columns = ["Магазин", "Адрес", "Кол-во шт"]

st.dataframe(
    summary_not_shipped,
    use_container_width=True,
    height=300,
    hide_index=True
)

st.divider()

# ---------------- FORM ----------------

if not st.session_state.shipment_completed:
    left, right = st.columns([1, 1])

    with left:
        st.subheader("🚛 Данные машины")
        car_number = st.text_input("Номер машины")
        driver = st.text_input("Водитель")
        plomb = st.text_input("№ пломбы")

    with right:
        st.subheader("📦 Маршруты")
        routes = sorted(not_shipped["Номер маршрута"].dropna().unique())
        selected_routes = st.multiselect("Выберите маршруты", routes)

    # ---------------- DETAILS ----------------
    if selected_routes:
        st.subheader("📋 Детали маршрутов")

        details_df = not_shipped[
            not_shipped["Номер маршрута"].isin(selected_routes)
        ]

        st.dataframe(
            details_df[[
                "№ заказа",
                "Название магазина",
                "Адрес магазина",
                "Номер маршрута",
                "кол-во штук в заказе"
            ]],
            use_container_width=True,
            height=400
        )

    # ---------------- SHIP BUTTON ----------------
    if st.button("✅ ОТГРУЗИТЬ И СОЗДАТЬ PDF"):
        if not car_number:
            st.warning("Введите номер машины")
            st.stop()

        if not driver:
            st.warning("Введите ФИО водителя")
            st.stop()

        if not plomb:
            st.warning("Введите номер пломбы")
            st.stop()

        if not selected_routes:
            st.warning("Выберите маршрут")
            st.stop()

        # Генерируем PDF для каждого маршрута
        pdf_files = []
        
        for route in selected_routes:
            route_df = df[df["Номер маршрута"] == route]
            
            # Обновляем статус в Google Sheets
            update_route(route, car_number, driver, plomb)
            
            # Генерируем PDF
            pdf_file = generate_delivery_pdf(
                route_df,
                route,
                driver,
                car_number,
                plomb
            )
            pdf_files.append((route, pdf_file))
        
        # Сохраняем файлы в session state для скачивания
        st.session_state.pdf_files = pdf_files
        st.session_state.shipment_completed = True
        st.session_state.selected_routes = selected_routes
        st.rerun()

# ---------------- DOWNLOAD SECTION ----------------
else:
    st.success("✅ Маршруты успешно отгружены!")
    st.info("📄 Скачайте PDF-листы перед продолжением работы")
    
    # Кнопки скачивания для каждого маршрута
    for route, pdf_file in st.session_state.pdf_files:
        with open(pdf_file, "rb") as f:
            st.download_button(
                label=f"📄 Скачать маршрутный лист {route}",
                data=f,
                file_name=f"Маршрутный_лист_{route}.pdf",
                mime="application/pdf",
                key=f"download_{route}"
            )
    
    st.divider()
    
    # Кнопка для печати всех PDF (если нужно несколько)
    if len(st.session_state.pdf_files) > 1:
        st.info("💡 Для печати всех маршрутов скачайте каждый файл отдельно")
    
    # Кнопка сброса
    if st.button("🔄 Начать новую отгрузку"):
        # Очищаем временные файлы
        for _, pdf_file in st.session_state.pdf_files:
            try:
                os.unlink(pdf_file)
            except:
                pass
        
        st.session_state.shipment_completed = False
        st.session_state.pdf_files = []
        st.session_state.selected_routes = []
        st.rerun()
