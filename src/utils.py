
def check_types(value, allowed_types):
    if value:
        if not isinstance(value, allowed_types):
            allowed_types_text = allowed_types
            if isinstance(allowed_types, (list, set, tuple)):
                allowed_types_text = ", ".join([str(allowed_type.__name__) for allowed_type in allowed_types])
            else:
                allowed_types_text = str(allowed_types)
            raise Exception(f'{value} has type: {value.__class__.__name__}. Allowed only: {allowed_types_text}')
