import asyncio
import datetime
import decimal
import json
from copy import deepcopy
from functools import reduce

import pytz
import redis

from python_redis_orm.utils import check_types, get_ids_from_untyped_data, check_callable


### FIELDS ###


class RedisField:
    
    def __init__(self, default=None, choices=None, null=True):
        default = check_callable(default)
        choices = check_callable(choices)
        null = check_callable(null)
        check_types(choices, dict)
        check_types(null, bool)
        self.default = default
        self.value = None
        self.choices = choices
        self.null = null
    
    def _get_default_value(self):
        self.value = check_callable(self.default)
        return self.value
    
    def _check_choices(self, value):
        if self.choices:
            if value not in self.choices.keys():
                raise Exception(f'{value} is not allowed. Allowed values: {", ".join(list(self.choices.keys()))}')
    
    def check_value(self):
        if self.value is None:
            self.value = self._get_default_value()
        if self.value is None:
            if self.null:
                self.value = 'null'
            else:
                raise Exception('null is not allowed')
        if self.value:
            self._check_choices(self.value)
        return self.value
    
    def clean(self):
        self.value = self.check_value()
        return self.value
    
    def deserialize_value_check_null(self, value, redis_root):
        if value == 'null':
            if not self.null:
                if redis_root.ignore_deserialization_errors:
                    print(
                        f'{datetime.datetime.now()} - {value} can not be deserialized like {self.__class__.__name__}, ignoring')
                else:
                    raise Exception(f'{value} can not be deserialized like {self.__class__.__name__}')
    
    def deserialize_value(self, value, redis_root):
        self.deserialize_value_check_null(value, redis_root)
        return value


class RedisString(RedisField):
    
    def clean(self):
        self.value = self.check_value()
        if self.value not in [None, 'null']:
            self.value = f'{self.value}'
        return super().clean()
    
    def deserialize_value(self, value, redis_root):
        self.deserialize_value_check_null(value, redis_root)
        value = super().deserialize_value(value, redis_root)
        if value not in ['null', None]:
            value = f'{value}'
        else:
            value = None
        return value


class RedisNumber(RedisField):
    
    def clean(self):
        self.value = self.check_value()
        if self.value not in [None, 'null']:
            check_types(self.value, (int, float))
        return super().clean()
    
    def deserialize_value(self, value, redis_root):
        self.deserialize_value_check_null(value, redis_root)
        if value not in ['null', None]:
            value = super().deserialize_value(value, redis_root)
            if type(value) == str:
                if '.' in value:
                    value = float(value)
                else:
                    value = int(value)
            else:
                check_types(value, (int, float))
        else:
            value = None
        return value


class RedisId(RedisNumber):
    
    def __init__(self, *args, **kwargs):
        kwargs['null'] = False
        super().__init__(*args, **kwargs)


class RedisBool(RedisNumber):
    
    def __init__(self, *args, **kwargs):
        kwargs['choices'] = {True: 'Yes', False: 'No'}
        super().__init__(*args, **kwargs)
    
    def clean(self):
        self.value = self.check_value()
        if self.value not in [None, 'null']:
            check_types(self.value, bool)
            self.value = int(self.value)
        return super().clean()
    
    def deserialize_value(self, value, redis_root):
        self.deserialize_value_check_null(value, redis_root)
        if value not in ['null', None]:
            value = super().deserialize_value(value, redis_root)
            check_types(value, int)
            value = bool(value)
        return value


class RedisDecimal(RedisString):
    
    def clean(self):
        self.value = self.check_value()
        if self.value not in [None, 'null']:
            check_types(self.value, (int, float, decimal.Decimal))
        return super().clean()
    
    def deserialize_value(self, value, redis_root):
        self.deserialize_value_check_null(value, redis_root)
        if value not in ['null', None]:
            value = super().deserialize_value(value, redis_root)
            value = decimal.Decimal(value)
        else:
            value = None
        return value


class RedisJson(RedisField):
    
    def __init__(self, json_allowed_types=(list, dict), *args, **kwargs):
        self.json_allowed_types = json_allowed_types
        super().__init__(*args, **kwargs)
    
    def set_json_allowed_types(self, allowed_types):
        self.json_allowed_types = allowed_types
        return self.json_allowed_types
    
    def clean(self):
        self.value = self.check_value()
        if self.value not in [None, 'null']:
            check_types(self.value, self.json_allowed_types)
            json_string = json.dumps(self.value)
            self.value = json_string
        return super().clean()
    
    def deserialize_value(self, value, redis_root):
        self.deserialize_value_check_null(value, redis_root)
        if value not in ['null', None]:
            value = super().deserialize_value(value, redis_root)
            check_types(value, str)
            value = json.loads(value)
            check_types(value, self.json_allowed_types)
        else:
            value = None
        return value


class RedisDict(RedisJson):
    
    def clean(self):
        self.set_json_allowed_types(dict)
        return super().clean()
    
    def deserialize_value(self, value, redis_root):
        self.set_json_allowed_types(dict)
        self.deserialize_value_check_null(value, redis_root)
        if value not in ['null', None]:
            value = super().deserialize_value(value, redis_root)
        else:
            value = None
        return value


class RedisList(RedisJson):
    
    def clean(self):
        self.set_json_allowed_types(list)
        return super().clean()
    
    def deserialize_value(self, value, redis_root):
        self.set_json_allowed_types(list)
        self.deserialize_value_check_null(value, redis_root)
        if value not in ['null', None]:
            value = super().deserialize_value(value, redis_root)
        else:
            value = None
        return value


class RedisDateTime(RedisString):
    
    def clean(self):
        self.value = self.check_value()
        if self.value not in [None, 'null']:
            check_types(self.value, datetime.datetime)
            string_datetime = self.value.replace(tzinfo=pytz.UTC).strftime('%Y.%m.%d-%H:%M:%S+%Z')
            self.value = string_datetime
        return super().clean()
    
    def deserialize_value(self, value, redis_root):
        self.deserialize_value_check_null(value, redis_root)
        if value not in ['null', None]:
            value = super().deserialize_value(value, redis_root)
            check_types(value, str)
            value = datetime.datetime.strptime(value, '%Y.%m.%d-%H:%M:%S+%Z').replace(tzinfo=pytz.UTC)
        else:
            value = None
        return value


class RedisDate(RedisString):
    
    def clean(self):
        self.value = self.check_value()
        if self.value not in [None, 'null']:
            check_types(self.value, datetime.date)
            string_date = self.value.strftime('%Y.%m.%d+%Z')
            self.value = string_date
        return super().clean()
    
    def deserialize_value(self, value, redis_root):
        self.deserialize_value_check_null(value, redis_root)
        if value not in ['null', None]:
            value = super().deserialize_value(value, redis_root)
            check_types(value, str)
            value = datetime.datetime.strptime(value, '%Y.%m.%d+%Z').date()
        else:
            value = None
        return value


class RedisForeignKey(RedisNumber):
    
    def __init__(self, model=None, *args, **kwargs):
        model = check_callable(model)
        if args:
            args = list(map(check_callable, *args))
        allowed = True
        if model is None:
            allowed = False
        elif not issubclass(model, RedisModel):
            allowed = False
        if not allowed:
            raise Exception(f'{model.__name__} class is not RedisModel')
        else:
            self.model = model
            super().__init__(*args, **kwargs)
    
    def _get_id_from_instance_dict(self):
        if self.value:
            if type(self.value) == dict:
                if 'id' in self.value.keys():
                    self.value = self.value['id']
                else:
                    raise Exception(
                        f"{self.value} has no key 'id', please provide serialized instance or dict like " + "{'id': 1, ...}")
            else:
                raise Exception(
                    f'{self.value} type is not dict, please provide serialized instance or dict like ' + "{'id': 1, ...}")
        return self.value
    
    def clean(self):
        self.value = self.check_value()
        if self.value not in [None, 'null']:
            self.value = get_ids_from_untyped_data(self.value)[0]
        return super().clean()
    
    def deserialize_value(self, value, redis_root):
        self.deserialize_value_check_null(value, redis_root)
        if value not in ['null', None]:
            value = super().deserialize_value(value, redis_root)
            check_types(value, int)
            instance_id = value
            instance_qs = redis_root.get(self.model, return_dict=True, id=instance_id)
            if instance_id in instance_qs.keys():
                value = instance_qs[instance_id]
            else:
                value = {'id': value}
        else:
            value = None
        return value


class RedisManyToMany(RedisList):
    
    def __init__(self, model=None, *args, **kwargs):
        model = check_callable(model)
        if args:
            args = list(map(check_callable, *args))
        allowed = True
        if model is None:
            allowed = False
        elif not issubclass(model, RedisModel):
            allowed = False
        if not allowed:
            raise Exception(f'{model.__name__} class is not RedisModel')
        else:
            self.model = model
            super().__init__(*args, **kwargs)
    
    def clean(self):
        self.value = self.check_value()
        if self.value not in [None, 'null']:
            self.value = get_ids_from_untyped_data(self.value)
        return super().clean()
    
    def deserialize_value(self, value, redis_root):
        self.deserialize_value_check_null(value, redis_root)
        if value not in ['null', None]:
            value = super().deserialize_value(value, redis_root)
            instances_ids = value
            instances = redis_root.get(self.model, id__in=instances_ids)
            value = instances
        
        return value


### REDIS ROOT ###


class RedisRoot:
    
    ### INIT ###
    
    def __init__(
        self,
        connection_pool=None,
        prefix='redis_test',
        ignore_deserialization_errors=True,
        save_consistency=False,
        use_keys=True,
        solo_usage=True,
    ):
        connection_pool = check_callable(connection_pool)
        prefix = check_callable(prefix)
        ignore_deserialization_errors = check_callable(ignore_deserialization_errors)
        save_consistency = check_callable(save_consistency)
        use_keys = check_callable(use_keys)
        check_types(ignore_deserialization_errors, bool)
        check_types(save_consistency, bool)
        check_types(use_keys, bool)
        check_types(solo_usage, bool)
        self.registered_models = []
        self.registered_django_models = {}
        prefix = check_callable(prefix)
        if type(prefix) == str:
            self.prefix = prefix
        else:
            print(
                f'{datetime.datetime.now()} - Prefix {prefix} is type of {type(prefix)}, allowed only str, using default prefix "redis_test"')
            self.prefix = 'redis_test'
        self.connection_pool = self._get_connection_pool(connection_pool)
        self.ignore_deserialization_errors = ignore_deserialization_errors
        self.save_consistency = save_consistency
        self.use_keys = use_keys
        self.creating = {}
        self.solo_usage = solo_usage
        self.max_models_ids = {}
        self.set_wait_creating(False)
    
    @property
    def redis_instance(self):
        redis_instance = redis.Redis(connection_pool=self.connection_pool)
        return redis_instance
    
    def _get_connection_pool(self, connection_pool):
        if isinstance(connection_pool, redis.ConnectionPool):
            connection_pool.connection_kwargs['decode_responses'] = True
            self.connection_pool = connection_pool
        else:
            print(
                f'{datetime.datetime.now()} - {self.__class__.__name__}: No connection_pool provided, trying default config...')
            default_host = 'localhost'
            default_port = 6379
            default_db = 0
            try:
                connection_pool = redis.ConnectionPool(
                    decode_responses=True,
                    host=default_host,
                    port=default_port,
                    db=default_db,
                )
                self.connection_pool = connection_pool
            except BaseException as ex:
                raise Exception(
                    f'Default config ({default_host}:{default_port}, db={default_db}) failed, please provide connection_pool to {self.__class__.__name__}')
        return self.connection_pool
    
    
    ### UTILS ###
    
    def register_models(self, models_list):
        for model in models_list:
            if issubclass(model, RedisModel):
                if model not in self.registered_models:
                    self.registered_models.append(model)
            else:
                raise Exception(f'{model.__name__} class is not RedisModel')
        
    
    def order(self, instances, field_name):
        reverse = False
        if field_name.startswith('-'):
            reverse = True
            field_name = field_name[1:]
        
        return sorted(instances, key=(lambda instance: instance[field_name]), reverse=reverse)
    
    def get_wait_creating(self):
        if self.solo_usage:
            return self.is_creating
        else:
            return bool(int(self.redis_instance.get(f'__creating__:{self.prefix}')))
    
    def set_wait_creating(self, is_creating):
        if self.solo_usage:
            self.is_creating = is_creating
        else:
            self.redis_instance.set(f'__creating__:{self.prefix}', int(is_creating))
    
    def wait_creation(self):
        while self.get_wait_creating():
            pass
        self.set_wait_creating(True)
    
    def get_and_reserve_new_id(self, model):
        
        def really_new():
            new_id = self._get_model_new_id(model)
            self.creating[model] = [new_id]
            return new_id
        
        self.wait_creation()
        if model not in self.creating.keys():
            new_id = really_new()
        elif not len(self.creating[model]):
            new_id = really_new()
        else:
            new_id = self.creating[model][-1] + 1
        self.set_wait_creating(False)
        return new_id
    
    def remove_creating(self, model, instance_id):
        self.wait_creation()
        self.creating[model] = list(filter(lambda some_instance_id: some_instance_id != instance_id, self.creating[model].copy()))
        self.set_wait_creating(False)
    
    ### GET ###
    
    def get(self, model, return_dict=False, **filters):
        instances = self._get_model_instances(model, filters)
        result = self._return_with_format(instances, return_dict)
        return result
    
    def _get_model_instances(self, model, filters):
        
        instances = self._get_stored_model_instances(model, filters)
        if self.save_consistency:
            instances = self._check_fields_existence(model, instances)
        return instances
    
    def _get_stored_model_instances(self, model, filters):
        if not filters:
            instances = self._get_instances_data_by_ids(model)
        else:
            # print()
            # print(filters)
            cleaned_filters = self._clean_filters(model, filters)
            # print(cleaned_filters)
            cleaned_filters_with_filtered_ids = self._get_cleaned_filters_with_filtered_ids(cleaned_filters)
            # print(cleaned_filters_with_filtered_ids)
            starting_model_filtered_ids = self._get_starting_model_filtered_ids(cleaned_filters_with_filtered_ids)
            # print(starting_model_filtered_ids)
            instances = self._get_instances_data_by_ids(model, starting_model_filtered_ids)
        return instances
    
    def _get_instances_data_by_ids(self, model, ids=None):
        model_name = model.__name__
        instances_data = {}
        if ids is None:
            raw_instances_data = self.fast_get_keys_values(f'{self.prefix}:{model_name}:*')
            for raw_instance_key, raw_instance_value in raw_instances_data.items():
                instance_id = int(raw_instance_key.split(':')[-2])
                instance_field_name = raw_instance_key.split(':')[-1]
                if instance_id not in instances_data.keys():
                    instances_data[instance_id] = {}
                instances_data[instance_id][instance_field_name] = raw_instance_value
        else:
            for instance_id in ids:
                raw_fields_data = self.fast_get_keys_values(f'{self.prefix}:{model_name}:{instance_id}:*')
                for field_key, field_value in raw_fields_data.items():
                    if instance_id not in instances_data.keys():
                        instances_data[instance_id] = {}
                    instances_data[instance_id][field_key.split(':')[-1]] = field_value
        instances_data = {
            instance_id: {
                field_name: self._deserialize_instance_field(model, field_name, field_value)
                for field_name, field_value in raw_instance_fields.items()
            }
            for instance_id, raw_instance_fields in instances_data.copy().items()
        }
        return instances_data
    
    def _get_model_new_id(self, model):
        if self.solo_usage:
            if model not in self.max_models_ids.keys():
                self.max_models_ids[model] = 0
            max_id = self.max_models_ids[model]
            new_id = max_id + 1
            self.max_models_ids[model] = new_id
        else:
            stored_max_id = self.redis_instance.get(f'max_id:{self.prefix}:{model.__name__}')
            max_id = 0
            if stored_max_id:
                max_id = int(stored_max_id)
            new_id = max_id + 1
            self.redis_instance.set(f'max_id:{self.prefix}:{model.__name__}', new_id)
        return new_id
        
        
    def _get_instances_by_key(self, key):
        raw_instances = self.fast_get_keys_values(key)
        instances = {}
        
        for instance_key, fields_json in raw_instances.items():
            prefix, model_name, instance_id = instance_key.split(':')
            instance_id = int(instance_id)
            fields_dict = json.loads(fields_json)
            for field_name, raw_value in fields_dict.items():
                value = self._deserialize_instance_field(raw_value, model_name, field_name)
                if instance_id not in instances.keys():
                    instances[instance_id] = {}
                instances[instance_id][field_name] = value
        return instances
    
    def _check_fields_existence(self, model, instances):
        checked_instances = {}
        fields = model.get_class_fields()
        if 'id' not in fields.keys():
            fields['id'] = RedisString(null=True)
        for instance_id, instance_fields in instances.items():
            checked_instances[instance_id] = {}
            for field_name, field in fields.items():
                if field_name in instance_fields.keys():
                    checked_instances[instance_id][field_name] = instance_fields[field_name]
                else:
                    checked_instances[instance_id][field_name] = None
        return checked_instances
    
    ### DESERIALIZE ###
    
    def _deserialize_instance_field(self, model, field_name, raw_value):
        value = raw_value
        saved_field_instance = self._get_field_instance_by_name(model, field_name)
        if issubclass(saved_field_instance.__class__, RedisField):
            value = self._deserialize_value_by_field_instance(saved_field_instance, raw_value)
        return value
    
    def _get_registered_model_by_name(self, model_name):
        found = False
        model = None
        for registered_model in self.registered_models:
            if registered_model.__name__ == model_name and not found:
                found = True
                model = registered_model
        if not found:
            if self.ignore_deserialization_errors:
                print(f'{datetime.datetime.now()} - {model_name} not found in registered models, ignoring')
                model = model_name
            else:
                raise Exception(f'{model_name} not found in registered models')
        return model
    
    def _get_field_instance_by_name(self, model, field_name):
        try:
            field_instance = getattr(model, field_name)
        except BaseException as ex:
            if self.ignore_deserialization_errors:
                print(
                    f'{datetime.datetime.now()} - {model.__name__} has no field {field_name}, ignoring deserialization')
                field_instance = field_name
            else:
                raise Exception(f'{model.__name__} has no field {field_name}')
        return field_instance
    
    def _deserialize_value_by_field_instance(self, field_instance, raw_value):
        try:
            value = field_instance.deserialize_value(raw_value, self)
        except BaseException as ex:
            if self.ignore_deserialization_errors:
                print(
                    f'{datetime.datetime.now()} - {raw_value} can not be deserialized like {field_instance.__class__.__name__}, ignoring')
                value = raw_value
            else:
                raise Exception(f'{raw_value} can not be deserialized like {field_instance.__class__.__name__}')
        return value
    
    ### FILTER ###
    
    def _clean_filters(self, starting_model, filters):
        cleaned_filters = {}
        for filter_param, filter_value in filters.items():
            field_to_filter_names, filter_type = self._split_filtering(filter_param)
            filtering_models = [starting_model]
            filtering_field_names = []
            for field_to_filter_name in field_to_filter_names:
                filtering_model_fields = filtering_models[-1].get_class_fields()
                field = filtering_model_fields[field_to_filter_name]
                if field.__class__ in [RedisForeignKey, RedisManyToMany]:
                    filtering_field_names.append(field_to_filter_name)
                    if field_to_filter_names.index(field_to_filter_name) == len(field_to_filter_names) - 1:
                        key = json.dumps({
                            'field_names': filtering_field_names,
                            'model_names': [model.__name__ for model in filtering_models]
                        })
                        if key not in cleaned_filters.keys():
                            cleaned_filters[key] = {}
                        if 'id' not in cleaned_filters[key].keys():
                            cleaned_filters[key]['id'] = {}
                        cleaned_filters[key]['id']['in'] = get_ids_from_untyped_data(filter_value)
                    else:
                        filtering_models.append(field.model)
                else:
                    key = json.dumps({
                        'field_names': filtering_field_names,
                        'model_names': [model.__name__ for model in filtering_models]
                    })
                    if key not in cleaned_filters.keys():
                        cleaned_filters[key] = {}
                    if field_to_filter_name not in cleaned_filters[key].keys():
                        cleaned_filters[key][field_to_filter_name] = {}
                    cleaned_filters[key][field_to_filter_name][filter_type] = filter_value
            
        return cleaned_filters
    
    def _split_filtering(self, filter_param):
        filter_field_name, filter_type = filter_param, 'exact'
        if '__' in filter_param:
            filter_param_split = filter_param.split('__')
            if filter_param_split[-1] in ['exact', 'iexact', 'contains', 'icontains', 'in', 'gt', 'gte', 'lt', 'lte',
                                          'startswith', 'istartswith', 'endswith', 'iendswith', 'range', 'isnull']:
                fields_to_filter = filter_param_split[:-1]
                filter_type = filter_param_split[-1]
            else:
                fields_to_filter = filter_param_split
        else:
            fields_to_filter = [filter_field_name]
        return fields_to_filter, filter_type
    
    def _get_cleaned_filters_with_filtered_ids(self, cleaned_filters):
        cleaned_filters_with_filtered_ids = {}
        for relations_data, filter_data in cleaned_filters.items():
            filtered_ids = []
            filtering_model_name = json.loads(relations_data)['model_names'][-1]
            for field_name, filters in filter_data.items():
                stored_data = self.fast_get_keys_values(
                    f'{self.prefix}:{filtering_model_name}:*:{field_name}'
                )
                model = self._get_registered_model_by_name(filtering_model_name)
                field_filtered_ids = []
                for instance_key, instance_value in stored_data.items():
                    value = self._deserialize_instance_field(model, field_name, instance_value)
                    allowed = (
                        self._filter_value(value, filter_type, filter_by)
                        for filter_type, filter_by in filters.items()
                    )
                    if all(allowed):
                        field_filtered_ids.append(int(instance_key.split(':')[-2]))
                filtered_ids.append(field_filtered_ids)
            if filtered_ids:
                filtered_ids = list(reduce(
                    lambda a, b: set(a) & set(b),
                    filtered_ids
                ))
            cleaned_filters_with_filtered_ids[relations_data] = filtered_ids
        
        return cleaned_filters_with_filtered_ids

    def _filter_value(self, value, filter_type, filter_by):
        allowed = True
        if isinstance(filter_by, datetime.datetime):
            filter_by = filter_by.replace(tzinfo=pytz.UTC)
        if filter_type == 'exact':
            if value != filter_by:
                allowed = False
        elif filter_type == 'iexact':
            if value.lower() != filter_by.lower():
                allowed = False
        elif filter_type == 'contains':
            if filter_by not in value:
                allowed = False
        elif filter_type == 'icontains':
            if filter_by.lower() not in value.lower():
                allowed = False
        elif filter_type == 'in':
            if value not in filter_by:
                allowed = False
        elif filter_type == 'gt':
            if value <= filter_by:
                allowed = False
        elif filter_type == 'gte':
            if value < filter_by:
                allowed = False
        elif filter_type == 'lt':
            if value >= filter_by:
                allowed = False
        elif filter_type == 'lte':
            if value > filter_by:
                allowed = False
        elif filter_type == 'startswith':
            if not value.startswith(filter_by):
                allowed = False
        elif filter_type == 'istartswith':
            if not value.lower().startswith(filter_by.lower()):
                allowed = False
        elif filter_type == 'endswith':
            if not value.endswith(filter_by):
                allowed = False
        elif filter_type == 'iendswith':
            if not value.lower().endswith(filter_by.lower()):
                allowed = False
        elif filter_type == 'range':
            if value not in range(filter_by):
                allowed = False
        elif filter_type == 'isnull':
            if (value in ['null', None]) != filter_by:
                allowed = False
        return allowed
    
    def _get_starting_model_filtered_ids(self, cleaned_filters_with_filtered_ids):
        starting_filtered_ids = []
        for relations_data, filtered_ids in cleaned_filters_with_filtered_ids.items():
            allowed_ids = filtered_ids.copy()
            real_relations_data = json.loads(relations_data)
            while real_relations_data['field_names']:
                field_name = real_relations_data['field_names'].pop(-1)
                model_name = real_relations_data['model_names'].pop(-1)
                all_stored_model_fields = self.fast_get_keys_values(f'{self.prefix}:{model_name}:*:{field_name}')
                allowed_ids = [
                    int(instance_key.split(':')[-2])
                    for instance_key, instance_value in all_stored_model_fields.items()
                    if int(instance_value) in allowed_ids
                ]
            starting_filtered_ids.append(allowed_ids)
        if starting_filtered_ids:
            starting_filtered_ids = sorted(list(reduce(
                lambda set_a, set_b: set(set(set_a) & set(set_b)),
                starting_filtered_ids.copy()
            )))
        return starting_filtered_ids
        
    ### UPDATE ###
    
    def update(self, model, instances=None, return_dict=False, **fields_to_update):
        updated_instances, data_to_update = self._collect_update(model, instances, fields_to_update)
        self._confirm_update(data_to_update)
        result = self._return_with_format(updated_instances, return_dict)
        return result
    
    def update_nb(self, model, instances=None, return_dict=False, **fields_to_update):
        updated_instances, data_to_update = self._collect_update(model, instances, fields_to_update)
        asyncio.get_event_loop().create_task(
            self._confirm_update_async(data_to_update)
        )
        result = self._return_with_format(updated_instances, return_dict)
        return result
    
    def _collect_update(self, model, instances, fields_to_update):
        model_name = model.__name__
        if instances is not None:
            ids_to_update = get_ids_from_untyped_data(instances)
        else:
            ids_to_update = None
        if ids_to_update is not None:
            updated_instances = self.get(model, return_dict=True, id__in=ids_to_update)
        else:
            updated_instances = self.get(model, return_dict=True)
        
        collected_data_to_update = {}
        for field_to_update_name, field_to_update_value in fields_to_update.items():
            saved_field_instance = self._get_field_instance_by_name(model, field_to_update_name)
            saved_field_instance.value = field_to_update_value
            saved_field_instance.clean()
            cleaned_field_to_update_value = saved_field_instance.value
            updated_instances = {
                updated_instance_id: {**updated_instance_data, field_to_update_name: field_to_update_value}
                for updated_instance_id, updated_instance_data in updated_instances.items()
            }
            keys_to_update = self.collect_keys(model_name, ids_to_update, field_to_update_name)
            update_mapping = {
                key: cleaned_field_to_update_value
                for key in keys_to_update
            }
            collected_data_to_update = {
                **collected_data_to_update,
                **update_mapping
            }
        return updated_instances, collected_data_to_update
    
    def _confirm_update(self, data_to_update):
        if data_to_update.keys():
            self.redis_instance.mset(data_to_update)
    
    async def _confirm_update_async(self, data_to_update):
        self._confirm_update(data_to_update)
            
    #
    #
    # def _get_instance_keys_to_update(self, instances, model_name):
    #     keys_to_update = []
    #
    #     if self.use_keys:
    #         if instances is None:
    #             keys_to_update += list(self.redis_instance.keys(f'{self.prefix}:{model_name}:*'))
    #         else:
    #             ids_to_update = get_ids_from_untyped_data(instances)
    #             for instance_id in ids_to_update:
    #                 keys_to_update += list(self.redis_instance.keys(f'{self.prefix}:{model_name}:{instance_id}:*'))
    #     else:
    #         if instances is None:
    #             keys_to_update += list(self.redis_instance.scan_iter(f'{self.prefix}:{model_name}:*'))
    #         else:
    #             ids_to_update = get_ids_from_untyped_data(instances)
    #             for instance_id in ids_to_update:
    #                 keys_to_update += list(self.redis_instance.scan_iter(f'{self.prefix}:{model_name}:{instance_id}:*'))
    #     return keys_to_update
    
    # def update(self, model, instances=None, return_dict=False, renew_ttl=False, new_ttl=None, **fields_to_update):
    #     model_name = model.__name__
    #     instance_keys_to_update = self._get_instance_keys_to_update(instances, model_name)
    #     updated_instances = {}
    #     for instance_key in instance_keys_to_update:
    #         prefix, model_name, instance_id = instance_key.split(':')
    #         instance_id = int(instance_id)
    #         fields_to_write = self._update_serialize_fields(instance_key, model, fields_to_update)
    #         self._update_confirm(model, instance_key, renew_ttl, new_ttl, fields_to_write)
    #         updated_instances[instance_id] = fields_to_write
    #     result = self._return_with_format(updated_instances, return_dict)
    #     return result
    #
    # def update_nb(self, model, instances=None, return_dict=False, renew_ttl=False, new_ttl=None, **fields_to_update):
    #     model_name = model.__name__
    #     instance_keys_to_update = self._get_instance_keys_to_update(instances, model_name)
    #     updated_instances = {}
    #     loop = asyncio.get_event_loop()
    #     for instance_key in instance_keys_to_update:
    #         prefix, model_name, instance_id = instance_key.split(':')
    #         instance_id = int(instance_id)
    #         fields_to_write = self._update_serialize_fields(instance_key, model, fields_to_update)
    #         loop.create_task(
    #             self._update_confirm_async(model, instance_key, renew_ttl, new_ttl, fields_to_write)
    #         )
    #         updated_instances[instance_id] = fields_to_write
    #     result = self._return_with_format(updated_instances, return_dict)
    #     return result
    #

    #
    # def _update_serialize_fields(self, instance_key, model, fields_to_update):
    #     instance_data_json = self.redis_instance.get(instance_key)
    #     instance_data = json.loads(instance_data_json)
    #     serialized_data = {}
    #     for field_name, field_data in instance_data.items():
    #         saved_field_instance = self._get_field_instance_by_name(field_name, model)
    #         if field_name in fields_to_update.keys():
    #             saved_field_instance.value = fields_to_update[field_name]
    #             cleaned_value = saved_field_instance.clean()
    #         else:
    #             cleaned_value = field_data
    #         serialized_data[field_name] = cleaned_value
    #     return serialized_data
    #
    # def _update_confirm(self, model, instance_key, renew_ttl, new_ttl, fields_to_write):
    #     ttl = None
    #     if renew_ttl:
    #         ttl = model.get_instance_ttl()
    #     elif new_ttl:
    #         ttl = new_ttl
    #     fields_to_write_json = json.dumps(fields_to_write)
    #     self.redis_instance.set(instance_key, fields_to_write_json, ex=ttl)
    #
    # async def _update_confirm_async(self, model, instance_key, renew_ttl, new_ttl, fields_to_write):
    #     ttl = None
    #     if renew_ttl:
    #         ttl = model.get_instance_ttl()
    #     elif new_ttl:
    #         ttl = new_ttl
    #     fields_to_write_json = json.dumps(fields_to_write)
    #     self.redis_instance.set(instance_key, fields_to_write_json, ex=ttl)
    
    ### DELETE ###
    
    def delete(self, model, instances=None):
        model_name = model.__name__
        self._confirm_delete(model_name, instances)
    
    def delete_nb(self, model, instances=None):
        model_name = model.__name__
        asyncio.get_event_loop().create_task(
            self._confirm_delete_async(model_name, instances)
        )
    
    def _confirm_delete(self, model_name, instances):
        ids_to_delete = None
        if instances is not None:
            ids_to_delete = get_ids_from_untyped_data(instances)
        keys_to_delete = self.collect_keys(model_name, ids_to_delete)
        if keys_to_delete:
            self.redis_instance.delete(*keys_to_delete)
    
    async def _confirm_delete_async(self, model_name, instances):
        self._confirm_delete(model_name, instances)
    
    def _delete_by_key(self, key):
        self.redis_instance.delete(key)
    
    ### CREATE ###
    
    def create(self, model, **params):
        params = self._get_allowed_model_params(model, params)
        redis_instance = model(redis_root=self, **params).save()
        return redis_instance
    
    def create_nb(self, model, **params):
        params = self._get_allowed_model_params(model, params)
        redis_instance = model(redis_root=self, **params).save_nb()
        return redis_instance
    
    def _get_allowed_model_params(self, model, params):
        model_attrs = model.get_class_fields()
        allowed_params = {
            param_name: params[param_name]
            for param_name in params.keys()
            if param_name in model_attrs.keys()
        }
        return allowed_params
    
    ### HELPERS ###
    
    def _return_with_format(self, instances, return_dict=False):
        if return_dict:
            return instances
        else:
            instances_list = [
                {
                    'id': instance_id,
                    **instance_fields
                }
                for instance_id, instance_fields in instances.items()
            ]
            return instances_list
    
    def fast_get_keys_values(self, string):
        if self.use_keys:
            keys = list(self.redis_instance.keys(string))
        else:
            keys = list(self.redis_instance.scan_iter(string))
        values = self.redis_instance.mget(keys)
        results = dict(zip(keys, values))
        return results
    
    def collect_keys(self, model_name, ids=None, field_name=None):
        collected_keys = []
        field_name_query_string = '*' if field_name is None else field_name
        if ids is None:
            query_string = f'{self.prefix}:{model_name}:*:{field_name_query_string}'
            if self.use_keys:
                collected_keys = list(self.redis_instance.keys(query_string))
            else:
                collected_keys = list(self.redis_instance.scan_iter(query_string))
        else:
            for id in ids:
                query_string = f'{self.prefix}:{model_name}:{id}:{field_name_query_string}'
                if self.use_keys:
                    collected_keys += list(self.redis_instance.keys(query_string))
                else:
                    collected_keys += list(self.redis_instance.scan_iter(query_string))
        return collected_keys


### REDIS MODEL ###


class RedisModel:
    id = RedisId()
    
    ### INIT ###
    
    def __init__(self, redis_root=None, **kwargs):
        self.__model_data__ = {
            'redis_root': None,
            'name': None,
            'fields': {},
            'meta': {},
        }
        
        if isinstance(redis_root, RedisRoot):
            self.__model_data__['redis_root'] = redis_root
            self.__model_data__['name'] = self.__class__.__name__
            if self.__class__ != RedisModel:
                self._renew_fields()
                self.__model_data__['redis_root'].register_models([self.__class__])
                self._fill_fields_values(kwargs)
        
        else:
            raise Exception(f'{redis_root.__name__} type is {type(redis_root)}. Allowed only RedisRoot')
    
    def _renew_fields(self):
        class_fields = self.__class__.get_class_fields()
        fields = {}
        for field_name, field in class_fields.items():
            fields[field_name] = self._get_initial_model_field(field_name)
        self.__model_data__['fields'] = fields
    
    @classmethod
    def get_class_fields(cls):
        field_names = dir(cls)
        fields = {}
        for field_name in field_names:
            field_value = getattr(cls, field_name)
            if isinstance(field_value, RedisField):
                fields[field_name] = field_value
        return fields
        
    def _get_initial_model_field(self, field_name):
        name = self.get('name')
        if field_name in dir(self.__class__):
            return deepcopy(getattr(self.__class__, field_name))
        else:
            raise Exception(f'{name} has no field {field_name}')
    
    def _fill_fields_values(self, field_values_dict):
        for name, value in field_values_dict.items():
            fields = self.__model_data__['fields']
            if name in fields.keys():
                fields[name].value = value
            else:
                raise Exception(f'{self.__class__.__name__} has no field {name}')
    
    ### SAVE ###
    
    def save(self):
        instance_key, fields_dict, deserialized_fields = self._serialize_data()
        self._set_fields(instance_key, fields_dict)
        return deserialized_fields
    
    def save_nb(self):
        instance_key, fields_dict, deserialized_fields = self._serialize_data()
        asyncio.get_event_loop().create_task(
            self._set_fields_async(instance_key, fields_dict)
        )
        return deserialized_fields
    
    def _serialize_data(self):
        redis_root = self.get('redis_root')
        name = self.get('name')
        fields = self.get('fields')
        fields = dict(fields)
        self._get_and_reserve_new_id()
        fields['id'] = self.id
        instance_key = f'{redis_root.prefix}:{name}:{self.id.value}'
        deserialized_fields = {}
        cleaned_fields = {}
        for field_name, field in fields.items():
            try:
                cleaned_value = field.clean()
                cleaned_fields[field_name] = cleaned_value
                deserialized_value = redis_root._deserialize_instance_field(self, field_name, cleaned_value)
                deserialized_fields[field_name] = deserialized_value
            except BaseException as ex:
                raise Exception(f'{ex} ({name} -> {field_name})')
        return instance_key, cleaned_fields, deserialized_fields
    
    def _get_and_reserve_new_id(self):
        redis_root = self.get('redis_root')
        self.id.value = redis_root.get_and_reserve_new_id(self.__class__)
    
    def _set_fields(self, instance_key, fields_dict):
        redis_root = self.get('redis_root')
        prefix, model_name, instance_id = instance_key.split(':')
        instance_id = int(instance_id)
        fields_dict = {
            f'{instance_key}:{field_name}': field_value
            for field_name, field_value in fields_dict.copy().items()
        }
        redis_root.redis_instance.mset(fields_dict)
        redis_root.remove_creating(self.__class__, instance_id)
    
    async def _set_fields_async(self, instance_key, fields_dict):
        self._set_fields(instance_key, fields_dict)
        
    ### UTILS ###
    
    def set(self, force=False, **fields_with_values):
        name = self.get('name')
        fields = self.get('fields')
        meta = self.get('meta')
        for field_name, value in fields_with_values.items():
            if field_name in fields.keys():
                field = fields[field_name]
                field.value = value
                return field.value
            elif field_name in meta.keys():
                meta[field_name] = value
                return meta[field_name]
            else:
                if force:
                    fields[field_name] = value
                else:
                    raise Exception(f'{name} has no field {field_name}')
    
    def get(self, field_name):
        data = self.__model_data__
        fields = data['fields']
        meta = data['meta']
        redis_root = data['redis_root']
        name = data['name']
        if field_name in fields.keys():
            field = fields[field_name]
            return field.value
        elif field_name in meta.keys():
            return meta[field_name]
        elif field_name == 'redis_root':
            return redis_root
        elif field_name == 'fields':
            return fields
        elif field_name == 'name':
            return name
        elif field_name == 'meta':
            return meta
        else:
            raise Exception(f'{name} has no field {field_name}')
