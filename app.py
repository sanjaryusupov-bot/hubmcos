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
    HRFlowable
)

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm, cm

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

# Инициализация session state
if 'shipment_completed' not in st.session_state:
    st.session_state.shipment_completed = False

if 'pdf_file' not in st.session_state:
    st.session_state.pdf_file = None

if 'selected_routes' not in st.session_state:
    st.session_state.selected_routes = []

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
    sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    return sheet

def get_data():
    sheet = connect_sheet()
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def update_routes(routes_list, car_number, driver, plomb):
    sheet = connect_sheet()
    data = sheet.get_all_records()
    headers = sheet.row_values(1)

    extra_columns = ["Номер машины", "Водитель", "№ пломбы", "Дата отгрузки факт"]
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
        if row["Номер маршрута"] in routes_list:
            sheet.update_cell(idx, status_col, "ОТГРУЖЕН")
            sheet.update_cell(idx, fact_col, datetime.now().strftime("%d.%m.%Y %H:%M"))
            sheet.update_cell(idx, car_col, car_number)
            sheet.update_cell(idx, driver_col, driver)
            sheet.update_cell(idx, plomb_col, plomb)

# ---------------- PDF GENERATION ----------------

def generate_delivery_pdf(all_data, routes_list, driver, car, plomb):
    """Генерация ОДНОГО PDF для всех выбранных маршрутов"""
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        filename = tmp_file.name
    
    # Создаем документ с точными отступами
    doc = SimpleDocTemplate(
        filename,
        pagesize=landscape(A4),
        leftMargin=15*mm,
        rightMargin=15*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )

    styles = getSampleStyleSheet()
    
    # Стили для кириллицы
    styleTitle = ParagraphStyle(
        'CustomTitle',
        parent=styles['Normal'],
        fontName='HYSMyeongJo-Medium',
        fontSize=16,
        leading=20,
        alignment=1,  # Center alignment
        spaceAfter=12,
        spaceBefore=6
    )
    
    styleInfo = ParagraphStyle(
        'CustomInfo',
        parent=styles['Normal'],
        fontName='HYSMyeongJo-Medium',
        fontSize=10,
        leading=14,
        spaceAfter=4
    )
    
    styleInfoBold = ParagraphStyle(
        'CustomInfoBold',
        parent=styles['Normal'],
        fontName='HYSMyeongJo-Medium',
        fontSize=10,
        leading=14,
        spaceAfter=4
    )
    
    styleCell = ParagraphStyle(
        'CustomCell',
        parent=styles['Normal'],
        fontName='HYSMyeongJo-Medium',
        fontSize=8,
        leading=10
    )
    
    styleBold = ParagraphStyle(
        'CustomBold',
        parent=styles['Normal'],
        fontName='HYSMyeongJo-Medium',
        fontSize=9,
        leading=11
    )

    elements = []
    total_points = len(all_data)
    routes_text = ", ".join(routes_list)

    # ЗАГОЛОВОК
    title = Paragraph("МАРШРУТНЫЙ ЛИСТ ДОСТАВКИ", styleTitle)
    elements.append(title)
    elements.append(Spacer(1, 6))
    
    # ИНФОРМАЦИЯ - используем отдельные Paragraph для каждой строки с жирным текстом
    info1 = Paragraph(f"<b>Маршрут(ы):</b> {routes_text}", styleInfo)
    elements.append(info1)
    
    info2 = Paragraph(f"<b>Дата:</b> {datetime.now().strftime('%d.%m.%Y')}", styleInfo)
    elements.append(info2)
    
    info3 = Paragraph(f"<b>Водитель:</b> {driver}", styleInfo)
    elements.append(info3)
    
    info4 = Paragraph(f"<b>Номер машины:</b> {car}", styleInfo)
    elements.append(info4)
    
    info5 = Paragraph(f"<b>№ пломбы:</b> {plomb}", styleInfo)
    elements.append(info5)
    
    info6 = Paragraph(f"<b>Количество магазинов:</b> {total_points}", styleInfo)
    elements.append(info6)
    
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.black))
    elements.append(Spacer(1, 8))

    # ТАБЛИЦА
    # Заголовки
    headers = [
        "№ заказа",
        "Магазин",
        "Адрес",
        "Маршрут",
        "№ пломбы",
        "Выдано коробок",
        "Получено коробок",
        "Подпись, печать,комментарии",
        "Подпись водителя"
    ]
    
    table_data = [headers]

    # Данные
    for _, row in all_data.iterrows():
        order_num = f"<b>{row['№ заказа']}</b>"
        shop_name = str(row["Название магазина"])[:40]
        address = str(row["Адрес магазина"])[:50]
        route_name = str(row["Номер маршрута"])
        
        table_data.append([
            Paragraph(order_num, styleBold),
            Paragraph(shop_name, styleCell),
            Paragraph(address, styleCell),
            Paragraph(route_name, styleCell),
            Paragraph(plomb, styleCell),
            Paragraph(" ", styleCell),
            Paragraph(" ", styleCell),
            Paragraph(" ", styleCell),
            Paragraph(" ", styleCell)
        ])

    # Ширина колонок
    table = Table(
        table_data,
        colWidths=[
            22*mm,  # № заказа
            38*mm,  # Магазин
            48*mm,  # Адрес
            24*mm,  # Маршрут
            20*mm,  # № пломбы
            22*mm,  # Выдано коробок
            22*mm,  # Получено коробок
            38*mm,  # Подпись, комментарии
            28*mm   # Подпись водителя
        ],
        repeatRows=1
    )

    # Стиль таблицы
    table.setStyle(TableStyle([
        # Заголовок
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1F2937")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'HYSMyeongJo-Medium'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,0), 'MIDDLE'),
        
        # Тело таблицы
        ('FONTNAME', (0,1), (-1,-1), 'HYSMyeongJo-Medium'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('VALIGN', (0,1), (-1,-1), 'MIDDLE'),
        
        # Границы
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        
        # Отступы
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        
        # Выравнивание
        ('ALIGN', (0,1), (0,-1), 'CENTER'),
        ('ALIGN', (3,1), (8,-1), 'CENTER'),
        ('ALIGN', (1,1), (2,-1), 'LEFT'),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 15))
    
    # ПРИМЕЧАНИЯ
    notes = Paragraph(
        "Примечания: Количество коробок заполняется при отгрузке. Получение подтверждается подписью и печатью.",
        styleCell
    )
    elements.append(notes)
    
    elements.append(Spacer(1, 10))
    
    # ПОДПИСИ
    signatures = Paragraph(
        "Подпись водителя: _________________________                                    Подпись ответственного: _________________________",
        styleCell
    )
    elements.append(signatures)

    # Строим PDF
    doc.build(elements)
    return filename

# ---------------- MAIN ----------------

# Загрузка данных
try:
    df = get_data()
except Exception as e:
    st.error("Ошибка подключения Google Sheets")
    st.exception(e)
    st.stop()

# Фильтрация
not_shipped = df[df["Статус отгрузки"] != "ОТГРУЖЕН"]
shipped = df[df["Статус отгрузки"] == "ОТГРУЖЕН"]

# Заголовок
st.title("🚚 Система отгрузки маршрутов")

# Метрики
col1, col2, col3, col4 = st.columns(4)
col1.metric("Не отгружено", not_shipped["Номер маршрута"].nunique())
col2.metric("Отгружено", shipped["Номер маршрута"].nunique())
col3.metric("Точек", len(not_shipped))
col4.metric("Кол-во шт", int(not_shipped["кол-во штук в заказе"].sum()))

st.divider()

# Итоги по неотгруженным точкам (сводная)
st.subheader("📊 Итоги по неотгруженным точкам")
summary_not_shipped = not_shipped.groupby(["Название магазина", "Адрес магазина"])["кол-во штук в заказе"].sum().reset_index()
summary_not_shipped.columns = ["Магазин", "Адрес", "Кол-во шт"]

total_shirts = summary_not_shipped["Кол-во шт"].sum()
summary_with_total = pd.concat([
    summary_not_shipped,
    pd.DataFrame([["ИТОГО:", "", total_shirts]], columns=summary_not_shipped.columns)
])

st.dataframe(summary_with_total, use_container_width=True, height=400, hide_index=True)
st.divider()

# Форма отгрузки
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

    # Детали выбранных маршрутов
    if selected_routes:
        st.subheader("📋 Детали маршрутов")
        details_df = not_shipped[not_shipped["Номер маршрута"].isin(selected_routes)]
        st.dataframe(
            details_df[["№ заказа", "Название магазина", "Адрес магазина", "Номер маршрута", "кол-во штук в заказе"]],
            use_container_width=True,
            height=400
        )

    # Кнопка отгрузки
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

        # Собираем все данные по выбранным маршрутам
        all_selected_data = not_shipped[not_shipped["Номер маршрута"].isin(selected_routes)]
        
        # Обновляем статусы в Google Sheets
        update_routes(selected_routes, car_number, driver, plomb)
        
        # Генерируем ОДИН PDF для всех маршрутов
        pdf_file = generate_delivery_pdf(all_selected_data, selected_routes, driver, car_number, plomb)
        
        st.session_state.pdf_file = pdf_file
        st.session_state.shipment_completed = True
        st.session_state.selected_routes = selected_routes
        st.rerun()

# Скачивание PDF
elif st.session_state.shipment_completed and st.session_state.pdf_file:
    st.success(f"✅ Маршруты {', '.join(st.session_state.selected_routes)} успешно отгружены!")
    
    # Проверяем существует ли файл
    if os.path.exists(st.session_state.pdf_file):
        with open(st.session_state.pdf_file, "rb") as f:
            st.download_button(
                label="📄 Скачать маршрутный лист (PDF)",
                data=f,
                file_name=f"Маршрутный_лист_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf"
            )
    else:
        st.error("Файл PDF не найден. Пожалуйста, повторите отгрузку.")
        if st.button("🔄 Повторить отгрузку"):
            st.session_state.shipment_completed = False
            st.session_state.pdf_file = None
            st.rerun()
    
    st.divider()
    
    if st.button("🔄 Начать новую отгрузку"):
        try:
            if st.session_state.pdf_file and os.path.exists(st.session_state.pdf_file):
                os.unlink(st.session_state.pdf_file)
        except:
            pass
        st.session_state.shipment_completed = False
        st.session_state.pdf_file = None
        st.session_state.selected_routes = []
        st.rerun()
else:
    # Если состояние не соответствует, сбрасываем
    st.session_state.shipment_completed = False
    st.session_state.pdf_file = None
    st.rerun()
