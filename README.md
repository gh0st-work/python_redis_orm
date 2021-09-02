# python-redis-orm

## **Python Redis ORM, turns redis to a fully functional in-memory database, inspired by Django ORM**

For one project, I needed to work with redis, but redis-py provides a minimum level of work with redis. I didn't find any Django-like ORM for redis, so I wrote this library, then there will be a port to Django.

### Working with this library, you are expected:

- Fully works in 2021
- Django-like architecture
- Easy adaptation to your needs
- Adequate informational messages and error messages
- Built-in RedisRoot class that stores specified models, with:
    - redis_instance setting - your redis connection (from redis-py)
    - prefix setting - prefix of this RedisRoot to be stored in redis
    - ignore_deserialization_errors setting - do not raise errors, while deserealizing data
    - save_consistency setting - show structure-first data
    - economy setting - to not return full data and save some requests (usually, speeds up your app on 80%)
- 6 built-in types of fields:
    - RedisField - base class for nesting
    - RedisString - string
    - RedisNumber - int or float
    - RedisId - instances IDs
    - RedisDateTime - for work with date and time, via python datetime
    - RedisForeignKey - for links to other redis models
- All fields supports:
    - Automatically serialization and deserialization
    - TTL (Time To Live)
    - Default values
    - Providing functions to default values
    - Allow null values setting
    - Choices
- Built-in RedisModel class, with:
    - All fields that you want
    - TTL (Time To Live), applies if no ttl on field
- CRUD (Create Read Update Delete), in our variation: save, filter, order, update, delete:
    - example_instance = ExampleModel(example_field='example_data').save() - to create an instance and get its JSON
    - filtered_example_instances = redis_root.get(ExampleModel, example_field='example_data') - to get all ExampleModel instances with example_field filter and get JSON
    - ordered_instances = redis_root.order(filtered_example_instances, '-id') - to get ordered filtered_example_instances by id ('-' for reverse)
    - updated_example_instances = redis_root.update(ExampleModel, ordered_instances, example_field='another_example_data') - to update all ordered_instances example_field with value 'another_example_data' and get them in JSON
    - redis_root.delete(ExampleModel, updated_example_instances) - to delete updated_example_instances


# Installation
`pip install python-redis-orm`

[Here is PyPI](https://pypi.org/project/python-redis-orm/)

Obviously, you need to install and run redis server on your machine, we support v3+ 


# Usage

All features:
[full_test.py](https://github.com/gh0st-work/python_redis_orm/blob/master/python_redis_orm/tests/full_test.py)
```python
import datetime
import random
from time import sleep
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
    redis_number_with_ttl = RedisNumber(default=0, null=False, ttl=5)


class MetaTtlCheckModel(RedisModel):
    redis_number = RedisNumber(default=0, null=False)

    class Meta:
        ttl = 5


# class DjangoForeignKeyModel(RedisModel):
#     foreign_key = RedisDjangoForeignKey(model=Proxy)


def get_redis_instance():
    REDIS_HOST = 'localhost'
    REDIS_PORT = 6379
    redis_instance = redis.StrictRedis(
        decode_responses=True,
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=0,
    )
    return redis_instance


def clean_db_after_test(redis_instance, prefix):
    for key in redis_instance.scan_iter(f'{prefix}:*'):
        redis_instance.delete(key)


def basic_test(redis_instance, prefix):
    try:
        redis_root = RedisRoot(
            prefix=prefix,
            redis_instance=redis_instance,
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
    clean_db_after_test(redis_instance, prefix)
    return have_exception


def auto_reg_test(redis_instance, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        redis_instance=redis_instance,
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
    clean_db_after_test(redis_instance, prefix)
    return have_exception


def no_redis_instance_test(*args, **kwargs):
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
        clean_db_after_test(redis_root.redis_instance, redis_root.prefix)
    except BaseException as ex:
        have_exception = True
    return have_exception


def choices_test(redis_instance, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        redis_instance=redis_instance,
        ignore_deserialization_errors=True
    )
    task_challenge_1 = TaskChallenge(
        redis_root=redis_root,
        status='bruh',
    )
    try:
        task_challenge_1.save()
        task_challenges = redis_root.get(TaskChallenge)
        have_exception = True
    except BaseException as ex:
        have_exception = False
    clean_db_after_test(redis_instance, prefix)
    return have_exception


def order_test(redis_instance, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        redis_instance=redis_instance,
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
    clean_db_after_test(redis_instance, prefix)
    return have_exception


def filter_test(redis_instance, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        redis_instance=redis_instance,
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

    clean_db_after_test(redis_instance, prefix)
    return have_exception


def update_test(redis_instance, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        redis_instance=redis_instance,
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

    clean_db_after_test(redis_instance, prefix)
    return have_exception


def functions_like_defaults_test(redis_instance, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        redis_instance=redis_instance,
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

    clean_db_after_test(redis_instance, prefix)
    return have_exception


def redis_foreign_key_test(redis_instance, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        redis_instance=redis_instance,
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

    clean_db_after_test(redis_instance, prefix)
    return have_exception


# def django_foreign_key_test(redis_instance, prefix):
#     redis_root = RedisRoot(
#         prefix=prefix,
#         redis_instance=redis_instance,
#         ignore_deserialization_errors=True
#     )
#     have_exception = True
#     try:
#         proxy = Proxy.objects.all()[0]
#         django_foreign_key_model = DjangoForeignKeyModel(
#             redis_root=redis_root,
#             foreign_key=proxy,
#         ).save()
#         django_foreign_key_models = redis_root.get(DjangoForeignKeyModel)
#         django_foreign_key_model = redis_root.order(django_foreign_key_models, '-id')[0]
#         if django_foreign_key_model['foreign_key'] == proxy:
#             have_exception = False
#     except BaseException as ex:
#         print(ex)
#     clean_db_after_test(redis_instance, prefix)
#     return have_exception


def delete_test(redis_instance, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        redis_instance=redis_instance,
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

    clean_db_after_test(redis_instance, prefix)
    return have_exception


def ttl_test(redis_instance, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        redis_instance=redis_instance,
        ignore_deserialization_errors=True
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
                    if 'redis_number_with_ttl' not in ttl_check_model.keys():
                        have_exception = False
    except BaseException as ex:
        print(ex)

    clean_db_after_test(redis_instance, prefix)
    return have_exception


def save_consistency_test(redis_instance, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        redis_instance=redis_instance,
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

    clean_db_after_test(redis_instance, prefix)
    return have_exception


def meta_ttl_test(redis_instance, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        redis_instance=redis_instance,
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

    clean_db_after_test(redis_instance, prefix)
    return have_exception


def economy_test(redis_instance, prefix):
    have_exception = True
    try:

        redis_root = RedisRoot(
            prefix=prefix,
            redis_instance=redis_instance,
            ignore_deserialization_errors=True,
            economy=True
        )
        started_in_economy = datetime.datetime.now()
        for i in range(10):
            task_challenge_1 = TaskChallenge(
                redis_root=redis_root,
                status='in_work',
            ).save()
            redis_root.update(TaskChallenge, task_challenge_1, account_checks_count=1)
        ended_in_economy = datetime.datetime.now()
        economy_time = (ended_in_economy - started_in_economy).total_seconds()
        clean_db_after_test(redis_instance, prefix)

        redis_root = RedisRoot(
            prefix=prefix,
            redis_instance=redis_instance,
            ignore_deserialization_errors=True,
            economy=False
        )
        started_in_no_economy = datetime.datetime.now()
        for i in range(10):
            task_challenge_1 = TaskChallenge(
                redis_root=redis_root,
                status='in_work',
            ).save()
            redis_root.update(TaskChallenge, task_challenge_1, account_checks_count=1)
        ended_in_no_economy = datetime.datetime.now()
        no_economy_time = (ended_in_no_economy - started_in_no_economy).total_seconds()
        clean_db_after_test(redis_instance, prefix)
        economy_percent = round((no_economy_time / economy_time - 1) * 100, 2)
        economy_symbol = ('+' if economy_percent > 0 else '-')
        print(f'Economy gives {economy_symbol}{economy_percent}% efficiency')
        if economy_symbol == '+':
            have_exception = False
    except BaseException as ex:
        print(ex)

    clean_db_after_test(redis_instance, prefix)
    return have_exception


def run_tests():
    redis_instance = get_redis_instance()
    tests = [
        basic_test,
        auto_reg_test,
        no_redis_instance_test,
        choices_test,
        order_test,
        filter_test,
        functions_like_defaults_test,
        redis_foreign_key_test,
        # django_foreign_key_test,
        update_test,
        delete_test,
        ttl_test,
        save_consistency_test,
        meta_ttl_test,
        economy_test,
    ]
    results = []
    started_in = datetime.datetime.now()
    print('STARTING TESTS\n')
    for i, test in enumerate(tests):
        print(f'Starting {int(i + 1)} test: {test.__name__.replace("_", " ")}')
        test_started_in = datetime.datetime.now()
        result = not test(redis_instance, test.__name__)
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


if __name__ == '__main__':
    run_tests()

```