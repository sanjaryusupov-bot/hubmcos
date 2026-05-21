# app.py

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
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

# ---------------- SETTINGS ----------------

st.set_page_config(
    page_title="Отгрузка маршрутов",
    layout="wide"
)

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

    return pd.DataFrame(data)

# ---------------- UPDATE ROUTE ----------------

def update_route(route_name, car_number, driver, plomb):

    sheet = connect_sheet()

    data = sheet.get_all_records()

    headers = sheet.row_values(1)

    # Создаем колонки если нет

    extra_columns = [
        "Номер машины",
        "Водитель",
        "№ пломбы"
    ]

    current_headers = headers.copy()

    for col_name in extra_columns:

        if col_name not in current_headers:

            sheet.update_cell(
                1,
                len(current_headers) + 1,
                col_name
            )

            current_headers.append(col_name)

    headers = sheet.row_values(1)

    status_col = headers.index("Статус отгрузки") + 1
    fact_col = headers.index("Дата отгрузки факт") + 1
    car_col = headers.index("Номер машины") + 1
    driver_col = headers.index("Водитель") + 1
    plomb_col = headers.index("№ пломбы") + 1

    for idx, row in enumerate(data, start=2):

        if row["Номер маршрута"] == route_name:

            sheet.update_cell(
                idx,
                status_col,
                "ОТГРУЖЕН"
            )

            sheet.update_cell(
                idx,
                fact_col,
                datetime.now().strftime("%d.%m.%Y %H:%M")
            )

            sheet.update_cell(
                idx,
                car_col,
                car_number
            )

            sheet.update_cell(
                idx,
                driver_col,
                driver
            )

            sheet.update_cell(
                idx,
                plomb_col,
                plomb
            )

# ---------------- PDF ----------------

def generate_pdf(df, route, driver, car, plomb):

    filename = f"{route}.pdf"

    doc = SimpleDocTemplate(
        filename,
        pagesize=A4
    )

    styles = getSampleStyleSheet()

    elements = []

    total_boxes = df["кол-во штук в заказе"].sum()

    title = Paragraph(
        f"""
        <b>МАРШРУТНЫЙ ЛИСТ</b><br/><br/>
        Маршрут: {route}<br/>
        Водитель: {driver}<br/>
        Машина: {car}<br/>
        № пломбы: {plomb}<br/>
        Дата: {datetime.now().strftime("%d.%m.%Y %H:%M")}<br/>
        Магазинов: {len(df)}<br/>
        Коробок: {total_boxes}<br/><br/>
        """,
        styles["Title"]
    )

    elements.append(title)

    data = [[
        "Заказ",
        "Магазин",
        "Адрес",
        "Маршрут",
        "Пломба",
        "Коробок выдано",
        "Получено",
        "Подпись"
    ]]

    for _, row in df.iterrows():

        data.append([
            row["№ заказа"],
            row["Название магазина"],
            row["Адрес магазина"],
            row["Номер маршрута"],
            plomb,
            row["кол-во штук в заказе"],
            "",
            ""
        ])

    table = Table(data)

    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
    ]))

    elements.append(table)

    elements.append(Spacer(1, 20))

    sign = Paragraph(
        """
        Подпись водителя ___________________________<br/><br/>
        Подпись принимающей стороны ___________________________
        """,
        styles["Normal"]
    )

    elements.append(sign)

    doc.build(elements)

    return filename

# ---------------- UI ----------------

st.title("🚚 Отгрузка маршрутов")

try:

    df = get_data()

except Exception as e:

    st.error("Ошибка подключения Google Sheets")
    st.stop()

# ---------------- FILTERS ----------------

not_shipped = df[
    df["Статус отгрузки"] != "ОТГРУЖЕН"
]

shipped = df[
    df["Статус отгрузки"] == "ОТГРУЖЕН"
]

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
    "Коробок",
    int(not_shipped["кол-во штук в заказе"].sum())
)

st.divider()

# ---------------- FORM ----------------

st.subheader("🚛 Данные отгрузки")

car_number = st.text_input(
    "Номер машины"
)

driver = st.text_input(
    "Водитель"
)

plomb = st.text_input(
    "№ пломбы"
)

routes = sorted(
    not_shipped["Номер маршрута"].dropna().unique()
)

selected_routes = st.multiselect(
    "Выберите маршруты",
    routes
)

# ---------------- DETAILS ----------------

if selected_routes:

    details_df = not_shipped[
        not_shipped["Номер маршрута"].isin(selected_routes)
    ]

    st.subheader("📦 Детали маршрутов")

    st.dataframe(
        details_df[
            [
                "№ заказа",
                "Название магазина",
                "Адрес магазина",
                "Номер маршрута",
                "кол-во штук в заказе"
            ]
        ],
        use_container_width=True
    )

# ---------------- SHIP BUTTON ----------------

if st.button("✅ ОТГРУЗИТЬ"):

    if not car_number:

        st.warning("Введите номер машины")
        st.stop()

    if not selected_routes:

        st.warning("Выберите маршрут")
        st.stop()

    for route in selected_routes:

        route_df = df[
            df["Номер маршрута"] == route
        ]

        update_route(
            route,
            car_number,
            driver,
            plomb
        )

        pdf_file = generate_pdf(
            route_df,
            route,
            driver,
            car_number,
            plomb
        )

        with open(pdf_file, "rb") as f:

            st.download_button(
                label=f"📄 Скачать PDF {route}",
                data=f,
                file_name=pdf_file,
                mime="application/pdf"
            )

    st.success("Маршруты успешно отгружены")