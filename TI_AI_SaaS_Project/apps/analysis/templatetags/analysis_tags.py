"""
Custom template tags for AI Analysis templates
"""

from django import template
from django.http import QueryDict

register = template.Library()


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    """
    Construct a URL-encoded query string based on the current request's GET parameters, applying the provided overrides.
    
    If the template context does not contain a `request`, an empty string is returned. For each keyword argument:
    - if the value is `None` or an empty string, the parameter is removed from the resulting query string;
    - otherwise the parameter is set or updated to the provided value.
    
    Parameters:
        context: Template context containing the current `request`.
        **kwargs: Key-value pairs to set, update, or remove in the query string.
    
    Returns:
        str: URL-encoded query string without a leading '?'.
    """
    request = context.get('request')
    if not request:
        return ''
    
    # Get current GET parameters
    query_dict = request.GET.copy()
    
    # Update with provided kwargs
    for key, value in kwargs.items():
        if value is None or value == '':
            # Remove parameter if value is None or empty
            query_dict.pop(key, None)
        else:
            query_dict[key] = value
    
    return query_dict.urlencode()
