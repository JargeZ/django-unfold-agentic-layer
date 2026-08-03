"""MCP server for Django Unfold documentation."""

from fastmcp import FastMCP

from .docs import ALL_SECTIONS, DOCS

mcp = FastMCP(
    "django_unfold_agentic_layer",
    instructions=(
        "Django Unfold documentation server. "
        "Use these tools to get accurate documentation for implementing "
        "Django Unfold admin theme features. Always check the relevant "
        "documentation before generating Django Unfold code."
    ),
)


@mcp.tool()
def unfold_get_started() -> str:
    """Get Django Unfold installation instructions and quickstart guide.

    Returns complete setup instructions including pip/uv/poetry install,
    INSTALLED_APPS configuration, URL setup, and ModelAdmin inheritance.
    """
    return DOCS["installation"]["content"]


@mcp.tool()
def unfold_configuration() -> str:
    """Get the complete UNFOLD settings dictionary documentation.

    Returns all configuration options: SITE_TITLE, SITE_HEADER, SITE_ICON,
    SITE_LOGO, SIDEBAR navigation, COLORS (oklch), THEME, ENVIRONMENT,
    DASHBOARD_CALLBACK, LOGIN, STYLES, SCRIPTS, BORDER_RADIUS, TABS, and more.
    Includes callback function examples.
    """
    return DOCS["configuration"]["content"]


@mcp.tool()
def unfold_actions() -> str:
    """Get documentation for Django Unfold actions.

    Covers all action types: global (changelist top), row (each row),
    detail (changeform top), and submit line (form submit). Includes
    @action decorator usage, icons, ActionVariant colors, permissions,
    and complete code examples.
    """
    return DOCS["actions"]["content"]


@mcp.tool()
def unfold_filters() -> str:
    """Get documentation for Django Unfold custom filters.

    Covers unfold.contrib.filters: DropdownFilter, RelatedDropdownFilter,
    MultipleRelatedDropdownFilter, ChoicesDropdownFilter, SingleNumericFilter,
    RangeNumericFilter, SliderNumericFilter, RangeDateFilter, RangeDateTimeFilter,
    TextFilter, FieldTextFilter, AutocompleteSelectFilter, and list_filter_submit.
    """
    return DOCS["filters"]["content"]


@mcp.tool()
def unfold_decorators() -> str:
    """Get documentation for the @display decorator.

    Covers label display (auto-colored and custom-colored), header display
    (two-line with initials/images), and dropdown display (list-based and
    custom template). Includes all parameter options and examples.
    """
    return DOCS["decorators"]["content"]


@mcp.tool()
def unfold_components() -> str:
    """Get documentation for Django Unfold UI components.

    Covers all dashboard components: card, chart/bar, chart/line, button,
    container, flex, icon, navigation, progress, separator, table, text,
    title, tracker, cohort, layer. Includes template syntax, nesting,
    and Chart.js data format.
    """
    return DOCS["components"]["content"]


@mcp.tool()
def unfold_inlines() -> str:
    """Get documentation for Django Unfold inlines.

    Covers StackedInline, TabularInline, NonrelatedTabularInline,
    NonrelatedStackedInline, and sortable inlines with drag-and-drop.
    Includes setup, get_form_queryset, save_new_instance, ordering_field.
    """
    return DOCS["inlines"]["content"]


@mcp.tool()
def unfold_widgets() -> str:
    """Get documentation for Django Unfold form widgets.

    Covers ArrayWidget (PostgreSQL ArrayField), WYSIWYG editor (Trix),
    and all available widget classes: text, email, URL, integer, decimal,
    textarea, password, select, radio, date, time, color, UUID, image,
    file, boolean switch, money. Includes formfield_overrides usage.
    """
    return DOCS["widgets"]["content"]


@mcp.tool()
def unfold_tabs() -> str:
    """Get documentation for Django Unfold changelist tabs.

    Covers UNFOLD['TABS'] configuration with models list, items list,
    title, link (reverse_lazy), and permission callbacks.
    """
    return DOCS["tabs"]["content"]


@mcp.tool()
def unfold_dashboard() -> str:
    """Get documentation for creating a custom Django Unfold dashboard.

    Covers template creation (admin/index.html), DASHBOARD_CALLBACK setup,
    template directory configuration, and using components in dashboard.
    """
    return DOCS["dashboard"]["content"]


@mcp.tool()
def unfold_pages() -> str:
    """Get documentation for creating custom admin pages.

    Covers UnfoldModelAdminViewMixin, class-based views integration,
    get_urls() override, model_admin=self requirement, template extension,
    and sidebar navigation integration.
    """
    return DOCS["pages"]["content"]


@mcp.tool()
def unfold_styles_scripts() -> str:
    """Get documentation for custom styles, scripts, and Tailwind CSS.

    Covers UNFOLD['STYLES'] and UNFOLD['SCRIPTS'] configuration,
    Tailwind 4.x setup (0.57+), Tailwind 3.x setup (below 0.56),
    CSS compilation, and recommendations.
    """
    return DOCS["styles_scripts"]["content"]


@mcp.tool()
def unfold_integration_import_export() -> str:
    """Get django-import-export integration documentation.

    Covers INSTALLED_APPS setup, ImportForm, ExportForm,
    SelectableFieldsExportForm, and ExportActionModelAdmin.
    """
    return DOCS["integrations_import_export"]["content"]


@mcp.tool()
def unfold_integration_guardian() -> str:
    """Get django-guardian integration documentation.

    Covers setup for object-level permissions with unfold.contrib.guardian.
    """
    return DOCS["integrations_guardian"]["content"]


@mcp.tool()
def unfold_integration_simple_history() -> str:
    """Get django-simple-history integration documentation.

    Covers INSTALLED_APPS ordering and dual inheritance with
    SimpleHistoryAdmin and ModelAdmin.
    """
    return DOCS["integrations_simple_history"]["content"]


@mcp.tool()
def unfold_integration_celery_beat() -> str:
    """Get django-celery-beat integration documentation.

    Covers unregistering default admin classes, re-registering with
    Unfold ModelAdmin, custom form widgets, and complete code example.
    """
    return DOCS["integrations_celery_beat"]["content"]


@mcp.tool()
def unfold_integration_modeltranslation() -> str:
    """Get django-modeltranslation integration documentation.

    Covers TabbedTranslationAdmin + ModelAdmin dual inheritance
    and EXTENSIONS flags configuration for language indicators.
    """
    return DOCS["integrations_modeltranslation"]["content"]


@mcp.tool()
def unfold_integration_money() -> str:
    """Get django-money integration documentation. Auto-styled, no extra config needed."""
    return DOCS["integrations_money"]["content"]


@mcp.tool()
def unfold_integration_constance() -> str:
    """Get django-constance integration documentation.

    Covers INSTALLED_APPS ordering, UNFOLD_CONSTANCE_ADDITIONAL_FIELDS,
    and custom field configuration.
    """
    return DOCS["integrations_constance"]["content"]


@mcp.tool()
def unfold_integration_location_field() -> str:
    """Get django-location-field integration documentation.

    Covers UnfoldAdminLocationWidget setup and form configuration.
    """
    return DOCS["integrations_location_field"]["content"]


@mcp.tool()
def unfold_integration_djangoql() -> str:
    """Get djangoql integration documentation. Auto-styled, no extra config needed."""
    return DOCS["integrations_djangoql"]["content"]


@mcp.tool()
def unfold_integration_json_widget() -> str:
    """Get django-json-widget integration documentation. Auto-styled with dark mode."""
    return DOCS["integrations_json_widget"]["content"]


@mcp.tool()
def unfold_features_overview() -> str:
    """Get a complete overview of all Django Unfold features and supported packages.

    Lists all core features, third-party integrations, and the technology stack.
    """
    return DOCS["features_overview"]["content"]


@mcp.tool()
def unfold_complete_example() -> str:
    """Get a complete Django Unfold integration example project.

    Returns a full working example with settings.py, models.py, admin.py,
    views.py, and dashboard template showing all major features together.
    """
    return DOCS["complete_example"]["content"]


@mcp.tool()
def unfold_search_docs(query: str) -> str:
    """Search Django Unfold documentation by keyword.

    Args:
        query: Search term to find in documentation sections.
               Examples: 'sidebar', 'chart', 'import export', 'color', 'action'.

    Returns matching documentation sections with full content.
    """
    query_lower = query.lower()
    results = []

    for key in ALL_SECTIONS:
        doc = DOCS[key]
        if (
            query_lower in doc["title"].lower()
            or query_lower in doc["content"].lower()
            or query_lower in key.lower()
        ):
            results.append(f"## {doc['title']}\n\n{doc['content']}")

    if not results:
        available = ", ".join(DOCS[k]["title"] for k in ALL_SECTIONS)
        return f"No results found for '{query}'. Available sections: {available}"

    return f"Found {len(results)} matching section(s):\n\n" + "\n\n---\n\n".join(results)
