from operator import itemgetter

from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet

from .model_helpers import get_model
from .models import DynamicFilterExpr, DynamicFilterTerm
from .utils import str_as_date, str_as_date_range, to_int
from django.db import models as django_models


class DynamicFilterExprForm(forms.ModelForm):
    class Meta:
        model = DynamicFilterExpr
        fields = ('name', 'is_global', )

    def save(self, commit=True, **kwargs):
        return super(DynamicFilterExprForm, self).save(commit=commit)

    save.alters_data = True


class DynamicFilterTermInlineFormSet(BaseInlineFormSet):
    def clean(self):
        parenthesis = 0

        for form in self.forms:
            op, deleted = itemgetter('op', 'DELETE')(form.cleaned_data)
            
            if deleted:
                continue # inline object was deleted by user

            if op == '(':
                parenthesis += 1
            elif op == ')':
                parenthesis -= 1

            if parenthesis < 0:
                raise ValidationError("Missing opening parenthesis")

        if parenthesis:
            raise ValidationError("Missing closing parenthesis")


class DynamicFilterTermInlineForm(forms.ModelForm):

    class Meta:
        model = DynamicFilterTerm
        fields = ('op', 'field', 'lookup', 'value', )

    def __init__(self, *args, **kwargs):
        self._clean_errors = {}
        super(DynamicFilterTermInlineForm, self).__init__(*args, **kwargs)

    @property
    def _filter_model(self):
        return get_model(self.instance.filter.model)

    def _filter_model_field_type(self, field_name):
        return type(self._filter_model._meta.get_field(field_name))

    def _clean_datetimefield(self, value, lookup, field):
        """
        DateField
        DateTimeField
        """
        if self._filter_model_field_type(field) in [django_models.DateField, django_models.DateTimeField]:
            if lookup not in ('year', 'month', 'day', 'range', 'lt', 'lte', 'gt', 'gte'):
                self._clean_errors.update({'lookup': 'Datetime field. Should be date lookup.'})
                return
            if lookup == 'range':
                try:
                    str_as_date_range(value)
                except:
                    self._clean_errors.update({'value': 'Should be "DD/MM/YYYY, DD/MM/YYYY"'})
            if lookup in ('year', 'month', 'day'):
                try:
                    float(value)
                except:
                    self._clean_errors.update({'value': 'Should be a number'})
            if lookup in ('lt', 'lte', 'gt', 'gte'):
                try:
                    str_as_date(value)
                except:
                    self._clean_errors.update({'value': 'Should be "DD/MM/YYYY".'})

    def _clean_numericfields(self, value, lookup, field):
        """
        PositiveIntegerField,
        IntegerField,
        BigIntegerField,
        SmallIntegerField
        """
        if self._filter_model_field_type(field) in [
            django_models.PositiveIntegerField,
            django_models.IntegerField,
            django_models.BigIntegerField,
            django_models.SmallIntegerField
        ]:
            if lookup not in ('lt', 'lte', 'gt', 'gte', '=', 'icontains', 'istartswith', 'iendswith', 'in'):
                self._clean_errors.update({'lookup': 'Numeric field. Should be lt, lte, gt, gte, icontains, '
                                                     'equals, starts with, ends with or one of lookup.'})
                return

            if lookup == "in":
                for v in value.split(","):
                    if to_int(v.strip()) is None:
                        self._clean_errors.update({'value': 'Numeric field. Should list of numbers.'})
                        return
                return
            int_val = to_int(value)
            if int_val is None:
                self._clean_errors.update({'value': 'Numeric field. Should be number.'})

    def _clean_relationfields(self, value, lookup, field):
        """
        """
        if self._filter_model_field_type(field) in [
            django_models.ManyToManyField,
            django_models.ForeignKey
        ]:
            if lookup not in ('=', 'in'):
                self._clean_errors.update({'lookup': 'ManyToMany field. Should be = or in, lookup.'})
                return

    def _clean_booleanfields(self, value, lookup, field):
        """
        """
        if self._filter_model_field_type(field) in [
            django_models.BooleanField,
            django_models.NullBooleanField
        ]:
            if lookup not in ('isnull', 'isnotnull', 'istrue', 'isfalse'):
                self._clean_errors.update({'lookup': 'Boolean field. Should be "True/False/Null/NotNull"'})
                return

    def clean(self):
        errors = {}

        op, field, lookup, value = itemgetter('op', 'field', 'lookup', 'value')(self.cleaned_data)

        if op in ('-', '!'):
            if field == '-':
                errors.update({'field': 'Missing value'})

            if lookup == '-':
                errors.update({'lookup': 'Missing value'})

            if not value:
                if lookup not in ('isnull', 'isnotnull', 'istrue', 'isfalse'):
                    errors.update({'value': 'Missing value'})


            field = field.split("__")[0]
            self._clean_datetimefield(value, lookup, field)
            self._clean_numericfields(value, lookup, field)
            self._clean_relationfields(value, lookup, field)
            self._clean_booleanfields(value, lookup, field)

        else:
            pass

        if self._clean_errors:
            raise ValidationError(self._clean_errors)
