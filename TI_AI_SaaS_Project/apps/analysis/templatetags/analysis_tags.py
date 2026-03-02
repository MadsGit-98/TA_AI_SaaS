"""
Custom template tags for AI Analysis templates
"""

from django import template
from django.http import QueryDict

register = template.Library()


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    """
    Build a URL query string from the current request's GET parameters,
    updated with any provided keyword arguments.
    
    Usage:
        {% querystring page=2 %}
        {% querystring category='Best Match' %}
        {% querystring page=page_obj.next_page_number %}
    
    Args:
        context: Template context (automatically provided)
        **kwargs: Key-value pairs to update/override in the query string
    
    Returns:
        URL-encoded query string (without leading '?')
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
