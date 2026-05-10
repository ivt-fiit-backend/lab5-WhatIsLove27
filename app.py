import json
from flask import Flask, abort, jsonify, request
from flask_restx import Api, Resource, fields  # type: ignore

PAGE_SIZE = 25

app = Flask(__name__)
api = Api(
    app,
    version='1.0',
    title='Nobel Prize API',
    description='API для получения информации о нобелевских премиях '
                'и лауреатах',
    doc='/swagger/'
)

with open('awards.json', encoding='utf-8') as f:
    awards = json.load(f)

# Загрузка лауреатов из файла
with open('laureats.json', encoding='utf-8') as f:
    content = f.read().strip()
    # Обработка возможных проблем с JSON
    if content.startswith('[') and content.endswith(']'):
        laureates = json.loads(content)
    else:
        # Пытаемся найти валидный JSON массив
        start_idx = content.find('[')
        end_idx = content.rfind(']') + 1
        if start_idx != -1 and end_idx > start_idx:
            json_str = content[start_idx:end_idx]
            laureates = json.loads(json_str)
        else:
            laureates = []
            print("Не удалось найти валидный JSON массив в laureates.json")

# Создаем пространство имен для версии 2 API
ns_v2 = api.namespace(
    'v2',
    description='API версии 2 для работы с лауреатами'
)

# Модель для документирования API (опционально)
laureate_model = ns_v2.model('Laureate', {
    'id': fields.String(description='ID лауреата'),
    'knownName': fields.Raw(description='Известное имя'),
    'givenName': fields.Raw(description='Имя', required=False),
    'familyName': fields.Raw(description='Фамилия', required=False),
    'fullName': fields.Raw(description='Полное имя'),
    'gender': fields.String(description='Пол'),
    'birth': fields.Raw(description='Информация о рождении'),
    'death': fields.Raw(description='Информация о смерти', required=False),
    'links': fields.Raw(description='Ссылки'),
    'nobelPrizes': fields.List(
        fields.Raw,
        description='Нобелевские премии'
    ),
    'orgName': fields.Raw(
        description='Название организации (для организаций)',
        required=False
    ),
    'nativeName': fields.String(
        description='Оригинальное название (для организаций)',
        required=False
    ),
    'acronym': fields.String(
        description='Аббревиатура (для организаций)',
        required=False
    )
})

# Модель для пагинированного ответа
paginated_laureates = ns_v2.model('PaginatedLaureates', {
    'page': fields.Integer(description='Номер страницы'),
    'per_page': fields.Integer(
        description='Количество элементов на странице'
    ),
    'total': fields.Integer(description='Общее количество лауреатов'),
    'items': fields.List(
        fields.Nested(laureate_model),
        description='Список лауреатов на странице'
    )
})


@app.route("/api/v1/awards/")
def awards_list():
    try:
        p = int(request.args.get('p', 0))
        if p < 0:
            raise ValueError
    except ValueError:
        return abort(400)
    page = awards[p * 50:(p + 1) * 50]
    return jsonify({
        'page': p,
        'count_on_page': PAGE_SIZE,
        'total': len(awards),
        'items': page,
    })


@app.route("/api/v1/award/<int:pk>/")
def award_object(pk):
    if 0 <= pk < len(awards):
        return jsonify(awards[pk])
    else:
        abort(404)


@app.route("/api/v1/laureates/")
def laureates_list():
    """
    Возвращает список лауреатов с пагинацией
    """
    try:
        page = int(request.args.get('page', 0))
        if page < 0:
            raise ValueError
        per_page = int(request.args.get('per_page', PAGE_SIZE))
        if per_page <= 0 or per_page > 100:
            per_page = PAGE_SIZE
    except ValueError:
        return abort(400, description="Некорректные параметры пагинации")

    start = page * per_page
    end = start + per_page
    page_items = laureates[start:end]

    return jsonify({
        'page': page,
        'per_page': per_page,
        'total': len(laureates),
        'items': page_items,
    })


@app.route("/api/v1/laureate/<int:index>/")
def laureate_by_index(index):
    """
    Возвращает лауреата по индексу в списке
    """
    if 0 <= index < len(laureates):
        return jsonify(laureates[index])
    else:
        abort(404, description=f"Лауреат с индексом {index} не найден")


@app.route("/api/v1/laureate/id/<string:id>/")
def laureate_by_id(id):
    """
    Возвращает лауреата по его ID
    """
    for laureate in laureates:
        if str(laureate.get('id')) == id:
            return jsonify(laureate)
    abort(404, description=f"Лауреат с ID {id} не найден")


@app.route("/api/v1/laureates/search/")
def laureates_search():
    """
    Поиск лауреатов по имени
    """
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify({'items': [], 'count': 0})

    results = []
    for laureate in laureates:
        # Поиск по известному имени
        known_name = laureate.get('knownName', {}).get('en', '').lower()
        # Поиск по полному имени
        full_name = laureate.get('fullName', {}).get('en', '').lower()
        # Поиск по имени организации
        org_name = laureate.get('orgName', {}).get('en', '').lower()

        if query in known_name or query in full_name or query in org_name:
            results.append(laureate)

    return jsonify({
        'query': query,
        'count': len(results),
        'items': results[:20]  # Ограничиваем количество результатов
    })


@app.route("/api/v1/laureates/year/<int:year>/")
def laureates_by_year(year):
    """
    Возвращает лауреатов, получивших премию в указанном году
    """
    results = []
    for laureate in laureates:
        prizes = laureate.get('nobelPrizes', [])
        for prize in prizes:
            if prize.get('awardYear') == str(year):
                results.append(laureate)
                break

    return jsonify({
        'year': year,
        'count': len(results),
        'items': results
    })


@app.route("/api/v1/laureates/category/<string:category>/")
def laureates_by_category(category):
    """
    Возвращает лауреатов по категории премии
    """
    results = []
    category_lower = category.lower()
    for laureate in laureates:
        prizes = laureate.get('nobelPrizes', [])
        for prize in prizes:
            prize_category = prize.get('category', {}).get('en', '').lower()
            if prize_category == category_lower:
                results.append(laureate)
                break

    return jsonify({
        'category': category,
        'count': len(results),
        'items': results
    })


# ============== Эндпойнты Flask-RESTX для /v2/ ==============

@ns_v2.route('/laureates/')
class LaureatesList(Resource):
    @ns_v2.doc('list_laureates')
    @ns_v2.param(
        'page',
        'Номер страницы (начиная с 0)',
        type=int,
        default=0
    )
    @ns_v2.param(
        'per_page',
        'Количество элементов на странице',
        type=int,
        default=PAGE_SIZE,
        max=100
    )
    @ns_v2.marshal_list_with(laureate_model)
    @ns_v2.response(200, 'Успешно', paginated_laureates)
    def get(self):
        """
        Возвращает список всех лауреатов с пагинацией
        """
        try:
            page = int(request.args.get('page', 0))
            if page < 0:
                raise ValueError
            per_page = int(request.args.get('per_page', PAGE_SIZE))
            if per_page <= 0 or per_page > 100:
                per_page = PAGE_SIZE
        except ValueError:
            abort(400, description="Некорректные параметры пагинации")

        start = page * per_page
        end = start + per_page
        page_items = laureates[start:end]

        return {
            'page': page,
            'per_page': per_page,
            'total': len(laureates),
            'items': page_items,
        }


@ns_v2.route('/laureate/<string:id>/')
@ns_v2.param('id', 'Идентификатор лауреата')
class LaureateResource(Resource):
    @ns_v2.doc('get_laureate')
    @ns_v2.marshal_with(laureate_model)
    @ns_v2.response(200, 'Успешно')
    @ns_v2.response(404, 'Лауреат не найден')
    def get(self, id):
        """
        Возвращает конкретного лауреата по его ID
        """
        for laureate in laureates:
            if str(laureate.get('id')) == id:
                return laureate
        abort(404, description=f"Лауреат с ID {id} не найден")


# Дополнительный эндпойнт для обратной совместимости
@ns_v2.route('/laureate/by-index/<int:index>/')
@ns_v2.param('index', 'Индекс лауреата в списке')
class LaureateByIndexResource(Resource):
    @ns_v2.doc('get_laureate_by_index')
    @ns_v2.marshal_with(laureate_model)
    @ns_v2.response(200, 'Успешно')
    @ns_v2.response(404, 'Лауреат не найден')
    def get(self, index):
        """
        Возвращает лауреата по его индексу в списке
        """
        if 0 <= index < len(laureates):
            return laureates[index]
        abort(404, description=f"Лауреат с индексом {index} не найден")


# Поисковый эндпойнт для версии 2
@ns_v2.route('/laureates/search/')
class LaureatesSearch(Resource):
    @ns_v2.doc('search_laureates')
    @ns_v2.param('q', 'Поисковый запрос', required=True)
    @ns_v2.response(200, 'Успешно')
    def get(self):
        """
        Поиск лауреатов по имени
        """
        query = request.args.get('q', '').lower()
        if not query:
            return {'items': [], 'count': 0}

        results = []
        for laureate in laureates:
            known_name = laureate.get('knownName', {}).get('en', '').lower()
            full_name = laureate.get('fullName', {}).get('en', '').lower()
            org_name = laureate.get('orgName', {}).get('en', '').lower()

            if query in known_name or query in full_name or query in org_name:
                results.append(laureate)

        return {
            'query': query,
            'count': len(results),
            'items': results[:20]
        }


if __name__ == '__main__':
    app.run(debug=True)
