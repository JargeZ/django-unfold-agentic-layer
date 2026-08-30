# Спецификация: динамическая генерация MCP-примитивов для моделей админки

Статус: **финальная** (все вопросы черновика закрыты в ревью `f6e58bd`, технические допущения
проверены экспериментально — см. §12). Продолжает пункт Roadmap note «Admin-introspection tools»
в корневом `CLAUDE.md`.

---

## 0. Что уже есть в коде (baseline)

Часть фундамента уже реализована в `resources/` — **чисто описательный** слой (нормализованные
метаданные о моделях админки), ещё не подключённый ни к `mcp.resource()`, ни к `mcp.tool()`:

- `resources/schemas.py` — `AdminModelResource`, `AdminAppResource`, `ActionInfo`, `FilterFieldInfo`.
- `resources/actions/build_admin_app_resource.py`, `build_admin_model_resource.py` — собирают эти
  pydantic-модели из `admin.site._registry` / `AppConfig`.
- `resources/actions/extract_*` — вытаскивают `list_filter` / `search_fields` / `actions` /
  `actions_list` / `actions_row` / `actions_detail` / `actions_submit_line` (в т.ч.
  unfold-специфичные через `_shared.get_base_unfold_actions`).
- Всё покрыто snapshot-тестами (`syrupy`, `.ambr`) на реальном `blog` из `django_test_app`.

`actions/base.py::BaseLogicAction` (`def execute(self): ...`) — единственный принятый паттерн для
экшенов. Один файл = один экшен, как в существующих `resources/actions/*`.

### 0.1 🔑 Архитектурный инвариант: слой нормализации обязателен

**Билдеры MCP-примитивов не имеют права напрямую лазать в Django.** Любое обращение к
`ModelAdmin` / `_meta` / `AdminSite` сначала нормализуется в абстрактную схему через слой
`resources/actions/*` (`BuildAdminAppResource`, `BuildAdminModelResource`, `Extract*`), и только
её потребляют `Build*ResourceDefinition` / `Build*ToolDefinition`.

Этот слой **расширяем** — большая часть работы этой итерации как раз в его расширении
(см. §5, §7). Правило одностороннее:

```
Django (ModelAdmin, AdminSite, forms, ChangeList)
  → resources/actions/*  (нормализация)      ← расширяем здесь
    → resources/schemas.py (pydantic-схемы)  ← расширяем здесь
      → builders (mcp.resource / mcp.tool)   ← только потребляют схемы
```

Причина: билдеры отвечают за форму MCP-примитива, а не за знание Django. Так тесты билдеров
работают на схемах-фикстурах, а не на живой админке, и любая версия Django/unfold абсорбируется
в одном слое.

### 0.2 Зафиксированные ограничения области

- Поддерживается **только дефолтный `django.contrib.admin.site`**. Параметр
  `admin_site: AdminSite = default_admin_site` остаётся в сигнатурах (он уже есть и полезен для
  тестов), но URI-схема site не кодирует, и множественные admin-сайты вне области.
- Целевая Django — **5+** (в текущем окружении фактически стоит 6.0.7; см. §11.4 про рассинхрон
  с `pyproject.toml`).

---

## 1. `BuildAdminMCPInstance` — точка входа

```python
class BuildAdminMCPInstance(BaseLogicAction):
    def execute(
        self,
        request: HttpRequest,          # актор для permission-фильтрации
        admin_site: AdminSite = default_admin_site,
    ) -> FastMCP: ...
```

Экшен возвращает **новый** объект `FastMCP`, а не мутирует модульный `mcp` из
`mcp_server/tools.py`. В него монтируется статичный docs-сервер (все 25 текущих `unfold_*` тулов
сохраняются без изменений), а поверх — динамически построенные admin-ресурсы и тулы.
Единственный вариант, совместимый с per-user мемоизацией: разные пользователи получают
изолированные наборы примитивов без гонок за общий mutable singleton.

### 1.1 Ленивость и мемоизация

- Билд выполняется один раз по требованию. `bridge.py` перестаёт делать статичный
  `from .tools import mcp` и дёргает мемоизированную обёртку.
- **Механизм — `functools.lru_cache`**, для тестов подключается `pytest-antilru` (busts
  `functools.lru_cache` между тестами).
- Кэш **per-process/per-worker** — это принято как норма. «Строим один раз» означает «один раз на
  воркер», не глобально.
- Ключ кэша уже сейчас закладывается под `user.pk` (сегодня — фактически один слот, т.к. доступ
  только у суперюзера).

> ⚠️ **Известная ловушка `pytest-antilru`**: pytest-django загружается раньше pytest-antilru, из-за
> чего `lru_cache`, созданный на этапе `AppConfig.ready()`, не бустится
> ([ipwnponies/pytest-antilru#27](https://github.com/ipwnponies/pytest-antilru/issues/27)).
> Следствие для нас: **не создавать кэш на import-time / в `AppConfig.ready()`** — только лениво
> при первом вызове. Это и так требование «no import-time side effects» из
> [Django reusable-apps](https://docs.djangoproject.com/en/5.2/intro/reusable-apps/), но здесь оно
> ещё и напрямую влияет на тестируемость. Опция `lru_cache_disabled` позволяет сузить бустинг до
> наших модулей, чтобы не ломать `lru_cache` внутри Django/fastmcp.

### 1.2 Permission-фильтрация — переиспользуем Django, не пишем свою

Логика «какие модели и какие действия видит пользователь» **должна быть ровно той же**, что
использует сама админка. Для каждого неотфильтрованного геттера, который сейчас использует
`resources/actions/*`, в Django/unfold есть request-aware публичный аналог:

| Сейчас (неотфильтрованное)                                    | Request-aware аналог (использовать)                              |
|---------------------------------------------------------------|------------------------------------------------------------------|
| `admin_site._registry.items()`                                | `AdminSite.get_app_list(request)` / `_build_app_dict(request)`     |
| —                                                             | `ModelAdmin.get_model_perms(request)` → `{add, change, delete, view}` |
| `model_admin.actions` + `admin_site.actions` + `get_action()`  | `ModelAdmin.get_actions(request)` — **уже** фильтрует права        |
| `_get_base_actions_list()`                                    | `get_actions_list(request)`                                        |
| `_get_base_actions_detail()`                                  | `get_actions_detail(request, object_id)`                           |
| `_get_base_actions_row()`                                     | `get_actions_row(request)`                                         |
| `_get_base_actions_submit_line()`                             | `get_actions_submit_line(request, object_id)`                      |

`AdminSite._build_app_dict(request)` делает ровно то, что нужно: пропускает модель, если
`has_module_permission(request)` ложно или если в `get_model_perms(request)` нет ни одного `True`.
Unfold-actions фильтруются через `_filter_unfold_actions_by_permissions`, которое дёргает
`has_<permission>_permission(request[, object_id])` — включая объектные проверки.

**Следствие для слоя нормализации:** `Extract*`-экшены получают request-aware варианты
(`execute(model_admin, request)`), а неотфильтрованные остаются для документационных сценариев.
Отдельный «шаг фильтрации» как самостоятельный экшен больше не нужен — фильтрация встроена в те
же Django-вызовы, что и извлечение. Это строго лучше: невозможно случайно получить
отфильтрованный список моделей и неотфильтрованный список действий.

---

## 2. URI-схема

Зеркалит структуру URL самой админки — `app/model/`:

| Примитив                    | URI                                                      |
|-----------------------------|----------------------------------------------------------|
| Детальный ресурс            | `dj-admin://{app_label}/{model_name}/{pk}/`               |
| Списочный ресурс            | `dj-admin://{app_label}/{model_name}/{?<params>}`         |

`model_name` обязателен — без него `app_label` не различает модели внутри одного приложения.

`{?...}` — RFC 6570 query-синтаксис, поддерживаемый fastmcp
(`fastmcp/resources/template.py::extract_query_params` / `build_regex`). Список параметров строится
динамически под конкретную модель, синхронно с сигнатурой функции-хендлера.

---

## 3. Ресурсы модели: `_build_resource_definition_for_model`

```python
def _build_resource_definition_for_model(mcp, model_resource: AdminModelResource):
    _build_details_resource(mcp, model_resource)
    _build_list_resource(mcp, model_resource)
```

На вход — **нормализованная схема**, не `ModelAdmin` (см. §0.1).

### 3.1 `BuildModelDetailResourceDefinition`

```python
mcp.resource(
    uri="dj-admin://blog/blogpost/{pk}/",
    name=...,          # verbose_name
    description=...,   # докстринг класса ModelAdmin (через слой нормализации, не напрямую)
    mime_type="application/json",
)
```

- **name** — `opts.verbose_name` (уже нормализуется в `BuildAdminModelResource`).
- **description** — `inspect.getdoc(type(model_admin))`, тот же паттерн, что
  `BuildAdminAppResource` применяет к `AppConfig`. Извлечение живёт в слое нормализации, билдер
  берёт готовое поле схемы.

### 3.2 `BuildModelListResourceDefinition`

Параметры типизируются через `Annotated[..., Field(...)]` в динамически построенной сигнатуре
(`inspect.Signature` + `Annotated`). ✅ Проверено (§12.2): fastmcp корректно превращает такую
сигнатуру в JSON Schema с `description` / `minimum` / `maximum` / `default`.

Состав параметров:

| Параметр            | Источник                                                    |
|---------------------|-------------------------------------------------------------|
| `q`                 | `search_fields` (только если непустые)                       |
| один на каждый фильтр | `filter_spec.expected_parameters()` — см. §4                |
| `limit` / `offset`  | наши, транслируются в срез (см. §5)                          |
| `order_by`          | наш, транслируется в `o` (см. §5)                            |

---

## 4. Фильтры: `expected_parameters()` — единый контракт

### 4.1 🐞 Дефект текущей реализации, который эта итерация обязана исправить

`ExtractListFilterFields` сейчас кладёт в `FilterFieldInfo.key` **имя поля модели**. Текущий
снапшот `test_build_admin_model_resource.ambr`:

```
key: 'author'        ← НЕ является валидным GET-параметром админки
key: 'created_at'    ← тоже
```

Реальные параметры, которых ждёт `ChangeList` (проверено, §12.3):

```
author      → ['author__id__exact', 'author__isnull']
created_at  → ['created_at__gte', 'created_at__lt']
```

Агент, подставивший `?author=1`, получает `IncorrectLookupParameters: Cannot resolve keyword
'author' into field`. То есть **фильтры в текущем описании нерабочие**.

### 4.2 Правильный источник — сама админка

```python
cl = model_admin.get_changelist_instance(request)
filter_specs, has_filters, remaining, has_related, has_active = cl.get_filters(request)
for spec in filter_specs:
    spec.expected_parameters()   # → точные имена GET-параметров
    spec.choices(cl)             # → допустимые значения + готовые query_string
    spec.title                   # → человекочитаемое имя
```

`expected_parameters()` определён на базовом `ListFilter` и реализован **всеми** семействами
фильтров — то есть контракт универсален. Проверено на живых классах (§12.3):

| Класс фильтра                          | `expected_parameters()`                                                          |
|----------------------------------------|-----------------------------------------------------------------------------------|
| `RelatedFieldListFilter` (плейн FK)     | `['author__id__exact', 'author__isnull']`                                         |
| `DateFieldListFilter`                   | `['created_at__gte', 'created_at__lt']`                                           |
| кастомный `SimpleListFilter`            | `['title_startswith']` + `spec.lookup_choices` = `[('a','A'), ('b','B')]`         |
| unfold `AutocompleteSelectFilter`       | `['author__id__exact', 'author__isnull']` — идентично плейн FK                     |
| unfold `RangeDateTimeFilter`            | `['created_at_from_0', 'created_at_from_1', 'created_at_to_0', 'created_at_to_1']` |

**Пересмотр решения из ревью.** В ревью было «кастомные фильтры пока помечаем неподдерживаемыми,
но `AutocompleteSelectFilter` должен работать». Исследование показывает, что разделять их не
нужно:

- Все unfold-фильтры наследуются от Django-баз (`DropdownFilter(admin.SimpleListFilter)`,
  `RelatedDropdownFilter(admin.RelatedFieldListFilter)`, `TextFilter(admin.SimpleListFilter)`,
  `RangeNumericFilter(admin.FieldListFilter)`), поэтому `expected_parameters()` есть у всех.
- `AutocompleteSelectFilter` отличается от плейн FK **только виджетом** — на уровне
  query-параметров он неотличим, что ровно и означает «работает с str/tuple первичных ключей».
- Кастомный `SimpleListFilter` тоже полностью интроспектируем: имя параметра + `lookup_choices`.

Поэтому: **поддерживаем все фильтры по `expected_parameters()`**. Единственное, что деградирует
для нестандартных классов — *тип значения*: если `spec` не даёт перечислимых `choices` /
`lookup_choices`, параметр описывается как `str` без ограничений. Это деградация типизации,
а не отказ в поддержке.

`RangeDateTimeFilter` с суффиксами `_0`/`_1` (split date/time виджет) — иллюстрация того, почему
угадывать имена параметров нельзя, а `expected_parameters()` можно.

### 4.3 Следствия для схемы

`FilterFieldInfo` расширяется: `key` становится **реальным GET-параметром** (одна запись на каждый
элемент `expected_parameters()`), плюс появляются `choices` и `related_resource_uri` (см. §7.3).
Извлечение фильтров становится **request-зависимым** (`get_filters(request)`), что заодно даёт
per-user корректность бесплатно.

### 4.4 Обработка ошибок

Неизвестный/некорректный параметр → `django.contrib.admin.options.IncorrectLookupParameters` при
вычислении queryset. Ловим и превращаем в понятную агенту MCP-ошибку со списком валидных
параметров (они у нас есть из `expected_parameters()`).

---

## 5. Сортировка и пагинация — требуют трансляции

Проверено (§12.4). Django changelist **не** использует `limit`/`offset`/имена полей:

### 5.1 Сортировка: `o` — это индексы колонок

```
list_display = ('title', 'author', 'created_at')

o=1        → ordering ['title', '-pk']
o=-1       → ordering ['-title', '-pk']
o=1.-3     → ordering ['title', '-created_at', '-pk']   (точка = мультиколоночная)
o=title    → ordering ['-pk']   ← ⚠️ МОЛЧА ИГНОРИРУЕТСЯ, без ошибки
```

`o` принимает **1-based индексы в `list_display`**, `-` = по убыванию. Имя поля игнорируется
молча — самый опасный вариант отказа, агент не узнает, что сортировка не применилась.

**Решение:** наружу отдаём агенту `order_by` с **именами полей** (валидируемый `Literal` из
сортируемых колонок), внутри транслируем в `o=<индексы>`. Множество допустимых значений берём из
`ModelAdmin.get_sortable_by(request)` ∩ `get_list_display(request)`. Отдельный экшен трансляции с
собственными тестами.

### 5.2 Пагинация: `p` + `list_per_page`, никаких limit/offset

```
list_per_page = 3, всего 7 записей
''      → page_num=1, result_list=[post-6, post-5, post-4], num_pages=3
p=2     → page_num=2, result_list=[post-3, post-2, post-1]
all=    → show_all=True, result_list=все 7
```

`limit`/`offset` в админке не существует. **Решение:** `limit`/`offset` остаются в MCP-контракте
(они естественны для агента), но применяются как срез к `cl.get_queryset(request)`, а не через
`p`. `ChangeList` используем как машину фильтрации/сортировки, а пагинацию делаем сами — иначе
пришлось бы мутировать `model_admin.list_per_page`, что не потокобезопасно (это атрибут класса,
общий для всех запросов).

`limit` типизируется как `Annotated[int, Field(ge=1, le=<потолок>)]` с дефолтом; потолок —
кандидат в настройку `UNFOLD_AGENTIC_LAYER`.

---

## 6. Проброс `HttpRequest` в хендлеры — ✅ решено через ASGI scope

**Механизм (проверен end-to-end, §12.1): кладём Django `HttpRequest` в синтетический ASGI scope.**

```python
# bridge.py — при сборке scope
scope = {
    "type": "http",
    ...,
    "django_unfold_agentic_layer.request": request,   # ← namespaced ключ
}

# в любом tool/resource-хендлере
from fastmcp.server.dependencies import get_http_request

django_request = get_http_request().scope["django_unfold_agentic_layer.request"]
```

Почему работает — цепочка проверена по исходникам и экспериментом:

1. `bridge._dispatch` строит scope и передаёт в `manager.handle_request(scope, receive, send)`.
2. `mcp/server/streamable_http.py::handle_request` делает `Request(scope, receive)` — Starlette
   `Request` хранит **тот же самый объект** scope.
3. Этот `Request` уходит как `ServerMessageMetadata(request_context=request)`.
4. `mcp/server/lowlevel/server.py:753` кладёт его в `request_ctx` как `RequestContext.request`.
5. `fastmcp.server.dependencies.get_http_request()` первым делом читает `request_ctx.get().request`.

Эксперимент подтвердил: в хендлере доступен живой Django-request с
`request.user == <User: staff>`.

**Собственные contextvars не нужны** — используется штатный механизм передачи request-метаданных,
как и просил ревью. `RequestContextMiddleware` из fastmcp (который обычно ставит
`_current_http_request`) в нашем обходном пути не участвует, но и не требуется: SDK-шный
`request_ctx` заполняется в любом случае.

### 6.1 Экшены работы с request

- **`ApplyMCPFiltersToRequest`** — принимает исходный `HttpRequest` + словарь MCP-параметров,
  возвращает **копию** с подставленным `GET` (`QueryDict`). Оригинал не мутирует.
- **`SynthesizeAdminRequest`** — собирает fake-request с нуля. Используется как fallback, когда
  реального request нет (unit-тесты слоя нормализации).

**Минимальный набор атрибутов проверен экспериментально (§12.3):**

```python
request = HttpRequest()
request.method = "GET"
request.user = user            # нужен get_actions() и has_*_permission()
request.GET = QueryDict(query) # единственное, что читает сам ChangeList
```

Этого достаточно: `get_changelist_instance()`, поиск (`q`), фильтры, сортировка и кастомные
`SimpleListFilter` отрабатывают. `ChangeList.__init__` обращается только к `request.GET`;
`request.user` нужен вызовам прав внутри `get_queryset` / `get_actions`.

Unfold-флаги `list_filter_submit` / `list_filter_sheet` — **чисто фронтенд**, на состав
GET-параметров не влияют и в MCP не переносятся. Не все атрибуты админки имеют смысл для MCP.

**Тестирование:** обязательны кейсы, гоняющие настоящий HTTP-запрос через `/mcp/` (как уже делает
`test_mcp_endpoint.py`) — синтетический request проверяет слой нормализации, но не мост.

---

## 7. Схема модели: readable / editable

### 7.1 Принцип «сверху вниз»

Источник правды выбирается по близости к тому, что пользователь видит в браузере:

1. **Сначала форма** — `model_admin.get_form(request, obj, change=...)`. Даёт состав редактируемых
   полей и `required`.
2. **Затем класс админки** — `get_readonly_fields(request, obj)`, `get_fields(request, obj)`,
   `get_fieldsets(request, obj)`, т.е. самые высокоуровневые геттеры, которые вызывает сам
   фреймворк (уже подготовленные списки), а не сырые атрибуты `fields` / `exclude`.

Проверено на `BlogPost` (§12.5):

```
form fields:  title (required=True), body (required=False), author (required=True)
readonly_fields: ()
get_fields:   ['title', 'body', 'author']
created_at (auto_now_add) — в форме ОТСУТСТВУЕТ  ← readable, но не editable
```

Это и есть иллюстрация, почему форма — правильный первый источник: она сама исключает
неredactируемое.

### 7.2 mandatory / optional / nullable — из формы

`form.fields[name].required` — источник правды для mandatory/optional, потому что админка может
поднять `required=True` поверх `blank=True` модели. `nullable` берётся из модели (`field.null`) —
у формы такого понятия нет.

Виджет читается после разворачивания обёртки:

```python
widget = field.widget
if isinstance(widget, RelatedFieldWidgetWrapper):
    widget = widget.widget      # → UnfoldAdminSelectWidget
```

Без этого у всех FK виджет выглядит как `RelatedFieldWidgetWrapper`, и unfold-специфика теряется.

### 7.3 `choices` и связанные модели — отдаём URI, а не значения

Вместо инлайна списка значений отдаём агенту **URI ресурса**, который он может запросить:

- **FK / M2M** → URI списочного ресурса админки связанной модели:
  `dj-admin://auth/user/`. Связанная модель берётся из `spec.field.related_model._meta` /
  `model_field.related_model._meta` (проверено: `auth.user`).
- **`choices`** → URI вида `dj-admin://{app_label}/{model_name}/{field_name}/choices/`.
  **Структура URL фиксируется сейчас, реализация хендлера — следующая итерация.**

Для перечислимых фильтров `spec.choices(cl)` уже сейчас отдаёт готовые пары
display + `query_string` (`?author__id__exact=2`) — их можно класть в описание параметра как
примеры, не изобретая формат.

---

## 8. Экшены выполнения ресурсов и рендеринг

### 8.1 Иерархия результата

Один инстанс — частный случай N инстансов:

```
BuildOneResourceResult
  → BuildListResourceResult().execute(qs)   # qs отфильтрован по pk
```

`BuildListResourceResult` возвращает мультиконтентный `ResourceResult` (API подтверждён,
`fastmcp/resources/base.py`):

```python
return ResourceResult(
    contents=[
        ResourceContent(content='[{"id": 1}]', mime_type="application/json"),
        ResourceContent(content="# Users\n...", mime_type="text/markdown"),
    ],
    meta={"total": 1},
)
```

`ResourceContent` принимает любой тип: `str`/`bytes` проходят как есть, остальное
автосериализуется в JSON.

### 8.2 JSON → Markdown

```python
class GetModelJsonRepresentation(BaseLogicAction):
    def execute(self, instance, model_resource) -> ModelInstanceJson: ...

class RenderModelInstanceMarkdown(BaseLogicAction):
    def execute(self, value: ModelInstanceJson) -> str: ...
```

JSON — основная логика; Markdown строится поверх неё. Оба тестируются отдельно, и только потом
идёт wiring в fastmcp.

### 8.3 Реестр рендереров — расширяемый через hook

Реестр `field type / widget → renderer` расширяется **через hook в `conf.py`
(`UNFOLD_AGENTIC_LAYER`)**, чтобы host-проект регистрировал рендер для своих кастомных полей и
виджетов без форка. Механика merge уже есть — `conf.get_config()` делает deep-merge вложенных
словарей по образцу `unfold.settings.get_config`; добавляется новый ключ в `Settings` /
`SettingsDict` / `DEFAULTS` (module-level asserts не дадут им разъехаться).

Дефолтный реестр покрывает встроенные типы; ключ разрешения — тип поля модели и/или класс
виджета из формы (после разворачивания `RelatedFieldWidgetWrapper`, см. §7.2).

**FK / M2M рендерятся как ссылка-URI** на детальный ресурс (`dj-admin://app/model/{pk}/`) —
не вложенным объектом. Это снимает риск рекурсии и N+1 и даёт агенту явную точку перехода.

---

## 9. Тулы: create / update

Для каждой модели генерируются `mcp.tool()`-определения поверх **стандартных Django-форм**:

- вход тула маппится в `model_admin.get_form(request, obj)`;
- `form.is_valid()` — вся валидация переиспользуется, ничего не дублируем;
- при `is_valid() is False` ошибки собираются обратно в структурированный, понятный агенту вид.

Состав и типы полей берутся из расширенной схемы (§7), а не из прямого обращения к Django.

### 9.1 Delete — отложен до `InputRequiredResult`

**Обоснование (проверено по исходникам).** `ctx.elicit()` в текущем мосте нерабочий:
`bridge.py` создаёт `FastMCPStreamableHTTPSessionManager(json_response=True, stateless=True)`,
а в ветке `is_json_response_enabled` (`mcp/server/streamable_http.py`) цикл
`async for event_message in request_stream_reader` ждёт **единственный** `JSONRPCResponse` и на
server→client запрос (`elicitation/create`, `sampling/createMessage`) лишь пишет `debug` и ждёт
дальше. Канала для ответа клиента внутри того же POST нет — GET/DELETE в `MCPView` отклоняются.
Итог: `ctx.elicit()` зависает до таймаута.

**Правильный механизм — `InputRequiredResult`** ([docs](https://gofastmcp.com/servers/elicitation#elicitation-on-the-modern-protocol)):
тул не приостанавливается, а **возвращает** описание нужного ввода; клиент выполняет запрос и
**перевызывает** тул с ответом. Состояние между раундами едет в `request_state` (sealed token),
поэтому механизм явно рассчитан на «stateless, serverless и load-balanced деплойменты, где два
раунда не гарантированно попадают на один воркер» — то есть ровно на нашу архитектуру.

```python
from mcp.types import ElicitRequest, ElicitRequestFormParams, InputRequiredResult

@mcp.tool
async def delete_blogpost(pk: int, ctx: Context) -> str | InputRequiredResult:
    responses = ctx.input_responses
    if responses is None:
        return InputRequiredResult(
            result_type="input_required",
            input_requests={"confirm": ElicitRequest(
                method="elicitation/create",
                params=ElicitRequestFormParams(
                    message=f"Delete {obj}? This cannot be undone.",
                    requested_schema={...},
                ),
            )},
            request_state=f"pk={pk}",
        )
    ...
```

**Блокеры (почему именно следующая итерация, а не эта):**

| Требование                              | Сейчас в проекте                              |
|-----------------------------------------|-----------------------------------------------|
| `InputRequiredResult` появился в fastmcp **4.0.0** | `pyproject.toml`: `fastmcp>=3.4.6,<4` (стоит 3.4.6) |
| Нужен протокол MCP **2026-07-28+**       | `mcp` 1.27.0, `LATEST_PROTOCOL_VERSION = "2025-11-25"` |

То есть delete разблокируется **апгрейдом fastmcp до 4.x + свежего MCP SDK**, а не переходом в
stateful/SSE режим (это отдельная, теперь уже не нужная для delete задача из Roadmap note).

**Форма будущего тула:** отдельный тул удаления, принимающий `pk`, single-instance-only, с
подтверждением через `InputRequiredResult` и метаданными `annotations={"destructiveHint": True}`
(поле `ToolAnnotations.destructiveHint` подтверждено в `mcp/types.py`).

**В этой итерации delete-тул просто не генерируется.** Явный `NotImplementedError`-заглушки не
делаем — отсутствующий тул честнее, чем тул, который всегда падает.

> Уточнение к формулировке ревью: официальная документация fastmcp **не** объявляет `ctx.elicit()`
> deprecated — она разделяет их по эпохам протокола (`ctx.elicit()` для ≤2025-11-25,
> `InputRequiredResult` для 2026-07-28+), и сервер, которому нужны обе, ветвится по
> `ctx.request_context.protocol_version`. Для нас это ничего не меняет: `ctx.elicit()` в stateless
> JSON-режиме не работает независимо от статуса deprecation, а целевой механизм —
> `InputRequiredResult`.

---

## 10. Расширение тестового приложения

Продолжаем расширять **существующий `blog`** — он для этого и сделан. Новые сущности вводим, если
они дают реальные юзкейсы (например, `Like` / `Comment` для FK-обратных связей и M2M).

Нужны поля, реально нагружающие field-type-зависимый рендер и readable/editable-экстракцию:

- `choices` (для §7.3 и `ChoicesFieldListFilter`)
- `BooleanField`
- **nullable `ForeignKey`** (проверка `nullable`-маркера и `__isnull`-параметра)
- `JSONField`

Фильтры на тестовой админке:

- один **кастомный `SimpleListFilter`** — покрывает ветку «параметр есть, `lookup_choices` есть,
  поля модели нет»;
- **`AutocompleteSelectFilter`** — должен поддерживаться и вести себя идентично плейн FK.

Для последнего потребуется `unfold.contrib.filters` в `INSTALLED_APPS` тестового проекта
(сейчас не подключён) и `search_fields` на связанной admin-модели.

Конвенции — по skill'ам `test` / `test-fixtures`: фикстуры по семантическим группам
(`tests/fixtures/<topic>.py` + re-export в `conftest.py`, когда их станет больше пары), фабрики
через `_create`, snapshot-ассерты вместо ручных.

> Ожидаемый побочный эффект: снапшоты `test_build_admin_model_resource.ambr` /
> `test_build_admin_app_resource.ambr` изменятся — и от новых полей, и от исправления §4.1
> (`key` фильтров станет реальным GET-параметром). Это желаемое изменение, а не регрессия.

---

## 11. Остаточные открытые вопросы

Их немного — почти всё закрыто ревью и §12.

### 11.1 Имена параметров с дандерами в MCP-контракте
Экспериментально (§12.2) `author__id__exact` работает **вербатим** — и в URI-шаблоне, и в
сигнатуре Python, и при разборе `read_resource`. Значит query-параметры MCP-ресурса могут быть
1:1 зеркалом GET-параметров админки.
**Вопрос:** оставляем сырые дандер-имена (максимальная верность админке, зато уродливо для LLM),
или даём алиасы (`author`, `author_isnull`) с трансляцией?
*Рекомендация:* сырые имена + внятный `description` — меньше кода, невозможно рассинхронизировать,
и агент видит ровно то, что понимает Django.
A: Сырые имена, 1в1 трансляция.

### 11.2 Потолок `limit` и дефолтный размер страницы

Брать `model_admin.list_per_page` как дефолт `limit`, а потолок вынести в
`UNFOLD_AGENTIC_LAYER`? Или фиксированный дефолт независимо от админки?
A: list_per_page

### 11.3 Гранулярность `order_by`

`Literal` из сортируемых колонок (валидируется на входе, но перестраивается при изменении
`list_display`) — или свободный `str` с проверкой в рантайме? `Literal` лучше для LLM, но
жёстче привязывает схему к текущему `list_display`.

A: Литерал, свободных типов должно быть минимум

### 11.4 Рассинхрон заявленных версий Django

`pyproject.toml` объявляет `django>=4.2` и классификаторы 4.2 / 5.0 / 5.1, в окружении стоит
**6.0.7**, а решение по спеке — «целевая Django 5+». Три разных ответа. Нужно привести к одному
(и, вероятно, поднять нижнюю границу до 5.x — часть решений выше опирается на поведение
современного `ChangeList`).
A: Приводим к современному, да. Пайпроджект надо привести к 5+

---

## 12. Приложение: что проверено экспериментально

Все проверки выполнены на живом `django_test_app` (Django 6.0.7, fastmcp 3.4.6, mcp 1.27.0);
временные тесты удалены, рабочее дерево чистое, `24 passed`.

### 12.1 Проброс Django-request через ASGI scope — ✅
Тул, зарегистрированный на `mcp`, прочитал
`get_http_request().scope["django_unfold_agentic_layer.request"]` и получил живой Django-request
с `request.user == <User: staff>`, при вызове через реальный HTTP POST на `/mcp/` с
`client.force_login(staff_user)`. Scope-ключи в хендлере:
`['client', 'django_unfold_agentic_layer.request', 'headers', 'http_version', 'method', 'path',
'query_string', 'raw_path', 'scheme', 'server', 'type']`.

### 12.2 Динамическая сигнатура + RFC 6570 query-параметры — ✅
`inspect.Signature` с `Annotated[..., Field(...)]`, скормленная `mcp.resource(uri)`, дала
корректный JSON Schema:
```json
{"author__id__exact": {"anyOf": [{"type":"string"},{"type":"null"}], "default": null},
 "limit": {"default": 50, "description": "Max rows", "maximum": 200, "minimum": 1, "type": "integer"}}
```
`read_resource("dj-admin://blog/blogpost/?author__id__exact=7&q=hello&limit=10")` вернул
`ResourceResult(contents=[ResourceContent(..., mime_type='application/json')])`, `limit`
приведён к `int`. Дандер-имена прошли без искажений.

### 12.3 Минимальный синтетический request + фильтры — ✅
`HttpRequest()` с `method` / `user` / `GET` достаточен для `get_changelist_instance()`; поиск
(`q=second`), фильтр (`author__id__exact=2`), сортировка (`o=-1`) и кастомный `SimpleListFilter`
(`title_startswith=a`) отработали. `expected_parameters()` проверен на пяти семействах фильтров
(таблица в §4.2). Неизвестный параметр → `IncorrectLookupParameters`.

### 12.4 Семантика `o` и `p` — ✅
`o` = 1-based индексы `list_display`, точка для мультиколоночной, `-` для убывания;
`o=title` **молча игнорируется**. Пагинация — `p=<страница>` + `all=`, `limit`/`offset` не
существует.

### 12.5 Форма и поля — ✅
`get_form()` → `title` (required), `body` (optional), `author` (required, `ModelChoiceField`,
виджет `RelatedFieldWidgetWrapper` → `UnfoldAdminSelectWidget`); `created_at` (`auto_now_add`)
в форме отсутствует. `get_readonly_fields()` → `()`.

### 12.6 Permission-API — ✅ (по исходникам)
`AdminSite._build_app_dict(request)` фильтрует по `has_module_permission` + `get_model_perms`;
`ModelAdmin.get_actions(request)` уже применяет `_filter_actions_by_permissions`; unfold даёт
`get_actions_list/detail/row/submit_line(request)` поверх `_filter_unfold_actions_by_permissions`,
которое поддерживает и объектные проверки (`has_<perm>_permission(request, object_id)`).

---

## Приложение: Field / Annotated

```python
from typing import Annotated
from pydantic import Field

@mcp.tool
def process_image(
    image_url: Annotated[str, Field(description="URL of the image to process")],
    resize: Annotated[bool, Field(description="Whether to resize the image")] = False,
    width: Annotated[int, Field(description="Target width in pixels", ge=1, le=2000)] = 800,
    format: Annotated[
        Literal["jpeg", "png", "webp"],
        Field(description="Output image format"),
    ] = "jpeg",
) -> dict:
    """Process an image with optional resizing."""
```

`Field` даёт `description`, `ge`/`gt`/`le`/`lt`, `min_length`/`max_length`, `pattern`, `default`.

Маппинг Django → Pydantic на первом проходе держим неглубоким: `max_length` поля →
`Field(max_length=...)`, `choices` → `Literal`, `null` → `| None`. Более экзотические
`field.validators` (`MinValueValidator` и т.п.) в констрейнты **не** транслируем — они всё равно
отработают внутри `form.is_valid()` (§9), и дублировать валидацию в двух местах значит рисковать
расхождением.
