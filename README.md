# python-redis-orm

## **Python Redis ORM library that gives redis easy-to-use objects with fields and speeds a development up, inspired by Django ORM**


[![Full test](https://github.com/gh0st-work/python_redis_orm/actions/workflows/python-app.yml/badge.svg?event=push)](https://github.com/gh0st-work/python_redis_orm/actions/workflows/python-app.yml)

For one project, I needed to work with redis, but redis-py provides a minimum level of work with redis. I didn't find any Django-like ORM for redis, so I wrote this library, then there will be a port to Django.

### Working with this library, you are expected:

- Fully works in 2021
- Django-like architecture
- Easy adaptation to your needs
- Adequate informational messages and error messages
- Built-in RedisRoot class that stores specified models, with:
    - **redis_instance** setting - your redis connection (from redis-py)
    - **prefix** setting - prefix of this RedisRoot to be stored in redis
    - **ignore_deserialization_errors** setting - do not raise errors, while deserializing data
    - **save_consistency** setting - show structure-first data
    - **economy** setting - to not return full data and save some requests (usually, speeds up your app on 80%)
- 13 built-in types of fields:
    - **RedisField** - base class for nesting
    - **RedisString** - string
    - **RedisNumber** - int or float
    - **RedisId** - instances IDs
    - **RedisBool** - bool
    - **RedisDecimal** - working accurately with numbers via decimal
    - **RedisJson** - for data, that can be JSONed
    - **RedisList** - list
    - **RedisDict** - dict
    - **RedisDateTime** - for work with date and time, via python datetime.datetime
    - **RedisDate** - for work with date, via python datetime.data
    - **RedisForeignKey** - for link to other instance
    - **RedisManyToMany** - for links to other instances
- All fields supports:
    - Automatically serialization
    - Automatically deserialization
    - TTL (Time To Live) setting
    - Default values
    - Providing functions without call, to call, while need
    - Allow null values setting
    - Choices
    - Filtering (and deep filtering):
        - **exact** - equality
        - **iexact** - case-independent equality
        - **contains** - is filter string in the value string
        - **icontains** - is filter string case-independent in the value string
        - **in** - is value in the provided list
        - **gt** - is value greater
        - **gte** - is value greater or equals
        - **lt** - is value less
        - **lte** - is value less or equals
        - **startswith** - is string starts with
        - **istartswith** - is string case-independent starts with
        - **endswith** - is string ends with
        - **iendswith** - is string case-independent ends wth
        - **range** - is value in provided range
        - **isnull** - is value in ["null", None]
- Built-in RedisModel class, with:
    - All fields that you want
    - TTL (Time To Live)
- CRUD (Create Read Update Delete)
- Non-blocking usage! Any operation gives the same result as the default, but it just creates an asyncio task in the background instead of write inside the call


# Installation
`pip install python-redis-orm`

[Here is PyPI](https://pypi.org/project/python-redis-orm/)

Obviously, you need to install and run redis server on your machine, we support v3+ 


# Usage

1. Create **RedisRoot** with params:
    - **prefix** (str) - prefix for your redis root
    - **connection_pool** (redis.ConnectionPool) - redis-py redis.ConnectionPool instance, with decode_responses=True
    - **ignore_deserialization_errors** (bool) - to ignore deserialization errors or raise exception
    - **save_consistency** (bool) - to use structure-first data
    - **economy** (bool) - if True, all update requests will return only instance id 
    - **use_keys** (bool) - to use Redis keys command (uses memory instead of CPU) instead of scan
2. Create your models
3. Call **register_models()** on your RedisRoot instance and provide list with your models
4. Use our CRUD


# CRUD
```python
example_instance = ExampleModel(example_field='example_data').save() # - to create an instance and get its data dict
# or:
example_instance = redis_root.create(ExampleModel, example_field='example_data')
filtered_example_instances = redis_root.get(ExampleModel, example_field='example_data') # - to get all ExampleModel instances with example_field filter and get its data dict
ordered_instances = redis_root.order(filtered_example_instances, '-id') # - to get ordered filtered_example_instances by id ('-' for reverse)
updated_example_instances = redis_root.update(ExampleModel, ordered_instances, example_field='another_example_data') # - to update all ordered_instances example_field with value 'another_example_data' and get its data dict
redis_root.delete(ExampleModel, updated_example_instances) # - to delete updated_example_instances

# Non-blocking funcs are the same, just add "_nb" to the end:
# ExampleModel(...).save_nb()
# redis_root.create_nb(...)
# redis_root.update_nb(...)
# redis_root.delete_nb(...)

```


# Example usage

All features:

[full_test.py](https://github.com/gh0st-work/python_redis_orm/blob/master/python_redis_orm/tests/full_test.py)
```python
import random
import sys
from time import sleep
import asyncio
import os

from python_redis_orm.core import *


def generate_token(chars_count):
    allowed_chars = 'QWERTYUIOPASDFGHJKLZXCVBNM1234567890'
    token = f'{"".join([random.choice(allowed_chars) for i in range(chars_count)])}'
    return token


def generate_token_12_chars():
    return generate_token(12)


class BotSession(RedisModel):
    session_token = RedisString(default=generate_token_12_chars)
    created = RedisDateTime(default=datetime.datetime.now)


class TaskChallenge(RedisModel):
    bot_session = RedisForeignKey(model=BotSession)
    task_id = RedisNumber(default=0, null=False)
    status = RedisString(default='in_work', choices={
        'in_work': 'В работе',
        'completed': 'Завершён успешно',
        'completed_frozen_points': 'Завершён успешно, получил поинты в холде',
        'completed_points': 'Завершён успешно, получил поинты',
        'completed_decommissioning': 'Завершён успешно, поинты списаны',
        'failed_bot': 'Зафейлил бот',
        'failed_task_creator': 'Зафейлил создатель задания',
    }, null=False)
    account_checks_count = RedisNumber(default=0)
    created = RedisDateTime(default=datetime.datetime.now)


class TtlCheckModel(RedisModel):
    redis_number_with_ttl = RedisNumber(default=0, null=False)


class MetaTtlCheckModel(RedisModel):
    redis_number = RedisNumber(default=0, null=False)
    
    class Meta:
        ttl = 5


class DictCheckModel(RedisModel):
    redis_dict = RedisDict()


class ListCheckModel(RedisModel):
    redis_list = RedisList()


class ForeignKeyCheckModel(RedisModel):
    task_challenge = RedisForeignKey(model=TaskChallenge)


class ManyToManyCheckModel(RedisModel):
    task_challenges = RedisManyToMany(model=TaskChallenge)


class ModelWithOverriddenSave(RedisModel):
    multiplied_max_field = RedisNumber()
    
    def save(self):
        redis_root = self.get('redis_root')  # get value of any field
        new_value = 1
        all_instances = redis_root.get(ModelWithOverriddenSave)
        if all_instances:
            max_value = max(list(map(lambda instance: instance['multiplied_max_field'], all_instances)))
            new_value = max_value * 2
        self.set(multiplied_max_field=new_value)
        return super().save()


def clean_db_after_test(connection_pool, prefix):
    redis_instance = redis.Redis(connection_pool=connection_pool)
    for key in redis_instance.keys(f'{prefix}:*'):
        redis_instance.delete(key)


def basic_test(connection_pool, prefix):
    try:
        redis_root = RedisRoot(
            prefix=prefix,
            connection_pool=connection_pool,
            ignore_deserialization_errors=True
        )
        redis_root.register_models([
            TaskChallenge,
        ])
        for i in range(5):
            TaskChallenge(
                redis_root=redis_root,
                status='in_work',
            ).save()
        task_challenges_without_keys = redis_root.get(TaskChallenge)
        task_challenges_with_keys = redis_root.get(TaskChallenge, return_dict=True)
        have_exception = False
        if not len(task_challenges_without_keys):
            have_exception = True
        if not task_challenges_with_keys:
            have_exception = True
        else:
            if not task_challenges_with_keys.keys():
                have_exception = True
            else:
                if len(list(task_challenges_with_keys.keys())) != len(task_challenges_without_keys):
                    have_exception = True
    except BaseException as ex:
        have_exception = True
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def auto_reg_test(connection_pool, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        connection_pool=connection_pool,
        ignore_deserialization_errors=True
    )
    task_challenge_1 = TaskChallenge(
        redis_root=redis_root,
        status='in_work',
    ).save()
    try:
        task_challenges = redis_root.get(TaskChallenge)
        have_exception = False
    except BaseException as ex:
        have_exception = True
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def no_connection_pool_test(*args, **kwargs):
    try:
        redis_root = RedisRoot(
            ignore_deserialization_errors=True
        )
        task_challenge_1 = TaskChallenge(
            redis_root=redis_root,
            status='in_work',
        )
        task_challenge_1.save()
        task_challenges = redis_root.get(TaskChallenge)
        have_exception = False
        connection_pool = redis.ConnectionPool(
            host=os.environ['REDIS_HOST'],
            port=os.environ['REDIS_PORT'],
            db=0,
            decode_responses=True
        )
        clean_db_after_test(connection_pool, redis_root.prefix)
    except BaseException as ex:
        have_exception = True
    return have_exception


def choices_test(connection_pool, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        connection_pool=connection_pool,
        ignore_deserialization_errors=True
    )
    task_challenge_1 = TaskChallenge(
        redis_root=redis_root,
        status='bruh',
    )
    try:
        save_result = task_challenge_1.save()
        task_challenges = redis_root.get(TaskChallenge)
        have_exception = True
    except BaseException as ex:
        have_exception = False
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def order_test(connection_pool, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        connection_pool=connection_pool,
        ignore_deserialization_errors=True
    )
    for i in range(3):
        TaskChallenge(
            redis_root=redis_root
        ).save()
    have_exception = True
    try:
        task_challenges = redis_root.get(TaskChallenge)
        first_task_challenge = redis_root.order(task_challenges, 'id')[0]
        last_task_challenge = redis_root.order(task_challenges, '-id')[0]
        if first_task_challenge['id'] == 1 and last_task_challenge['id'] == len(task_challenges):
            have_exception = False
    except BaseException as ex:
        pass
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def filter_test(connection_pool, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        connection_pool=connection_pool,
        ignore_deserialization_errors=True
    )
    have_exception = True
    try:
        same_tokens_count = 2
        random_tokens_count = 8
        same_token = generate_token(50)
        random_tokens = [generate_token(50) for i in range(random_tokens_count)]
        for i in range(same_tokens_count):
            BotSession(redis_root, session_token=same_token).save()
        for random_token in random_tokens:
            BotSession(redis_root, session_token=random_token).save()
        task_challenges_with_same_token = redis_root.get(BotSession, session_token=same_token)
        if len(task_challenges_with_same_token) == same_tokens_count:
            have_exception = False
    except BaseException as ex:
        print(ex)
    
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def update_test(connection_pool, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        connection_pool=connection_pool,
        ignore_deserialization_errors=True
    )
    have_exception = True
    try:
        bot_session_1 = BotSession(redis_root, session_token='123').save()
        bot_session_1_id = bot_session_1['id']
        redis_root.update(BotSession, bot_session_1, session_token='234')
        bot_sessions_filtered = redis_root.get(BotSession, id=bot_session_1_id)
        if len(bot_sessions_filtered) == 1:
            bot_session_1_new = bot_sessions_filtered[0]
            if 'session_token' in bot_session_1_new.keys():
                if bot_session_1_new['session_token'] == '234':
                    have_exception = False
    except BaseException as ex:
        print(ex)
    
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def functions_like_defaults_test(connection_pool, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        connection_pool=connection_pool,
        ignore_deserialization_errors=True
    )
    have_exception = False
    try:
        bot_session_1 = BotSession(redis_root).save()
        bot_session_2 = BotSession(redis_root).save()
        if bot_session_1.session_token == bot_session_2.session_token:
            have_exception = True
    except BaseException as ex:
        pass
    
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def redis_foreign_key_test(connection_pool, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        connection_pool=connection_pool,
        ignore_deserialization_errors=True
    )
    have_exception = True
    try:
        bot_session_1 = BotSession(
            redis_root=redis_root,
        ).save()
        task_challenge_1 = TaskChallenge(
            redis_root=redis_root,
            bot_session=bot_session_1
        ).save()
        bot_sessions = redis_root.get(BotSession)
        bot_session = redis_root.order(bot_sessions, '-id')[0]
        task_challenges = redis_root.get(TaskChallenge)
        task_challenge = redis_root.order(task_challenges, '-id')[0]
        if type(task_challenge['bot_session']) == dict:
            if task_challenge['bot_session'] == bot_session:
                have_exception = False
    except BaseException as ex:
        print(ex)
    
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def delete_test(connection_pool, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        connection_pool=connection_pool,
        ignore_deserialization_errors=True
    )
    have_exception = True
    try:
        bot_session_1 = BotSession(
            redis_root=redis_root,
        ).save()
        task_challenge_1 = TaskChallenge(
            redis_root=redis_root,
            bot_session=bot_session_1
        ).save()
        redis_root.delete(BotSession, bot_session_1)
        redis_root.delete(TaskChallenge, task_challenge_1)
        bot_sessions = redis_root.get(BotSession)
        task_challenges = redis_root.get(TaskChallenge)
        if len(bot_sessions) == 0 and len(task_challenges) == 0:
            have_exception = False
    except BaseException as ex:
        print(ex)
    
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def save_consistency_test(connection_pool, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        connection_pool=connection_pool,
        ignore_deserialization_errors=True,
        save_consistency=True,
    )
    have_exception = True
    try:
        ttl_check_model_1 = TtlCheckModel(
            redis_root=redis_root,
        ).save()
        ttl_check_models = redis_root.get(TtlCheckModel)
        if len(ttl_check_models):
            ttl_check_model = ttl_check_models[0]
            if 'redis_number_with_ttl' in ttl_check_model.keys():
                sleep(6)
                ttl_check_models = redis_root.get(TtlCheckModel)
                if len(ttl_check_models):
                    ttl_check_model = ttl_check_models[0]
                    if 'redis_number_with_ttl' in ttl_check_model.keys():  # because consistency is saved
                        have_exception = False
    except BaseException as ex:
        print(ex)
    
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def meta_ttl_test(connection_pool, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        connection_pool=connection_pool,
        ignore_deserialization_errors=True,
    )
    have_exception = True
    try:
        meta_ttl_check_model_1 = MetaTtlCheckModel(
            redis_root=redis_root,
        ).save()
        meta_ttl_check_models = redis_root.get(MetaTtlCheckModel)
        if len(meta_ttl_check_models):
            meta_ttl_check_model = meta_ttl_check_models[0]
            if 'redis_number' in meta_ttl_check_model.keys():
                sleep(6)
                meta_ttl_check_models = redis_root.get(MetaTtlCheckModel)
                if not len(meta_ttl_check_models):
                    have_exception = False
    except BaseException as ex:
        print(ex)
    
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def use_keys_test(connection_pool, prefix):
    have_exception = True
    try:
        
        redis_root = RedisRoot(
            prefix=prefix,
            connection_pool=connection_pool,
            ignore_deserialization_errors=True,
            use_keys=True
        )
        started_in_keys = datetime.datetime.now()
        tests_count = 100
        for i in range(tests_count):
            task_challenge_1 = TaskChallenge(
                redis_root=redis_root,
                status='in_work',
            ).save()
            redis_root.update(TaskChallenge, task_challenge_1, account_checks_count=1)
        ended_in_keys = datetime.datetime.now()
        keys_time = (ended_in_keys - started_in_keys).total_seconds()
        clean_db_after_test(connection_pool, prefix)
        
        redis_root = RedisRoot(
            prefix=prefix,
            connection_pool=connection_pool,
            ignore_deserialization_errors=True,
            use_keys=False
        )
        started_in_no_keys = datetime.datetime.now()
        for i in range(tests_count):
            task_challenge_1 = TaskChallenge(
                redis_root=redis_root,
                status='in_work',
            ).save()
            redis_root.update(TaskChallenge, task_challenge_1, account_checks_count=1)
        ended_in_no_keys = datetime.datetime.now()
        no_keys_time = (ended_in_no_keys - started_in_no_keys).total_seconds()
        clean_db_after_test(connection_pool, prefix)
        keys_percent = round((no_keys_time / keys_time - 1) * 100, 2)
        keys_symbol = ('+' if keys_percent > 0 else '')
        print(f'Keys usage gives {keys_symbol}{keys_percent}% efficiency')
        have_exception = False
    except BaseException as ex:
        print(ex)
    
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def dict_test(connection_pool, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        connection_pool=connection_pool,
        ignore_deserialization_errors=True
    )
    have_exception = True
    try:
        some_dict = {
            'age': 19,
            'weed': True
        }
        DictCheckModel(
            redis_root=redis_root,
            redis_dict=some_dict
        ).save()
        dict_check_model_instance = redis_root.get(DictCheckModel)[0]
        if 'redis_dict' in dict_check_model_instance.keys():
            if dict_check_model_instance['redis_dict'] == some_dict:
                have_exception = False
    except BaseException as ex:
        print(ex)
    
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def list_test(connection_pool, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        connection_pool=connection_pool,
        ignore_deserialization_errors=True
    )
    have_exception = True
    try:
        some_list = [5, 9, 's', 4.5, False]
        ListCheckModel(
            redis_root=redis_root,
            redis_list=some_list
        ).save()
        list_check_model_instance = redis_root.get(ListCheckModel)[0]
        if 'redis_list' in list_check_model_instance.keys():
            if list_check_model_instance['redis_list'] == some_list:
                have_exception = False
    except BaseException as ex:
        print(ex)
    
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def non_blocking_test(connection_pool, prefix):
    have_exception = True
    
    # try:
    
    def task(data_count, use_non_blocking):
        connection_pool = redis.ConnectionPool(
            host=os.environ['REDIS_HOST'],
            port=os.environ['REDIS_PORT'],
            db=0,
            decode_responses=True
        )
        redis_root = RedisRoot(
            prefix=prefix,
            connection_pool=connection_pool,
            ignore_deserialization_errors=True
        )
        
        for i in range(data_count):
            redis_root.create(
                ListCheckModel,
                redis_list=['update_list']
            )
            redis_root.create(
                ListCheckModel,
                redis_list=['delete_list']
            )
        
        def create_list():
            if use_non_blocking:
                list_check_model_instance = redis_root.create_nb(
                    ListCheckModel,
                    redis_list=['create_list']
                )
            else:
                list_check_model_instance = redis_root.create(
                    ListCheckModel,
                    redis_list=['create_list']
                )
        
        def update_list():
            to_update = redis_root.get(
                ListCheckModel,
                redis_list=['update_list']
            )
            if use_non_blocking:
                updated_instance = redis_root.update_nb(
                    ListCheckModel,
                    to_update,
                    redis_list=['now_updated_list']
                )
            else:
                updated_instance = redis_root.update(
                    ListCheckModel,
                    to_update,
                    redis_list=['now_updated_list']
                )
        
        def delete_list():
            to_delete = redis_root.get(
                ListCheckModel,
                redis_list=['delete_list']
            )
            if use_non_blocking:
                redis_root.delete_nb(
                    ListCheckModel,
                    to_delete,
                )
            else:
                redis_root.delete(
                    ListCheckModel,
                    to_delete,
                )
        
        tests = [
            create_list,
            update_list,
            delete_list,
        ]
        for test in tests:
            for i in range(data_count):
                test()
    
    data_count = 100
    clean_db_after_test(connection_pool, prefix)
    nb_started_in = datetime.datetime.now()
    task(data_count, True)
    nb_ended_in = datetime.datetime.now()
    nb_time = (nb_ended_in - nb_started_in).total_seconds()
    clean_db_after_test(connection_pool, prefix)
    b_started_in = datetime.datetime.now()
    task(data_count, False)
    b_ended_in = datetime.datetime.now()
    b_time = (b_ended_in - b_started_in).total_seconds()
    clean_db_after_test(connection_pool, prefix)
    
    nb_percent = round((nb_time / b_time - 1) * 100, 2)
    nb_symbol = ('+' if nb_percent > 0 else '')
    print(f'Non blocking gives {nb_symbol}{nb_percent}% efficiency')
    have_exception = False
    # except BaseException as ex:
    #     print(ex)
    
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def foreign_key_test(connection_pool, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        connection_pool=connection_pool,
        ignore_deserialization_errors=True,
    )
    have_exception = False
    try:
        task_id = 12345
        task_challenge = TaskChallenge(
            redis_root=redis_root,
            task_id=task_id
        ).save()
        foreign_key_check_instance = redis_root.create(
            ForeignKeyCheckModel,
            task_challenge=task_challenge
        )
        # Check really created
        task_challenge_qs = redis_root.get(TaskChallenge, task_id=task_id)
        if len(task_challenge_qs) != 1:
            have_exception = True
        else:
            task_challenge = task_challenge_qs[0]
            foreign_key_check_instance_qs = redis_root.get(ForeignKeyCheckModel, task_challenge=task_challenge)
            if len(foreign_key_check_instance_qs) != 1:
                have_exception = True
            else:
                foreign_key_check_instance = foreign_key_check_instance_qs[0]
                if foreign_key_check_instance['task_challenge']['task_id'] != task_id:
                    have_exception = True
    except BaseException as ex:
        print(ex)
        have_exception = True
    
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def many_to_many_test(connection_pool, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        connection_pool=connection_pool,
        ignore_deserialization_errors=True,
    )
    have_exception = False
    try:
        tasks_ids = set([random.randrange(0, 100) for i in range(10)])
        task_challenges = [
            TaskChallenge(
                redis_root=redis_root,
                task_id=task_id
            ).save()
            for task_id in tasks_ids
        ]
        many_to_many_check_instance = redis_root.create(
            ManyToManyCheckModel,
            task_challenges=task_challenges
        )
        # Check really created
        many_to_many_check_instances_qs = redis_root.get(ManyToManyCheckModel)
        if len(many_to_many_check_instances_qs) != 1:
            have_exception = True
        else:
            many_to_many_check_instance = many_to_many_check_instances_qs[0]
            if many_to_many_check_instance['task_challenges'] != task_challenges:
                have_exception = True
    except BaseException as ex:
        print(ex)
        have_exception = True
    
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def save_override_test(connection_pool, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        connection_pool=connection_pool,
        ignore_deserialization_errors=True,
    )
    have_exception = False
    try:
        instance_1 = redis_root.create(ModelWithOverriddenSave)
        instance_2 = redis_root.create(ModelWithOverriddenSave)
        if instance_1['multiplied_max_field'] * 2 != instance_2['multiplied_max_field']:
            have_exception = True
    except BaseException as ex:
        print(ex)
        have_exception = True
    
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def performance_test(connection_pool, prefix):
    have_exception = False
    try:
        
        def run_test(count, model):
            
            def test(count, model, **test_params):
                real_test_params = {
                    'use_keys': True,
                    'use_non_blocking': True
                }
                for key in real_test_params.copy():
                    if key in test_params.keys():
                        real_test_params[key] = test_params[key]
                
                def create_instances(redis_root, count, use_non_blocking, model):
                    
                    if use_non_blocking:
                        started_in = datetime.datetime.now()
                        results = [
                            redis_root.create_nb(model)
                            for i in range(count)
                        ]
                        ended_in = datetime.datetime.now()
                    else:
                        started_in = datetime.datetime.now()
                        results = [
                            redis_root.create(model)
                            for i in range(count)
                        ]
                        ended_in = datetime.datetime.now()
                    
                    time_took = (ended_in - started_in).total_seconds()
                    fields_count = len(results[0].keys()) * count
                    clean_db_after_test(connection_pool, prefix)
                    return [time_took, count, fields_count]
                
                redis_root = RedisRoot(
                    prefix=prefix,
                    connection_pool=connection_pool,
                    ignore_deserialization_errors=True,
                    use_keys=real_test_params['use_keys']
                )
                
                test_result = create_instances(redis_root, count, real_test_params['use_non_blocking'], model)
                
                return test_result
            
            test_confs = [
                {
                    'use_keys': False,
                    'use_non_blocking': False,
                },
                {
                    'use_keys': False,
                    'use_non_blocking': True,
                },
                {
                    'use_keys': True,
                    'use_non_blocking': False,
                },
                {
                    'use_keys': True,
                    'use_non_blocking': True,
                },
            
            ]
            
            test_confs_results = [
                test(count, model, **test_conf)
                for test_conf in test_confs
            ]
            
            print(f'\n\n\n'
                  f'Performance test results on your machine:\n'
                  f'Every test creates {test_confs_results[0][1]} instances ({test_confs_results[0][2]} fields) of {model.__name__} model,\n'
                  f'Here is the results:\n'
                  f'\n')
            
            min_time = min(list(map(lambda result: result[0], test_confs_results)))
            min_conf_text = ''
            for i, test_confs_result in enumerate(test_confs_results):
                test_conf_text = ", ".join([f"{k} = {v}" for k, v in test_confs[i].items()])
                print(f'Configuration: {test_conf_text} took {test_confs_result[0]}s')
                if test_confs_result[0] == min_time:
                    min_conf_text = test_conf_text
            print(f'\n\n'
                  f'The best configuration: {min_conf_text}\n')
        
        count = 1000
        model = TaskChallenge
        run_test(count, model)
    except BaseException as ex:
        print(ex)
        have_exception = True
    
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def run_tests():
    connection_pool = redis.ConnectionPool(
        host=os.environ['REDIS_HOST'],
        port=os.environ['REDIS_PORT'],
        db=0,
        decode_responses=True
    )
    tests = [
        basic_test,
        auto_reg_test,
        no_connection_pool_test,
        choices_test,
        order_test,
        filter_test,
        functions_like_defaults_test,
        redis_foreign_key_test,
        update_test,
        delete_test,
        save_consistency_test,
        meta_ttl_test,
        use_keys_test,
        list_test,
        dict_test,
        non_blocking_test,
        foreign_key_test,
        many_to_many_test,
        save_override_test,
        performance_test,
    ]
    results = []
    started_in = datetime.datetime.now()
    print('STARTING TESTS\n')
    for i, test in enumerate(tests):
        print(f'Starting {int(i + 1)} test: {test.__name__.replace("_", " ")}')
        test_started_in = datetime.datetime.now()
        result = not test(connection_pool, test.__name__)
        test_ended_in = datetime.datetime.now()
        test_time = (test_ended_in - test_started_in).total_seconds()
        print(f'{result = } / {test_time}s\n')
        results.append(result)
    ended_in = datetime.datetime.now()
    time = (ended_in - started_in).total_seconds()
    success_message = 'SUCCESS' if all(results) else 'FAILED'
    print('\n'
          f'{success_message}!\n')
    results_success_count = 0
    for i, result in enumerate(results):
        result_message = 'SUCCESS' if result else 'FAILED'
        print(f'Test {(i + 1)}/{len(results)}: {result_message} ({tests[i].__name__.replace("_", " ")})')
        if result:
            results_success_count += 1
    print(f'\n'
          f'{results_success_count} / {len(results)} tests ran successfully\n'
          f'All tests completed in {time}s\n')
    
    return all(results)


if __name__ == '__main__':
    results = run_tests()
    if not results:
        sys.exit(1)

```


### Output

```
STARTING TESTS

Starting 1 test: basic test
result = True / 0.017655s

Starting 2 test: auto reg test
result = True / 0.002688s

Starting 3 test: no connection pool test
2021-09-17 13:33:42.915213 - RedisRoot: No connection_pool provided, trying default config...
result = True / 0.003571s

Starting 4 test: choices test
result = True / 0.001307s

Starting 5 test: order test
result = True / 0.005999s

Starting 6 test: filter test
result = True / 0.019395s

Starting 7 test: functions like defaults test
result = True / 0.003462s

Starting 8 test: redis foreign key test
result = True / 0.006697s

Starting 9 test: update test
result = True / 0.003751s

Starting 10 test: delete test
result = True / 0.006936s

Starting 11 test: save consistency test
result = True / 6.009583s

Starting 12 test: meta ttl test
result = True / 6.010543s

Starting 13 test: use keys test
Keys usage gives +32.47% efficiency
result = True / 1.348907s

Starting 14 test: list test
result = True / 0.002379s

Starting 15 test: dict test
result = True / 0.002316s

Starting 16 test: non blocking test
Non blocking gives +195.91% efficiency
result = True / 13.0517s

Starting 17 test: foreign key test
result = True / 0.00598s

Starting 18 test: many to many test
result = True / 0.033524s

Starting 19 test: save override test
result = True / 0.003881s

Starting 20 test: performance test



Performance test results on your machine:
Every test creates 1000 instances (6000 fields) of TaskChallenge model,
Here is the results:


Configuration: use_keys = False, use_non_blocking = False took 40.92255s
Configuration: use_keys = False, use_non_blocking = True took 0.234719s
Configuration: use_keys = True, use_non_blocking = False took 31.373307s
Configuration: use_keys = True, use_non_blocking = True took 0.242484s


The best configuration: use_keys = False, use_non_blocking = True

result = True / 73.106303s


SUCCESS!

Test 1/20: SUCCESS (basic test)
Test 2/20: SUCCESS (auto reg test)
Test 3/20: SUCCESS (no connection pool test)
Test 4/20: SUCCESS (choices test)
Test 5/20: SUCCESS (order test)
Test 6/20: SUCCESS (filter test)
Test 7/20: SUCCESS (functions like defaults test)
Test 8/20: SUCCESS (redis foreign key test)
Test 9/20: SUCCESS (update test)
Test 10/20: SUCCESS (delete test)
Test 11/20: SUCCESS (save consistency test)
Test 12/20: SUCCESS (meta ttl test)
Test 13/20: SUCCESS (use keys test)
Test 14/20: SUCCESS (list test)
Test 15/20: SUCCESS (dict test)
Test 16/20: SUCCESS (non blocking test)
Test 17/20: SUCCESS (foreign key test)
Test 18/20: SUCCESS (many to many test)
Test 19/20: SUCCESS (save override test)
Test 20/20: SUCCESS (performance test)

20 / 20 tests ran successfully
All tests completed in 99.646971s

```