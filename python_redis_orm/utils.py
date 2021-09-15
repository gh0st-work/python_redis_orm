def check_types(value, allowed_types):
    if value:
        if not isinstance(value, allowed_types):
            allowed_types_text = allowed_types
            if isinstance(allowed_types, (list, set, tuple)):
                allowed_types_text = ", ".join([str(allowed_type.__name__) for allowed_type in allowed_types])
            else:
                allowed_types_text = str(allowed_types)
            raise Exception(f'{value} has type: {value.__class__.__name__}. Allowed only: {allowed_types_text}')


def check_classes(value, allowed_classes):
    if value:
        if not issubclass(value, allowed_classes):
            allowed_types_text = allowed_classes
            if isinstance(allowed_classes, (list, set, tuple)):
                allowed_types_text = ", ".join([str(allowed_class.__name__) for allowed_class in allowed_classes])
            else:
                allowed_types_text = str(allowed_classes)
            raise Exception(f'{value} class is: {value.__class__.__name__}. Allowed subclasses: {allowed_types_text}')


def get_ids_from_untyped_data(instances):
    if type(instances) == dict:
        if 'id' in instances.keys():
            ids = [instances['id']]
        else:
            if all([
                (type(instance_key) == int)
                for instance_key in instances.keys()
            ]):
                ids = list(set(instances.keys()))
            else:
                raise Exception('Not all keys are of the type int')
    elif type(instances) in [list, tuple, set]:
        if all([
            (type(instance_id) == int)
            for instance_id in instances
        ]):
            ids = list(set(instances))
        else:
            try:
                if all([
                    (type(instance_dict['id']) == int)
                    for instance_dict in instances
                ]):
                    ids = [
                        instance_dict['id']
                        for instance_dict in instances
                    ]
                else:
                    raise Exception('Not all elements are of the type int')
            except:
                raise Exception('Not all elements are of the type int')
    elif type(instances) == int:
        ids = [instances]
    else:
        raise Exception(f"Can't get ids from {instances}")
    return ids


def check_callable(value):
    try:
        result_value = value()
    except:
        result_value = value
    return result_value
