import json
from functools import reduce
from operator import or_, and_
from django.contrib.auth import get_user_model
from django.db import connection
from django.db import models
from django.db.models import Q
from django.db.models.deletion import CASCADE
from django.db.models.sql.query import Query
from ordered_model.models import OrderedModel
from . import shunting_yard
from .model_helpers import get_model
from .utils import (
    previous,
    str_as_date,
    str_as_date_range, to_int,
)

User = get_user_model()


class DynamicFilterExpr(models.Model):
    class Meta:
        verbose_name = 'Filter'
        verbose_name_plural = 'Filters'

    name = models.CharField(max_length=128, default='Report')
    model = models.CharField(max_length=64, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    is_global = models.BooleanField('Global?', default=False, db_index=True, help_text='Make filter accessible to all.')

    def __str__(self):
        return self.name

    # Make implicit operators explicit, to ensure the ops stack is never empty.
    def normalized_terms(self):
        nterms = []

        for prev, item in previous(self.dynamicfilterterm_set.all()):
            if prev:
                # Add implicit ANDs.
                if prev.op in ('-', '!', ')') and item.op in ('-', '!', '('):
                    nterms.append(DynamicFilterTerm(op='&'))

                # Add no-ops.
                elif prev.op in ('(', '&', '|') and item.op in (')', '&', '|'):
                    nterms.append(DynamicFilterTerm(op=' '))

            nterms.append(item)

        if not nterms:
            # Add no-op to avoid an empty filter.
            nterms.append(DynamicFilterTerm(op=' '))

        return nterms

    def as_q(self):
        try:
            terms = self.normalized_terms()
            return shunting_yard.evaluate(terms)
        except Exception as e:
            return f"error: {e}"

    def as_sql(self):
        try:
            model_obj = get_model(self.model)
            query = Query(model_obj)

            where = self.as_q().resolve_expression(query)

            compiler = query.get_compiler(using='default')
            query_str, args = where.as_sql(compiler, connection)

            return query_str % tuple(args)
        except Exception as e:
            return f"error: {e}"


class DynamicFilterTerm(OrderedModel):
    order_with_respect_to = "filter"

    OP_CHOICES = [
        ('-', '-'),
        ('!', 'NOT'),
        ('&', 'AND'),
        ('|', 'OR'),
        ('(', '('),
        (')', ')'),
    ]

    LOOKUP_CHOICES = [
        ('-', '---------'),
        ('=', 'Equals'),
        ('icontains', 'Contains'),
        ('icontains_one_of', 'Contains one of'),
        ('icontains_all_of', 'Contains all of'),
        ('istartswith', 'Starts with'),
        ('iendswith', 'Ends with'),
        ('in', 'One of'),
        ('-', '---------'),
        ('range', 'Date Range'),
        ('year', 'Date Year'),
        ('month', 'Date Month'),
        ('day', 'Date Day'),
        ('-', '---------'),
        ('isnull', 'Is NULL'),
        ('isnotnull', 'Is not NULL'),
        ('istrue', 'Is TRUE'),
        ('isfalse', 'Is FALSE'),
        ('-', '---------'),
        ('lt', 'Less Than'),
        ('gt', 'Greater Than'),
        ('lte', 'Less Than or Equal To'),
        ('gte', 'Greater Than or Equal To'),
        ('-', '---- JSONField ----'),
        ('has_key', 'Has key'),
        ('contains_json', 'Contains JSON'),

    ]

    class Meta:
        ordering = ('order',)
        verbose_name = 'Field'
        verbose_name_plural = 'Fields'

    filter = models.ForeignKey(DynamicFilterExpr, on_delete=CASCADE)
    op = models.CharField(max_length=1, choices=OP_CHOICES, default='-')
    field = models.CharField(max_length=64, blank=True, null=True)
    lookup = models.CharField(max_length=16, choices=LOOKUP_CHOICES, default='-')
    value = models.CharField(max_length=100, blank=True, null=True)
    bilateral = models.BooleanField(default=False)

    @property
    def fields(self):
        if self.field:
            return self.field.split('|')

    def __str__(self):
        try:
            if not self.field:
                return "-"

            def get_operator():
                if self.op == '!':
                    return '!='
                return '=='

            if self.op in ('-', '!'):
                expr = ' OR '.join([
                    f'{self.get_keypath(field)} {get_operator()} {self.get_value()}'
                    for field in self.fields
                ])

                if self.op == '!':
                    f'NOT({expr})'

                return expr

            return self.op
        except Exception as e:
            return f"Error: {e}"

    def clean(self):
        if self.op in ('&', '|', '(', ')'):
            # Clear irrelevant fields for these operators
            self.field = '-'
            self.lookup = '-'
            self.value = None

        elif self.op in ('-', '!'):
            # Clear irrelevant fields for these operators
            if self.lookup in ('isnull', 'isnotnull', 'istrue', 'isfalse'):
                self.value = None

    def get_keypath(self, field):
        if self.lookup in ('=', 'istrue', 'isfalse'):
            return field
        if self.lookup in ('isnull', 'isnotnull'):
            return f'{field}__isnull'
        if self.lookup in ["icontains_one_of", "icontains_all_of"]:
            return f'{field}__icontains'
        if self.lookup == "contains_json":
            return f'{field}__contains'
        return f'{field}__{self.lookup}'

    def get_value(self):
        if self.lookup == "contains_json":
            return json.loads(self.value)
        if self.lookup in ('isnull', 'istrue'):
            return True

        if self.lookup in ('isnotnull', 'isfalse'):
            return False

        if self.lookup in ['in', 'icontains_one_of', 'icontains_all_of']:
            return self.value.split(',') if self.value else []

        if self.lookup == 'range':
            return str_as_date_range(self.value)

        if 'date' in self.field:
            return str_as_date(self.value)

        return self.value

    def get_term(self, field):
        return {self.get_keypath(field): self.get_value()}

    def as_q(self):
        try:
            if self.lookup in ["icontains_one_of", "icontains_all_of"]:
                q = Q()
                op_ = or_
                if self.lookup in "icontains_all_of":
                    op_ = and_
                for field in self.fields:
                    q |= reduce(op_, [
                        Q(**{self.get_keypath(field): x}) for x in self.get_value()
                    ])
            else:
                q = reduce(or_, [
                    Q(**self.get_term(field))
                    for field in self.fields
                ])

            if self.op == '!':
                return ~q

            return q
        except:
            pass


class DynamicFilterColumn(models.Model):
    class Meta:
        ordering = ('order',)
        verbose_name = 'Column'
        verbose_name_plural = 'Columns'

    filter = models.ForeignKey(DynamicFilterExpr, on_delete=CASCADE)
    field = models.CharField(max_length=64, blank=True, null=True)
    order = models.PositiveSmallIntegerField()

    def __str__(self):
        return self.field


class DynamicFilterColumnSortOrder(models.Model):
    class Meta:
        ordering = ('order',)
        verbose_name = 'Column sort order'
        verbose_name_plural = 'Column sort orders'

    filter = models.ForeignKey(DynamicFilterExpr, on_delete=CASCADE)
    field = models.CharField(max_length=64, blank=True, null=True)
    order = models.PositiveSmallIntegerField()

    def __str__(self):
        return self.field
