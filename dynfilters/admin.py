from django import forms
from django.contrib import admin
from ordered_model.admin import OrderedInlineModelAdminMixin, OrderedTabularInline

from .models import (
    DynamicFilterExpr,
    DynamicFilterTerm,
)

from .forms import (
    DynamicFilterExprForm,
    DynamicFilterTermInlineForm,
    DynamicFilterTermInlineFormSet,
)

from .model_helpers import (
    get_model_admin,
    get_model_choices,
    get_dynfilters_fields,
)

from .url_helpers import redirect_to_referer_next


class DynamicFilterInline(admin.TabularInline):
    extra = 0

    def formfield_for_dbfield(self, db_field, **kwargs):
        obj = kwargs['request'].parent_object

        if db_field.name == 'field' and obj:
            model_admin = get_model_admin(obj)
            kwargs['widget'] = forms.Select(choices=get_dynfilters_fields(model_admin))

        return super().formfield_for_dbfield(db_field, **kwargs)


class DynamicFilterTermInline(OrderedTabularInline, DynamicFilterInline):
    model = DynamicFilterTerm
    form = DynamicFilterTermInlineForm
    formset = DynamicFilterTermInlineFormSet
    verbose_name = 'Search Criteria'
    verbose_name_plural = 'Search Criterias'
    fields = ('op', 'field', 'lookup', 'value', 'move_up_down_links')
    readonly_fields = ('move_up_down_links', )


@admin.register(DynamicFilterExpr)
class DynamicFilterExprAdmin(OrderedInlineModelAdminMixin, admin.ModelAdmin):
    form = DynamicFilterExprForm
    inlines = [DynamicFilterTermInline]

    list_per_page = 50
    list_display = ('name', 'model', 'user', 'is_global')
    readonly_fields = ("model", "as_q", "as_sql")

    def save_model(self, request, obj, form, change):
        obj.user = request.user
        super().save_model(request, obj, form, change)

    def get_form(self, request, obj=None, **kwargs):
        request.parent_object = obj
        return super(DynamicFilterExprAdmin, self).get_form(request, obj, **kwargs)

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'model':
            kwargs['widget'] = forms.Select(choices=get_model_choices())

        if db_field.name == 'user':
            db_field.default = kwargs['request'].user

        return super().formfield_for_dbfield(db_field,**kwargs)

    def has_add_permission(self, request):
        return False

    def response_change(self, request, obj):
        response = super().response_change(request, obj)

        return redirect_to_referer_next(request, response)
