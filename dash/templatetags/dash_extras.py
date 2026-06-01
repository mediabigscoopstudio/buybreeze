from django import template

register = template.Library()


@register.filter(name='str_replace')
def str_replace(value, arg):
    """Replace a substring. Usage: {{ value|str_replace:"old:new" }}"""
    try:
        old, new = arg.split(':', 1)
        return str(value).replace(old, new)
    except (ValueError, AttributeError):
        return value
