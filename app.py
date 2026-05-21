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
    routes_text = ", ".join(routes
