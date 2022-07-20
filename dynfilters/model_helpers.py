from django.apps import apps
from django.contrib import admin


def get_model_name(opts):
    return opts.model_name.capitalize()


def get_qualified_model_name(opts):
    return f'{opts.app_label}.{opts.model_name.capitalize()}'


def get_qualified_model_names(opts):
    # The model may be a proxy, so we need to consider parents also
    names = [
        get_qualified_model_name(meta)
        for parent in opts.get_parent_list() 
        if (meta := parent._meta)
    ]

    names.append(
        get_qualified_model_name(opts)
    )

    return names


def get_model(qmodel_name):
    app_label, model_name = qmodel_name.split('.')
    return apps.get_model(app_label, model_name)


def get_model_admin(obj):
    model_obj = get_model(obj.model)
    return admin.site._registry.get(model_obj)


def get_model_choices():
    return [
        (
            get_qualified_model_name(opts),
            get_model_name(opts)
        )
        for model_obj in apps.get_models()
        if has_dynfilter(model_obj, (opts := model_obj._meta))
    ]


def has_dynfilter(model_obj, opts):
    model_admin = admin.site._registry.get(model_obj)
    return hasattr(model_admin, 'dynfilters_fields') and not opts.proxy


def get_dynfilters_fields(model_admin):
    def humanize(f):
        if f == '-':
            return ('-', '---------')

        if isinstance(f, str):
            fs = []
            for s in f.split('|'):
                f_0 = s.split("__")[0]
                f_parts_str = " > ".join(s.split("__")[1:]) if s.split("__")[1:] else ""
                f_parts_str = f" > {f_parts_str}" if f_parts_str else ""
                verbose_name = model_admin.model._meta.get_field(f_0).verbose_name
                field_type = "({})".format(getattr(type(model_admin.model._meta.get_field(f_0)), "__name__", "unknown")) \
                    if not f_parts_str else ""

                fs.append("{}{} {}".format(verbose_name.capitalize(), f_parts_str, field_type))
            return f, ' OR '.join(fs)

        return f

    fields = getattr(model_admin, 'dynfilters_fields', [])
    return [humanize(f) for f in fields]


def get_dynfilters_select_related(model_admin):
    return getattr(model_admin, 'dynfilters_select_related', [])


def get_dynfilters_prefetch_related(model_admin):
    return getattr(model_admin, 'dynfilters_prefetch_related', [])
