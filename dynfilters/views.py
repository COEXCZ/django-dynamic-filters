from django.contrib import messages
from .model_helpers import get_model
from .models import DynamicFilterExpr
from .url_helpers import (
    redirect_to_referer,
    redirect_to_change,
)


def dynfilters_add(request, model_name):
    try:
        model_obj = get_model(model_name)
    except:
        messages.error(request, 'This type of model is unknown.')
        return redirect_to_referer(request)

    expr = DynamicFilterExpr.objects.create(
        model=model_name,
        user=request.user,
    )

    return redirect_to_change(request, expr.id, follow=True)


def dynfilters_change(request, expr_id):
    return redirect_to_change(request, expr_id, follow=True)


def dynfilters_delete(request, expr_id):
    try:
        expr = DynamicFilterExpr.objects.get(pk=expr_id)
    except DynamicFilterExpr.DoesNotExist:
        messages.error(request, 'This filter does not exist.')
        return redirect_to_referer(request)
    expr.delete()
    messages.success(request, f"Filter '{expr.name}' deleted.")
    return redirect_to_referer(request)
