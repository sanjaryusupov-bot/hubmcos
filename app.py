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
        alignment=1,
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
    
    styleHeader = ParagraphStyle(
        'CustomHeader',
        parent=styles['Normal'],
        fontName='HYSMyeongJo-Medium',
        fontSize=9,
        leading=11,
        alignment=1
    )

    elements = []
    total_points = len(all_data)
    routes_text = ", ".join(routes_list)

    # ЗАГОЛОВОК
    title = Paragraph("МАРШРУТНЫЙ ЛИСТ ДОСТАВКИ", styleTitle)
    elements.append(title)
    elements.append(Spacer(1, 6))
    
    # ИНФОРМАЦИЯ
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

    # ТАБЛИЦА - заголовки БЕЗ тегов <b>
    headers = [
        "№ заказа",
        "Магазин",
        "Адрес",
        "Маршрут",
        "№ пломбы",
        "Выдано\nкоробок",
        "Получено\nкоробок",
        "Подпись, печать,\nкомментарии",
        "Подпись\nводителя"
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
            Paragraph("___________", styleCell),
            Paragraph("___________", styleCell),
            Paragraph("___________", styleCell),
            Paragraph("___________", styleCell)
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
