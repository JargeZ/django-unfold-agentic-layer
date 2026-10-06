"""Complete Django Unfold documentation content for MCP tools."""

DOCS = {
    "installation": {
        "title": "Installation & Quickstart",
        "content": """# Django Unfold - Installation & Quickstart

## Installation

Install Django Unfold using your preferred package manager:

```bash
pip install django-unfold
uv add django-unfold
poetry add django-unfold
```

## Configuration

Add `unfold` to the **beginning** of your `INSTALLED_APPS` in `settings.py`:

```python
# settings.py

INSTALLED_APPS = [
    "unfold",  # Must be before django.contrib.admin
    "unfold.contrib.filters",  # optional, if special filters are needed
    "unfold.contrib.forms",  # optional, if special form elements are needed
    "unfold.contrib.inlines",  # optional, if special inlines are needed
    "unfold.contrib.import_export",  # optional, if django-import-export package is used
    "unfold.contrib.guardian",  # optional, if django-guardian package is used
    "unfold.contrib.simple_history",  # optional, if django-simple-history package is used
    "unfold.contrib.location_field",  # optional, if django-location-field package is used
    "unfold.contrib.constance",  # optional, if django-constance package is used
    "django.contrib.admin",  # required
]
```

## URL Configuration

```python
# urls.py

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
    # Other URL paths
]
```

## ModelAdmin Inheritance

**CRITICAL**: All admin classes MUST inherit from `unfold.admin.ModelAdmin` instead of `django.contrib.admin.ModelAdmin`. Using the default admin class will result in unstyled forms and missing Unfold functionality.

```python
# admin.py

from django.contrib import admin
from unfold.admin import ModelAdmin


@admin.register(MyModel)
class CustomAdminClass(ModelAdmin):
    pass
```

## Key Points
- `unfold` must be listed BEFORE `django.contrib.admin` in INSTALLED_APPS
- Always use `unfold.admin.ModelAdmin` as the base class
- The default admin URL configuration (`admin.site.urls`) works without changes
- No database migrations are required
- Unfold works alongside the default Django admin
""",
    },
    "configuration": {
        "title": "Settings & Configuration Options",
        "content": """# Django Unfold - Complete Settings Configuration

The `UNFOLD` dictionary in `settings.py` provides comprehensive configuration options. The admin works with defaults; no configuration is required.

## Complete Configuration Example

```python
# settings.py

from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

UNFOLD = {
    # Site branding
    "SITE_TITLE": "Custom suffix in <title> tag",
    "SITE_HEADER": "Appears in sidebar at the top",
    "SITE_SUBHEADER": "Appears under SITE_HEADER",
    "SITE_DROPDOWN": [
        {
            "icon": "diamond",
            "title": _("My site"),
            "link": "https://example.com",
        },
    ],
    "SITE_URL": "/",

    # Icons and logos (support light/dark mode)
    # Single mode:
    # "SITE_ICON": lambda request: static("icon.svg"),
    # Dual mode:
    "SITE_ICON": {
        "light": lambda request: static("icon-light.svg"),
        "dark": lambda request: static("icon-dark.svg"),
    },
    # "SITE_LOGO": lambda request: static("logo.svg"),
    "SITE_LOGO": {
        "light": lambda request: static("logo-light.svg"),
        "dark": lambda request: static("logo-dark.svg"),
    },
    "SITE_SYMBOL": "speed",  # Material symbol from icon set
    "SITE_FAVICONS": [
        {
            "rel": "icon",
            "sizes": "32x32",
            "type": "image/svg+xml",
            "href": lambda request: static("favicon.svg"),
        },
    ],

    # Display options
    "SHOW_HISTORY": True,  # show/hide "History" button, default: True
    "SHOW_VIEW_ON_SITE": True,  # show/hide "View on site" button, default: True
    "SHOW_BACK_BUTTON": False,  # show/hide "Back" button on changeform, default: False

    # Environment label (displays in header)
    "ENVIRONMENT": "sample_app.environment_callback",
    "ENVIRONMENT_TITLE_PREFIX": "sample_app.environment_title_prefix_callback",

    # Dashboard
    "DASHBOARD_CALLBACK": "sample_app.dashboard_callback",

    # Theme: "dark" or "light" (disables theme switcher when set)
    "THEME": "dark",

    # Login page customization
    "LOGIN": {
        "image": lambda request: static("sample/login-bg.jpg"),
        "redirect_after": lambda request: reverse_lazy("admin:APP_MODEL_changelist"),
        "form": "app.forms.CustomLoginForm",  # Inherits from unfold.forms.AuthenticationForm
    },

    # Custom styles and scripts
    "STYLES": [
        lambda request: static("css/style.css"),
    ],
    "SCRIPTS": [
        lambda request: static("js/script.js"),
    ],

    # Border radius customization
    "BORDER_RADIUS": "6px",

    # Color customization (oklch format)
    "COLORS": {
        "base": {
            "50": "oklch(98.5% .002 247.839)",
            "100": "oklch(96.7% .003 264.542)",
            "200": "oklch(92.8% .006 264.531)",
            "300": "oklch(87.2% .01 258.338)",
            "400": "oklch(70.7% .022 261.325)",
            "500": "oklch(55.1% .027 264.364)",
            "600": "oklch(44.6% .03 256.802)",
            "700": "oklch(37.3% .034 259.733)",
            "800": "oklch(27.8% .033 256.848)",
            "900": "oklch(21% .034 264.665)",
            "950": "oklch(13% .028 261.692)",
        },
        "primary": {
            "50": "oklch(97.7% .014 308.299)",
            "100": "oklch(94.6% .033 307.174)",
            "200": "oklch(90.2% .063 306.703)",
            "300": "oklch(82.7% .119 306.383)",
            "400": "oklch(71.4% .203 305.504)",
            "500": "oklch(62.7% .265 303.9)",
            "600": "oklch(55.8% .288 302.321)",
            "700": "oklch(49.6% .265 301.924)",
            "800": "oklch(43.8% .218 303.724)",
            "900": "oklch(38.1% .176 304.987)",
            "950": "oklch(29.1% .149 302.717)",
        },
        "font": {
            "subtle-light": "var(--color-base-500)",
            "subtle-dark": "var(--color-base-400)",
            "default-light": "var(--color-base-600)",
            "default-dark": "var(--color-base-300)",
            "important-light": "var(--color-base-900)",
            "important-dark": "var(--color-base-100)",
        },
    },

    # Extensions (e.g., modeltranslation)
    "EXTENSIONS": {
        "modeltranslation": {
            "flags": {
                "en": "🇬🇧",
                "fr": "🇫🇷",
                "nl": "🇧🇪",
            },
        },
    },

    # Sidebar configuration
    "SIDEBAR": {
        "show_search": False,       # Search in applications and models names
        "command_search": False,    # Replace sidebar search with command search
        "show_all_applications": False,  # Dropdown with all applications and models
        "navigation": [
            {
                "title": _("Navigation"),
                "separator": True,      # Top border
                "collapsible": True,    # Collapsible group of links
                "items": [
                    {
                        "title": _("Dashboard"),
                        "icon": "dashboard",  # Material Symbols icon
                        "link": reverse_lazy("admin:index"),
                        "badge": "sample_app.badge_callback",
                        "badge_variant": "info",  # info, success, warning, primary, danger
                        "badge_style": "solid",   # background fill style
                        "permission": lambda request: request.user.is_superuser,
                    },
                    {
                        "title": _("Users"),
                        "icon": "people",
                        "link": reverse_lazy("admin:auth_user_changelist"),
                    },
                ],
            },
        ],
    },

    # Tabs configuration
    "TABS": [
        {
            "models": [
                "app_label.model_name_in_lowercase",
            ],
            "items": [
                {
                    "title": _("Your custom title"),
                    "link": reverse_lazy("admin:app_label_model_name_changelist"),
                    "permission": "sample_app.permission_callback",
                },
            ],
        },
    ],
}
```

## Callback Functions

```python
def dashboard_callback(request, context):
    \\"\\"\\"Callback to prepare custom variables for the dashboard template.\\"\\"\\"
    context.update({
        "sample": "example",  # injected into templates/admin/index.html
    })
    return context


def environment_callback(request):
    \\"\\"\\"Returns [text, color_type] for the environment label in header.\\"\\"\\"
    return ["Production", "danger"]  # info, danger, warning, success


def badge_callback(request):
    return 3


def permission_callback(request):
    return request.user.has_perm("sample_app.change_model")
```

## Icons
Unfold uses Google Material Symbols. Browse available icons at: https://fonts.google.com/icons
Icons are specified as strings, e.g., "dashboard", "people", "settings", "speed", "diamond", etc.
""",
    },
    "actions": {
        "title": "Actions (Global, Row, Detail, Submit Line)",
        "content": """# Django Unfold - Actions

Read the base Django actions documentation first: https://docs.djangoproject.com/en/5.1/ref/contrib/admin/actions/

Unfold provides enhanced actions with icons, variants, and multiple action types.

## Action Types Overview

| Type | Location | Usage |
|------|----------|-------|
| Global | Changelist - top | General actions for all instances in listing |
| Row | Changelist - each row | Action for one specific instance from listing |
| Detail | Changeform - top | Action for one specific instance from detail |
| Submit line | Changeform - submit line | Action performed during form submit |

## Basic Action Example

```python
# admin.py

from django.contrib.auth.models import User
from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from unfold.admin import ModelAdmin
from unfold.decorators import action

@admin.register(User)
class UserAdmin(ModelAdmin):
    actions_list = ["custom_action"]

    @action(description="Custom action", icon="person")
    def custom_action(self, request: HttpRequest, queryset: QuerySet):
        pass
```

## Icon Support

```python
@action(description="Custom action", icon="person")
def custom_action(self, request: HttpRequest, queryset: QuerySet):
    pass
```

## Action Variants

Unfold supports different color variants for actions:

```python
from unfold.decorators import action
from unfold.enums import ActionVariant

# Available variants:
# ActionVariant.DEFAULT = "default"
# ActionVariant.PRIMARY = "primary"
# ActionVariant.SUCCESS = "success"
# ActionVariant.INFO = "info"
# ActionVariant.WARNING = "warning"
# ActionVariant.DANGER = "danger"

@action(description="Custom action", variant=ActionVariant.PRIMARY)
def custom_action(self, request: HttpRequest, queryset: QuerySet):
    pass
```

## Permissions

Two ways to handle permissions:

### 1. ModelAdmin Method-based Permissions
```python
@admin.register(User)
class UserAdmin(ModelAdmin):
    @action(
        description="Custom action",
        permissions=["custom_action", "auth.view_user"]  # Both permission types
    )
    def custom_action(self, request, queryset):
        pass

    def has_custom_action_permission(self, request, obj=None):
        return request.user.is_superuser
```

### 2. Django Built-in Permissions
Use format `app_label.permission_codename`. Note: with built-in permissions (containing a dot), the permission check won't receive the object instance during detail view checks.

## Global, Row, and Detail Actions

These actions are based on custom URLs. Handler function is basically a function-based view.

- For actions **without** intermediate steps: write logic inside handler directly
- For actions **with** intermediate steps: redirect to custom URL with custom view
- Request and object ID are passed to handler functions
- Return redirect back to detail or listing

```python
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from unfold.admin import ModelAdmin
from unfold.decorators import action

@admin.register(MyModel)
class MyModelAdmin(ModelAdmin):
    actions_list = ["my_global_action"]       # Global actions
    actions_row = ["my_row_action"]           # Row actions
    actions_detail = ["my_detail_action"]     # Detail actions
    actions_submit_line = ["my_submit_action"]  # Submit line actions

    @action(description="Global action", icon="public", variant=ActionVariant.PRIMARY)
    def my_global_action(self, request, queryset):
        # Global action logic
        pass

    @action(description="Row action", icon="edit")
    def my_row_action(self, request, object_id):
        # Row action - receives object_id
        obj = self.model.objects.get(pk=object_id)
        return redirect(reverse_lazy("admin:app_model_changelist"))

    @action(description="Detail action", icon="visibility")
    def my_detail_action(self, request, object_id):
        # Detail action - receives object_id
        obj = self.model.objects.get(pk=object_id)
        return redirect(reverse_lazy("admin:app_model_change", args=[object_id]))

    @action(description="Save & notify", icon="send")
    def my_submit_action(self, request, obj):
        # Submit line action - receives the object being saved
        pass
```

## Hide Built-in Actions

```python
class MyAdmin(ModelAdmin):
    actions_list = ["my_action", "existing_action_wrapper"]
    actions_list_hide_default = True   # Hide default list actions
    actions_detail_hide_default = True  # Hide default detail actions

    @action(description=_("History"), icon="history")
    def existing_action_wrapper(self, *args, **kwargs):
        return redirect("https://example.com")
```
""",
    },
    "filters": {
        "title": "Custom Filters",
        "content": """# Django Unfold - Filters

Unfold extends Django's filtering with custom filters through `unfold.contrib.filters`.

## Setup

```python
# settings.py

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
]
```

## Submit Button

When using filters with input fields, users need a submit button. Set `list_filter_submit = True`:

```python
from unfold.admin import ModelAdmin

class MyAdmin(ModelAdmin):
    list_filter_submit = True  # Adds submit button to filter form
    list_filter = [
        # your filters here
    ]
```

## Available Filter Types

### Dropdown Filters
```python
from unfold.contrib.filters.admin import (
    DropdownFilter,
    RelatedDropdownFilter,
    MultipleRelatedDropdownFilter,
    ChoicesDropdownFilter,
    MultipleChoicesDropdownFilter,
)

class MyAdmin(ModelAdmin):
    list_filter = [
        # Simple dropdown for model fields
        ("status", DropdownFilter),
        # Related model dropdown
        ("category", RelatedDropdownFilter),
        # Multiple selection related dropdown
        ("tags", MultipleRelatedDropdownFilter),
        # Choices field dropdown
        ("status", ChoicesDropdownFilter),
        # Multiple choices dropdown
        ("status", MultipleChoicesDropdownFilter),
    ]
```

### Numeric Filters
```python
from unfold.contrib.filters.admin import (
    SingleNumericFilter,
    RangeNumericFilter,
    SliderNumericFilter,
)

class MyAdmin(ModelAdmin):
    list_filter_submit = True
    list_filter = [
        ("price", SingleNumericFilter),   # Single numeric input
        ("price", RangeNumericFilter),    # Min/max range inputs
        ("rating", SliderNumericFilter),  # Slider input
    ]
```

### Date/Time Filters
```python
from unfold.contrib.filters.admin import (
    RangeDateFilter,
    RangeDateTimeFilter,
)

class MyAdmin(ModelAdmin):
    list_filter_submit = True
    list_filter = [
        ("created_at", RangeDateFilter),      # Date range
        ("updated_at", RangeDateTimeFilter),  # DateTime range
    ]
```

### Text Filters
```python
from unfold.contrib.filters.admin import (
    TextFilter,
    FieldTextFilter,
)

class MyAdmin(ModelAdmin):
    list_filter_submit = True
    list_filter = [
        ("name", FieldTextFilter),  # Text input for specific field
    ]
```

### Custom Text Filter
```python
from unfold.contrib.filters.admin import TextFilter

class CustomTextFilter(TextFilter):
    title = "Custom Search"
    parameter_name = "custom_search"

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(name__icontains=self.value())
        return queryset

class MyAdmin(ModelAdmin):
    list_filter_submit = True
    list_filter = [CustomTextFilter]
```

### Autocomplete Filters
```python
from unfold.contrib.filters.admin import (
    AutocompleteSelectFilter,
    AutocompleteSelectMultipleFilter,
)

class MyAdmin(ModelAdmin):
    list_filter = [
        ("author", AutocompleteSelectFilter),
        ("tags", AutocompleteSelectMultipleFilter),
    ]
```

**Note**: The related model's admin must have `search_fields` defined for autocomplete to work.
""",
    },
    "decorators": {
        "title": "Display Decorator",
        "content": """# Django Unfold - @display Decorator

Unfold provides an enhanced `@display` decorator via `unfold.decorators.display`, fully compatible with Django's native `django.contrib.admin.decorators.display` but with additional features.

## Import

```python
from unfold.decorators import display
```

## Label Display

### Auto-colored labels
```python
@display(description=_("Status"), ordering="status", label=True)
def show_status(self, obj):
    return obj.status
```

### Custom-colored labels
```python
from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _

class UserStatus(TextChoices):
    ACTIVE = "ACTIVE", _("Active")
    PENDING = "PENDING", _("Pending")
    INACTIVE = "INACTIVE", _("Inactive")
    CANCELLED = "CANCELLED", _("Cancelled")

class UserAdmin(ModelAdmin):
    list_display = ["show_status"]

    @display(
        description=_("Status"),
        ordering="status",
        label={
            UserStatus.ACTIVE: "success",     # green
            UserStatus.PENDING: "info",       # blue
            UserStatus.INACTIVE: "warning",   # orange
            UserStatus.CANCELLED: "danger",   # red
        },
    )
    def show_status(self, obj):
        return obj.status
```

### Label with custom text
```python
@display(description=_("Status"), ordering="status", label=True)
def show_status_with_custom_label(self, obj):
    return obj.status, obj.get_status_display()
```

## Header Display (Two-line)

`@display(header=True)` shows two pieces of information in a single cell:

```python
class UserAdmin(ModelAdmin):
    list_display = ["display_as_two_line_heading"]

    @display(header=True)
    def display_as_two_line_heading(self, obj):
        \\"\\"\\"Returns [main_heading, sub_heading, optional_initials_or_image]\\"\\"\\"
        return [
            "First main heading",
            "Smaller additional description",  # Use None if not needed
            "AB",  # Short text as circular badge prefix
            # OR use an image dict:
            # {
            #     "path": "some/path/picture.jpg",
            #     "squared": True,      # Square format (default: circle)
            #     "borderless": True,   # No border
            #     "width": 64,          # Custom width
            #     "height": 48,         # Custom height
            # }
        ]
```

## Dropdown Support

### List-based Dropdown
```python
class UserAdmin(ModelAdmin):
    list_display = ["display_dropdown"]

    @display(description=_("Status"), dropdown=True)
    def display_dropdown(self, obj):
        return {
            "title": "Custom dropdown title",
            "striped": True,       # Optional: alternating colors
            "height": 200,         # Optional: dropdown height in px
            "max_height": 300,     # Optional: max height with scroll
            "width": 240,          # Optional: dropdown width in px
            "items": [
                {"title": "First title", "link": "#"},  # link is optional
                {"title": "Second title", "link": "#"},
            ]
        }
```

### Custom Template Dropdown
```python
@display(description=_("Status"), dropdown=True)
def display_dropdown(self, obj):
    return {
        "title": "Custom dropdown title",
        "content": "Any HTML content or template string",
    }
```
""",
    },
    "components": {
        "title": "UI Components for Dashboards",
        "content": """# Django Unfold - UI Components

Unfold provides predefined templates for dashboard development. Components can be nested for unlimited layout combinations.

## Usage Syntax

```html
{% load unfold %}

{% component "unfold/components/card.html" %}
    {% component "unfold/components/title.html" %}
        Card Title
    {% endcomponent %}
{% endcomponent %}
```

Components receive variables via `{% include with param1=value1 %}` syntax.

## Available Components

| Component | Description | Parameters |
|-----------|-------------|------------|
| unfold/components/button.html | Basic button | class, name, href, submit |
| unfold/components/card.html | Card component | class, title, footer, label, icon |
| unfold/components/chart/bar.html | Bar chart | class, data, height, width |
| unfold/components/chart/line.html | Line chart | class, data, height, width |
| unfold/components/cohort.html | Cohort component | data |
| unfold/components/container.html | Max-width wrapper | class |
| unfold/components/flex.html | Flex items | class, col |
| unfold/components/icon.html | Icon element | class |
| unfold/components/navigation.html | Navigation links | class, items |
| unfold/components/progress.html | Progress bar | class, value, title, description |
| unfold/components/separator.html | Horizontal rule | class |
| unfold/components/table.html | Table | table, card_included, striped |
| unfold/components/text.html | Paragraph | class |
| unfold/components/title.html | Heading | class |
| unfold/components/tracker.html | Tracker component | class, data |
| unfold/components/layer.html | Abstract wrapper | - |

## Complex Dashboard Example

```html
{% load i18n unfold %}

{% block content %}
    {% component "unfold/components/container.html" %}
        <div class="flex flex-col gap-4">
            {% component "unfold/components/navigation.html" with items=navigation %}
            {% endcomponent %}

            {% component "unfold/components/navigation.html" with class="ml-auto" items=filters %}
            {% endcomponent %}
        </div>

        <div class="grid grid-cols-3">
            {% for card in cards %}
                {% trans "Last 7 days" as label %}
                {% component "unfold/components/card.html" with class="lg:w-1/3" %}
                    {% component "unfold/components/text.html" %}
                        {{ card.title }}
                    {% endcomponent %}

                    {% component "unfold/components/title.html" %}
                        {{ card.metric }}
                    {% endcomponent %}
                {% endcomponent %}
            {% endfor %}
        </div>
    {% endcomponent %}
{% endblock %}
```

## Chart Data Format

Charts use Chart.js. Pass data as a dictionary from `DASHBOARD_CALLBACK`:

```python
def dashboard_callback(request, context):
    context.update({
        "chart_data": {
            "labels": ["Jan", "Feb", "Mar", "Apr"],
            "datasets": [
                {
                    "label": "Revenue",
                    "data": [100, 200, 150, 300],
                    "borderColor": "rgb(99, 102, 241)",
                    "backgroundColor": "rgba(99, 102, 241, 0.1)",
                }
            ]
        }
    })
    return context
```

Then in template:
```html
{% component "unfold/components/chart/line.html" with data=chart_data %}
{% endcomponent %}
```
""",
    },
    "inlines": {
        "title": "Inlines (Stacked, Tabular, Nonrelated, Sortable)",
        "content": """# Django Unfold - Inlines

Unfold provides styled inline classes. **Always use Unfold's inline classes** for visual consistency.

## Basic Inlines

```python
# admin.py

from django.contrib import admin
from django.contrib.auth.models import User
from unfold.admin import ModelAdmin, StackedInline, TabularInline


class MyStackedInline(StackedInline):
    model = MyRelatedModel


class MyTabularInline(TabularInline):
    model = MyRelatedModel


@admin.register(User)
class UserAdmin(ModelAdmin):
    inlines = [MyStackedInline, MyTabularInline]
```

**Important**: Use `unfold.admin.StackedInline` and `unfold.admin.TabularInline`, NOT `django.contrib.admin.StackedInline`/`TabularInline`.

## Nonrelated Inlines

Display models without foreign key relationship. Requires `unfold.contrib.inlines`.

```python
# settings.py
INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.inlines",
    # ...
]
```

```python
# admin.py

from django.contrib.auth.models import User
from unfold.admin import ModelAdmin
from unfold.contrib.inlines.admin import NonrelatedTabularInline  # or NonrelatedStackedInline
from .models import OtherModel


class OtherNonrelatedInline(NonrelatedTabularInline):
    model = OtherModel
    fields = ["field1", "field2"]  # Omit to display all fields

    def get_form_queryset(self, obj):
        \\"\\"\\"REQUIRED: Return queryset for nonrelated objects.\\"\\"\\"
        return self.model.objects.all()

    def save_new_instance(self, parent, instance):
        \\"\\"\\"REQUIRED: Handle saving with reference to parent.\\"\\"\\"
        pass


@admin.register(User)
class UserAdmin(ModelAdmin):
    inlines = [OtherNonrelatedInline]
```

## Sortable Inlines

Enable drag-and-drop sorting for inlines:

```python
# models.py

from django.db import models
from django.utils.translation import gettext_lazy as _


class MyModel(models.Model):
    weight = models.PositiveIntegerField(_("weight"), default=0, db_index=True)
```

```python
# admin.py

from unfold.admin import TabularInline  # Also works with StackedInline


class MyInline(TabularInline):
    model = MyModel
    ordering_field = "weight"          # Field used for ordering
    hide_ordering_field = True         # Hide the weight field from UI
    list_display = ["email", "weight"] # weight is mandatory in display
```

### Important Notes for Sortable Inlines:
- The ordering field MUST be `PositiveIntegerField` with `db_index=True`
- Sorting only works for existing (saved) records
- New items must be saved first before they can be sorted
- Sorting is for inline views only, not changelist views
""",
    },
    "widgets": {
        "title": "Form Widgets",
        "content": """# Django Unfold - Widgets

## ArrayWidget

Requires `unfold.contrib.forms`:

```python
# settings.py
INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.forms",
]
```

### Basic Usage
```python
# admin.py

from django.contrib import admin
from django.contrib.postgres.fields import ArrayField
from unfold.admin import ModelAdmin
from unfold.contrib.forms.widgets import ArrayWidget


@admin.register(MyModel)
class CustomAdminClass(ModelAdmin):
    formfield_overrides = {
        ArrayField: {
            "widget": ArrayWidget,
        }
    }
```

### With Choices
```python
from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _

class SomeChoices(TextChoices):
    OPTION_1 = "OPTION_1", _("Option 1")
    OPTION_2 = "OPTION_2", _("Option 2")

@admin.register(MyModel)
class CustomAdminClass(ModelAdmin):
    formfield_overrides = {
        ArrayField: {"widget": ArrayWidget}
    }

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)
        form.base_fields["array_field"].widget = ArrayWidget(choices=SomeChoices)
        return form
```

## WYSIWYG Editor (Trix)

Unfold includes built-in WYSIWYG support using the Trix editor:

```python
from unfold.widgets import UnfoldAdminTextareaWidget

class MyAdmin(ModelAdmin):
    formfield_overrides = {
        models.TextField: {"widget": UnfoldAdminTextareaWidget},
    }
```

## Available Widget Classes

All widgets are in `unfold.widgets`:

| Widget | Description |
|--------|-------------|
| UnfoldAdminTextInputWidget | Styled text input |
| UnfoldAdminEmailInputWidget | Styled email input |
| UnfoldAdminURLInputWidget | Styled URL input |
| UnfoldAdminIntegerFieldWidget | Styled integer input |
| UnfoldAdminDecimalFieldWidget | Styled decimal input |
| UnfoldAdminBigIntegerFieldWidget | Styled big integer input |
| UnfoldAdminTextareaWidget | Styled textarea |
| UnfoldAdminPasswordInput | Styled password input |
| UnfoldAdminSelectWidget | Styled select dropdown |
| UnfoldAdminRadioSelectWidget | Styled radio buttons |
| UnfoldAdminDateWidget | Styled date picker |
| UnfoldAdminTimeWidget | Styled time picker |
| UnfoldAdminSplitDateTimeWidget | Styled split datetime picker |
| UnfoldAdminColorInputWidget | Color picker |
| UnfoldAdminUUIDInputWidget | UUID input |
| UnfoldAdminImageFieldWidget | Image upload field |
| UnfoldAdminImageSmallFieldWidget | Small image upload |
| UnfoldAdminFileFieldWidget | File upload field |
| UnfoldBooleanWidget | Boolean widget |
| UnfoldBooleanSwitchWidget | Toggle switch |
| UnfoldAdminMoneyWidget | Money field (django-money) |

## Overriding Widgets

```python
from django.db import models
from unfold.admin import ModelAdmin
from unfold.widgets import UnfoldBooleanSwitchWidget

class MyAdmin(ModelAdmin):
    formfield_overrides = {
        models.BooleanField: {
            "widget": UnfoldBooleanSwitchWidget,
        },
    }
```
""",
    },
    "tabs": {
        "title": "Changelist Tabs",
        "content": """# Django Unfold - Changelist Tabs

Django Unfold provides tab navigation for changelist views.

## Configuration

All tab settings are in the `UNFOLD["TABS"]` key in `settings.py`:

```python
# settings.py

from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

UNFOLD = {
    "TABS": [
        {
            # Which models will display tab navigation
            "models": [
                "app_label.model_name_in_lowercase",
            ],
            # List of tab items
            "items": [
                {
                    "title": _("Your custom title"),
                    "link": reverse_lazy("admin:app_label_model_name_changelist"),
                    "permission": "sample_app.permission_callback",
                },
                {
                    "title": _("Another custom title"),
                    "link": reverse_lazy("admin:app_label_another_model_name_changelist"),
                    "permission": "sample_app.permission_callback",
                },
            ],
        },
    ],
}

# Permission callback
def permission_callback(request):
    return request.user.has_perm("sample_app.change_model")
```

## Key Points
- Tabs appear at the top of the changelist view
- Each tab group defines which models show the tabs (`models`)
- Each tab item has a `title`, `link`, and optional `permission`
- Permissions can be callback strings or lambda functions
- Multiple tab groups can be defined for different model sets
- Links typically use `reverse_lazy` pointing to admin changelist URLs
""",
    },
    "dashboard": {
        "title": "Custom Dashboard",
        "content": """# Django Unfold - Custom Dashboard

## Setup

### 1. Create the template

Create `templates/admin/index.html`:

```html
{% extends 'admin/base.html' %}

{% load i18n %}

{% block title %}
    {% if subtitle %}
        {{ subtitle }} |
    {% endif %}
    {{ title }} | {{ site_title|default:_('Django site admin') }}
{% endblock %}

{% block branding %}
    {% include "unfold/helpers/site_branding.html" %}
{% endblock %}

{% block content %}
    Start creating your own components here
{% endblock %}
```

### 2. Configure template directory

```python
# settings.py

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],  # Add this
        # ...
    }
]
```

### 3. Dashboard Callback

Pass custom variables to the dashboard template:

```python
# views.py

def dashboard_callback(request, context):
    context.update({
        "custom_variable": "value",
        "cards": [
            {"title": "Revenue", "metric": "$12,345"},
            {"title": "Users", "metric": "1,234"},
        ],
    })
    return context
```

```python
# settings.py

UNFOLD = {
    "DASHBOARD_CALLBACK": "app.views.dashboard_callback",
}
```

### 4. Using Components in Dashboard

```html
{% extends 'admin/base.html' %}
{% load i18n unfold %}

{% block content %}
    {% component "unfold/components/container.html" %}
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
            {% for card in cards %}
                {% component "unfold/components/card.html" %}
                    {% component "unfold/components/text.html" %}
                        {{ card.title }}
                    {% endcomponent %}
                    {% component "unfold/components/title.html" %}
                        {{ card.metric }}
                    {% endcomponent %}
                {% endcomponent %}
            {% endfor %}
        </div>

        {% component "unfold/components/card.html" with title="Revenue Chart" %}
            {% component "unfold/components/chart/line.html" with data=chart_data %}
            {% endcomponent %}
        {% endcomponent %}
    {% endcomponent %}
{% endblock %}
```

## Important Notes
- Custom CSS classes in the dashboard template are NOT automatically compiled
- For custom styling, either configure Tailwind CSS or write custom CSS
- Load custom styles via `UNFOLD["STYLES"]` setting
""",
    },
    "pages": {
        "title": "Custom Admin Pages",
        "content": """# Django Unfold - Custom Pages

## Creating Custom Pages

Use `UnfoldModelAdminViewMixin` for custom class-based views:

```python
# admin.py

from django.urls import path
from django.views.generic import TemplateView

from unfold.admin import ModelAdmin
from unfold.views import UnfoldModelAdminViewMixin

from .models import MyModel


class MyClassBasedView(UnfoldModelAdminViewMixin, TemplateView):
    title = "Custom Title"           # Required: page header title
    permission_required = ()         # Required: tuple of permissions
    template_name = "some/template/path.html"


@admin.register(MyModel)
class CustomAdmin(ModelAdmin):
    def get_urls(self):
        # IMPORTANT: model_admin parameter is required
        custom_view = self.admin_site.admin_view(
            MyClassBasedView.as_view(model_admin=self)
        )

        return super().get_urls() + [
            path("custom-url-path", custom_view, name="custom_name"),
        ]
```

## Template

Extend from `admin/base.html` for full Unfold UI (header, sidebar, menu):

```html
{% extends "admin/base.html" %}

{% load admin_urls i18n unfold %}

{% block content %}
    {% tab_list "model_name" %}

    {% trans "Custom page content" %}
{% endblock %}
```

## Important Notes
- Custom views are NOT automatically added to sidebar navigation
- You must manually add them to `UNFOLD["SIDEBAR"]["navigation"]` in settings
- The `model_admin=self` parameter is **required** when creating the view
- `permission_required` must be defined even if empty `()`
- `title` is required for page header display
""",
    },
    "styles_scripts": {
        "title": "Custom Styles, Scripts & Tailwind CSS",
        "content": """# Django Unfold - Custom Styles & Scripts

## Loading Custom Styles and Scripts

```python
# settings.py

from django.templatetags.static import static

UNFOLD = {
    "STYLES": [
        lambda request: static("css/style.css"),
    ],
    "SCRIPTS": [
        lambda request: static("js/script.js"),
    ],
}
```

## Tailwind 4.x (Unfold 0.57+)

### Setup
```bash
npm i tailwindcss @tailwindcss/cli
```

### Create styles.css
```css
/* styles.css */
@import 'tailwindcss';
```

### Compile
```bash
npx @tailwindcss/cli -i styles.css -o your_project/static/css/styles.css --minify
```

### Load in settings
```python
UNFOLD = {
    "STYLES": [
        lambda request: static("css/styles.css"),
    ],
}
```

## Tailwind 3.x (Unfold below 0.56)

### Install
```bash
npm install tailwindcss
```

### tailwind.config.js
```javascript
module.exports = {
    darkMode: "class",
    content: ["./your_project/**/*.{html,py,js}"],
    theme: {
        extend: {
            colors: {
                base: {
                    50: "rgb(var(--color-base-50) / <alpha-value>)",
                    100: "rgb(var(--color-base-100) / <alpha-value>)",
                    // ... 200-950
                },
                primary: {
                    50: "rgb(var(--color-primary-50) / <alpha-value>)",
                    100: "rgb(var(--color-primary-100) / <alpha-value>)",
                    // ... 200-950
                },
                font: {
                    "subtle-light": "rgb(var(--color-font-subtle-light) / <alpha-value>)",
                    "subtle-dark": "rgb(var(--color-font-subtle-dark) / <alpha-value>)",
                    "default-light": "rgb(var(--color-font-default-light) / <alpha-value>)",
                    "default-dark": "rgb(var(--color-font-default-dark) / <alpha-value>)",
                    "important-light": "rgb(var(--color-font-important-light) / <alpha-value>)",
                    "important-dark": "rgb(var(--color-font-important-dark) / <alpha-value>)",
                }
            }
        }
    }
};
```

### styles.css
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

### Compile
```bash
npx tailwindcss -i styles.css -o your_project/static/css/styles.css --minify
# Watch mode:
npx tailwindcss -i styles.css -o your_project/static/css/styles.css --minify --watch
```

### package.json scripts
```json
{
    "scripts": {
        "tailwind:watch": "npx tailwindcss -i styles.css -o your_project/static/css/styles.css --minify --watch",
        "tailwind:build": "npx tailwindcss -i styles.css -o your_project/static/css/styles.css --minify"
    }
}
```

## Recommendation
For Unfold 0.56+, prefer writing custom CSS directly rather than setting up Tailwind. This avoids conflicts with Unfold's built-in Tailwind configuration.
""",
    },
    "integrations_import_export": {
        "title": "Integration: django-import-export",
        "content": """# Django Unfold - django-import-export Integration

## Setup

### 1. Add to INSTALLED_APPS
```python
# settings.py

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.import_export",
    # ...
    "import_export",
]
```

### 2. Configure ModelAdmin

```python
# admin.py

from unfold.admin import ModelAdmin
from import_export.admin import ImportExportModelAdmin
from unfold.contrib.import_export.forms import (
    ExportForm,
    ImportForm,
    SelectableFieldsExportForm,  # Alternative: lets users select export fields
)


class ExampleAdmin(ModelAdmin, ImportExportModelAdmin):
    import_form_class = ImportForm
    export_form_class = ExportForm
    # Or for selectable fields:
    # export_form_class = SelectableFieldsExportForm
```

### 3. Export Action (django-import-export < 4.x)

```python
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.admin import ExportActionModelAdmin

# Not needed in django-import-export 4.x+
class ExampleAdmin(ModelAdmin, ExportActionModelAdmin):
    pass
```

**Note**: `ExportActionModelAdmin` was removed in django-import-export 4.x as styling issues were fixed upstream.
""",
    },
    "integrations_guardian": {
        "title": "Integration: django-guardian",
        "content": """# Django Unfold - django-guardian Integration

## Setup

```python
# settings.py

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.guardian",
    # ...
    "guardian",
]
```

After setup, an "Object permissions" button appears on change form detail pages.

Official docs: https://django-guardian.readthedocs.io/en/stable/installation/
""",
    },
    "integrations_simple_history": {
        "title": "Integration: django-simple-history",
        "content": """# Django Unfold - django-simple-history Integration

## Setup

```python
# settings.py

INSTALLED_APPS = [
    "unfold",
    # ...
    "unfold.contrib.simple_history",
    # ...
    "simple_history",
]
```

**Important**: `unfold.contrib.simple_history` must be AFTER `unfold` but BEFORE `simple_history`.

## Admin Configuration

```python
# admin.py

from django.contrib import admin
from django.contrib.auth import get_user_model
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin

User = get_user_model()

@admin.register(User)
class UserAdmin(SimpleHistoryAdmin, ModelAdmin):
    pass
```

Inherit from both `SimpleHistoryAdmin` and `unfold.admin.ModelAdmin`.
""",
    },
    "integrations_celery_beat": {
        "title": "Integration: django-celery-beat",
        "content": """# Django Unfold - django-celery-beat Integration

The default changelist templates in django-celery-beat use `django.contrib.admin.ModelAdmin`, causing design discrepancies. Override them:

```python
# admin.py

from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.widgets import UnfoldAdminSelectWidget, UnfoldAdminTextInputWidget

from django_celery_beat.models import (
    ClockedSchedule,
    CrontabSchedule,
    IntervalSchedule,
    PeriodicTask,
    SolarSchedule,
)
from django_celery_beat.admin import (
    ClockedScheduleAdmin as BaseClockedScheduleAdmin,
    CrontabScheduleAdmin as BaseCrontabScheduleAdmin,
    PeriodicTaskAdmin as BasePeriodicTaskAdmin,
    PeriodicTaskForm,
    TaskSelectWidget,
)

admin.site.unregister(PeriodicTask)
admin.site.unregister(IntervalSchedule)
admin.site.unregister(CrontabSchedule)
admin.site.unregister(SolarSchedule)
admin.site.unregister(ClockedSchedule)


class UnfoldTaskSelectWidget(UnfoldAdminSelectWidget, TaskSelectWidget):
    pass


class UnfoldPeriodicTaskForm(PeriodicTaskForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["task"].widget = UnfoldAdminTextInputWidget()
        self.fields["regtask"].widget = UnfoldTaskSelectWidget()


@admin.register(PeriodicTask)
class PeriodicTaskAdmin(BasePeriodicTaskAdmin, ModelAdmin):
    form = UnfoldPeriodicTaskForm


@admin.register(IntervalSchedule)
class IntervalScheduleAdmin(ModelAdmin):
    pass


@admin.register(CrontabSchedule)
class CrontabScheduleAdmin(BaseCrontabScheduleAdmin, ModelAdmin):
    pass


@admin.register(SolarSchedule)
class SolarScheduleAdmin(ModelAdmin):
    pass


@admin.register(ClockedSchedule)
class ClockedScheduleAdmin(BaseClockedScheduleAdmin, ModelAdmin):
    pass
```
""",
    },
    "integrations_modeltranslation": {
        "title": "Integration: django-modeltranslation",
        "content": """# Django Unfold - django-modeltranslation Integration

## Admin Configuration

```python
# admin.py

from django.contrib import admin
from modeltranslation.admin import TabbedTranslationAdmin
from unfold.admin import ModelAdmin
from .models import MyModel


@admin.register(MyModel)
class MyModelAdmin(ModelAdmin, TabbedTranslationAdmin):
    pass
```

## Language Flags

```python
# settings.py

UNFOLD = {
    "EXTENSIONS": {
        "modeltranslation": {
            "flags": {
                "en": "🇬🇧",
                "fr": "🇫🇷",
                "nl": "🇧🇪",
            },
        },
    },
}
```

Flags appear as suffix in each field's label, helping distinguish language versions.
""",
    },
    "integrations_money": {
        "title": "Integration: django-money",
        "content": """# Django Unfold - django-money Integration

Django-money is fully supported out of the box. No additional `INSTALLED_APPS` entries needed.

Unfold auto-detects MoneyField and applies `UnfoldAdminMoneyWidget` from `unfold.widgets`.

The widget handles both amount input and currency selection dropdown.

Official docs: https://django-money.readthedocs.io/en/latest/
""",
    },
    "integrations_constance": {
        "title": "Integration: django-constance",
        "content": """# Django Unfold - django-constance Integration

## Setup

```python
# settings.py

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.constance",
    # ...
    "constance",
]
```

**Important**: `unfold.contrib.constance` must be BEFORE `constance`.

## Configuration

```python
# settings.py

from unfold.contrib.constance.settings import UNFOLD_CONSTANCE_ADDITIONAL_FIELDS

CONSTANCE_ADDITIONAL_FIELDS = {
    **UNFOLD_CONSTANCE_ADDITIONAL_FIELDS,

    # Custom field example
    "choice_field": [
        "django.forms.fields.ChoiceField",
        {
            "widget": "unfold.widgets.UnfoldAdminSelectWidget",
            "choices": (
                ("light-blue", "Light blue"),
                ("dark-blue", "Dark blue"),
            ),
        },
    ],
}
```

`UNFOLD_CONSTANCE_ADDITIONAL_FIELDS` provides extra field types like `image_field` and `file_field`.
""",
    },
    "integrations_location_field": {
        "title": "Integration: django-location-field",
        "content": """# Django Unfold - django-location-field Integration

## Setup

```python
# settings.py

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.location_field",
    # ...
    "location_field",
]
```

**Important**: `unfold.contrib.location_field` must be BEFORE `location_field`.

## Admin Configuration

```python
# admin.py

from django.contrib import admin
from django import forms
from unfold.admin import ModelAdmin
from unfold.contrib.location_field.widgets import UnfoldAdminLocationWidget

class ExampleModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["location"].widget = UnfoldAdminLocationWidget(
            # base_fields=["city"],
            # zoom=7,
        )

@admin.register(ExampleModel)
class ExampleModelAdmin(ModelAdmin):
    form = ExampleModelForm
```
""",
    },
    "integrations_djangoql": {
        "title": "Integration: djangoql",
        "content": """# Django Unfold - djangoql Integration

No additional configuration needed. Unfold automatically styles djangoql's:
- Search input
- Toggle checkbox
- Dropdown components

Custom djangoql pages (like documentation) are NOT styled by Unfold.
Unfold removes the "help" link to djangoql's documentation page via CSS.
""",
    },
    "integrations_json_widget": {
        "title": "Integration: django-json-widget",
        "content": """# Django Unfold - django-json-widget Integration

Follow the official installation: https://pypi.org/project/django-json-widget/

No additional configuration needed. Unfold automatically applies:
- Custom CSS overrides for the widget
- Dark mode support
- Consistent admin appearance

Both `unfold` and `django-json-widget` in INSTALLED_APPS is sufficient.
""",
    },
    "features_overview": {
        "title": "Features Overview",
        "content": """# Django Unfold - Complete Features Overview

## Core Features
- **Visual interface**: Modern UI based on Tailwind CSS
- **Sidebar navigation**: Icons, collapsible sections, badges, permissions
- **Dark mode**: Light and dark themes with switcher
- **Flexible actions**: Global, row, detail, and submit line actions
- **Advanced filters**: Dropdowns, autocomplete, numeric, datetime, text filters
- **Dashboard tools**: Custom dashboard with components
- **UI components**: Cards, buttons, charts, tables, progress bars, etc.
- **WYSIWYG editor**: Built-in Trix editor support
- **Array widget**: PostgreSQL ArrayField support
- **Inline tabs**: Group inlines into tab navigation
- **Conditional fields**: Show/hide fields dynamically
- **Model tabs**: Custom tab navigation for models
- **Fieldset tabs**: Merge fieldsets into tabs
- **Sortable inlines**: Drag-and-drop sorting
- **Command palette**: Quick search across models
- **Datasets**: Custom changelists on change form detail pages
- **Environment label**: Distinguish environments
- **Nonrelated inlines**: Display unrelated models as inlines
- **Paginated inlines**: Break large record sets into pages
- **Favicons**: Built-in favicon configuration
- **Theming**: Custom colors, border radius, backgrounds
- **Font colors**: Adjustable font colors
- **Changeform modes**: Compressed field display
- **Language switcher**: Change language from admin
- **Infinite paginator**: Efficient large dataset handling
- **Parallel admin**: Run default admin alongside Unfold
- **Crispy forms**: Custom template pack for django-crispy-forms

## Third-party Package Support
- django-guardian (object-level permissions)
- django-import-export (data import/export)
- django-simple-history (model history tracking)
- django-constance (dynamic settings)
- django-celery-beat (periodic task scheduling)
- django-modeltranslation (multilingual models)
- django-money (monetary values)
- django-location-field (geographic points)
- djangoql (advanced search)
- django-json-widget (JSON editing)

## Technology Stack
- Tailwind CSS (styling)
- Material Symbols (icons) - https://fonts.google.com/icons
- Inter (font)
- Chart.js (charts)
- Alpine.js (JavaScript framework)
- HTMX (AJAX calls)
- Trix (WYSIWYG editor)
""",
    },
    "complete_example": {
        "title": "Complete Integration Example",
        "content": """# Django Unfold - Complete Integration Example

## Project Structure
```
myproject/
├── manage.py
├── myproject/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── myapp/
│   ├── admin.py
│   ├── models.py
│   └── views.py
└── templates/
    └── admin/
        └── index.html
```

## settings.py
```python
from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.inlines",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "myapp",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

UNFOLD = {
    "SITE_TITLE": "My Application",
    "SITE_HEADER": "My App Admin",
    "SITE_SYMBOL": "speed",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "ENVIRONMENT": "myapp.views.environment_callback",
    "DASHBOARD_CALLBACK": "myapp.views.dashboard_callback",
    "COLORS": {
        "primary": {
            "50": "oklch(97.7% .014 308.299)",
            "100": "oklch(94.6% .033 307.174)",
            "200": "oklch(90.2% .063 306.703)",
            "300": "oklch(82.7% .119 306.383)",
            "400": "oklch(71.4% .203 305.504)",
            "500": "oklch(62.7% .265 303.9)",
            "600": "oklch(55.8% .288 302.321)",
            "700": "oklch(49.6% .265 301.924)",
            "800": "oklch(43.8% .218 303.724)",
            "900": "oklch(38.1% .176 304.987)",
            "950": "oklch(29.1% .149 302.717)",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "navigation": [
            {
                "title": _("Main"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Dashboard"),
                        "icon": "dashboard",
                        "link": reverse_lazy("admin:index"),
                    },
                    {
                        "title": _("Products"),
                        "icon": "inventory_2",
                        "link": reverse_lazy("admin:myapp_product_changelist"),
                    },
                    {
                        "title": _("Orders"),
                        "icon": "shopping_cart",
                        "link": reverse_lazy("admin:myapp_order_changelist"),
                        "badge": "myapp.views.orders_badge",
                        "badge_variant": "danger",
                    },
                ],
            },
            {
                "title": _("Settings"),
                "separator": True,
                "items": [
                    {
                        "title": _("Users"),
                        "icon": "people",
                        "link": reverse_lazy("admin:auth_user_changelist"),
                        "permission": lambda request: request.user.is_superuser,
                    },
                ],
            },
        ],
    },
}
```

## models.py
```python
from django.db import models
from django.utils.translation import gettext_lazy as _


class Category(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Product(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        DRAFT = "draft", _("Draft")
        ARCHIVED = "archived", _("Archived")

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
```

## admin.py
```python
from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.filters.admin import RangeDateFilter, DropdownFilter
from unfold.decorators import action, display
from unfold.enums import ActionVariant

from .models import Category, Product


class ProductInline(TabularInline):
    model = Product
    extra = 0


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ["name"]
    inlines = [ProductInline]


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ["name", "display_category", "display_price", "display_status", "created_at"]
    list_filter = [
        ("category", DropdownFilter),
        ("status", DropdownFilter),
        ("created_at", RangeDateFilter),
    ]
    list_filter_submit = True
    search_fields = ["name", "description"]
    actions_list = ["mark_active"]

    @display(
        description=_("Category"),
        ordering="category__name",
    )
    def display_category(self, obj):
        return obj.category.name

    @display(
        description=_("Price"),
        ordering="price",
    )
    def display_price(self, obj):
        return f"${obj.price:,.2f}"

    @display(
        description=_("Status"),
        ordering="status",
        label={
            Product.Status.ACTIVE: "success",
            Product.Status.DRAFT: "info",
            Product.Status.ARCHIVED: "warning",
        },
    )
    def display_status(self, obj):
        return obj.status

    @action(
        description=_("Mark as Active"),
        icon="check_circle",
        variant=ActionVariant.SUCCESS,
    )
    def mark_active(self, request: HttpRequest, queryset: QuerySet):
        queryset.update(status=Product.Status.ACTIVE)
```

## views.py
```python
def dashboard_callback(request, context):
    context.update({
        "cards": [
            {"title": "Total Products", "metric": "150"},
            {"title": "Active Products", "metric": "120"},
            {"title": "Total Orders", "metric": "45"},
        ],
    })
    return context


def environment_callback(request):
    return ["Development", "warning"]


def orders_badge(request):
    return 5
```

## templates/admin/index.html
```html
{% extends 'admin/base.html' %}
{% load i18n unfold %}

{% block title %}
    {{ title }} | {{ site_title|default:_('Django site admin') }}
{% endblock %}

{% block branding %}
    {% include "unfold/helpers/site_branding.html" %}
{% endblock %}

{% block content %}
    {% component "unfold/components/container.html" %}
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
            {% for card in cards %}
                {% component "unfold/components/card.html" %}
                    {% component "unfold/components/text.html" %}
                        {{ card.title }}
                    {% endcomponent %}
                    {% component "unfold/components/title.html" %}
                        {{ card.metric }}
                    {% endcomponent %}
                {% endcomponent %}
            {% endfor %}
        </div>
    {% endcomponent %}
{% endblock %}
```
""",
    },
}

# Build a flat list of all section keys for search
ALL_SECTIONS = list(DOCS.keys())
