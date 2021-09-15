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
        task_challenge_1.save()
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


def economy_test(connection_pool, prefix):
    have_exception = True
    try:
        
        redis_root = RedisRoot(
            prefix=prefix,
            connection_pool=connection_pool,
            ignore_deserialization_errors=True,
            economy=True
        )
        started_in_economy = datetime.datetime.now()
        tests_count = 100
        for i in range(tests_count):
            task_challenge_1 = TaskChallenge(
                redis_root=redis_root,
                status='in_work',
            ).save()
            redis_root.update(TaskChallenge, task_challenge_1, account_checks_count=1)
        ended_in_economy = datetime.datetime.now()
        economy_time = (ended_in_economy - started_in_economy).total_seconds()
        clean_db_after_test(connection_pool, prefix)
        
        redis_root = RedisRoot(
            prefix=prefix,
            connection_pool=connection_pool,
            ignore_deserialization_errors=True,
            economy=False
        )
        started_in_no_economy = datetime.datetime.now()
        for i in range(tests_count):
            task_challenge_1 = TaskChallenge(
                redis_root=redis_root,
                status='in_work',
            ).save()
            redis_root.update(TaskChallenge, task_challenge_1, account_checks_count=1)
        ended_in_no_economy = datetime.datetime.now()
        no_economy_time = (ended_in_no_economy - started_in_no_economy).total_seconds()
        clean_db_after_test(connection_pool, prefix)
        economy_percent = round((no_economy_time / economy_time - 1) * 100, 2)
        economy_symbol = ('+' if economy_percent > 0 else '')
        print(f'Economy gives {economy_symbol}{economy_percent}% efficiency')
        if economy_symbol == '+':
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


def async_test(connection_pool, prefix):
    have_exception = True
    try:
        
        async def async_task(data_count, use_async=True):
            redis_roots = []
            connection_pool = redis.ConnectionPool(
                host=os.environ['REDIS_HOST'],
                port=os.environ['REDIS_PORT'],
                db=0,
                decode_responses=True
            )
            for i in range(data_count):
                redis_root = RedisRoot(
                    prefix=prefix,
                    connection_pool=connection_pool,
                    ignore_deserialization_errors=True
                )
                redis_roots.append(redis_root)
            
            async def create_list(redis_roots, redis_root_index, list_length):
                some_list = [random.choice('ABCDEF') for i in range(list_length)]
                redis_root = redis_roots[redis_root_index]
                list_check_model_instance = ListCheckModel(
                    redis_root=redis_root,
                    redis_list=some_list
                ).save()
                return {
                    'list': some_list,
                    'id': list_check_model_instance['id']
                }
            
            async def get_object_existence(redis_roots, redis_root_index, lists_with_ids):
                exists = False
                redis_root = redis_roots[redis_root_index]
                objects = redis_root.get(ListCheckModel, redis_list=lists_with_ids['list'])
                if objects:
                    if len(objects) == 1:
                        exists = objects[0]['id'] == lists_with_ids['id']
                return exists
            
            async def update_list(redis_roots, redis_root_index, lists_with_ids):
                result = False
                redis_root = redis_roots[redis_root_index]
                objects = redis_root.get(ListCheckModel, redis_list=lists_with_ids['list'])
                if objects:
                    if len(objects) == 1:
                        obj = objects[0]
                        new_list = deepcopy(lists_with_ids['list'])
                        new_list.append('check_value')
                        updated_obj = redis_root.update(ListCheckModel, obj, redis_list=new_list)
                        updated_objects = redis_root.get(ListCheckModel, redis_list=new_list)
                        if updated_objects:
                            if len(updated_objects) == 1:
                                result = updated_objects[0]['id'] == lists_with_ids['id']
                return result
            
            async def delete_list(redis_roots, redis_root_index, id):
                result = False
                redis_root = redis_roots[redis_root_index]
                objects = redis_root.get(ListCheckModel, id=id)
                if objects:
                    if len(objects) == 1:
                        obj = objects[0]
                        redis_root.delete(ListCheckModel, obj)
                        objects = redis_root.get(ListCheckModel, id=id)
                        if not objects:
                            result = True
                return result
            
            async def create_lists(lists_count, use_async=True):
                if use_async:
                    async_create_lists_tasks = [
                        create_list(redis_roots, i, i + 100)
                        for i in range(lists_count)
                    ]
                    list_of_lists_with_ids = await asyncio.gather(*async_create_lists_tasks)
                else:
                    list_of_lists_with_ids = [
                        await create_list(redis_roots, i, i + 100)
                        for i in range(lists_count)
                    ]
                return list_of_lists_with_ids
            
            async def get_objects_existence(list_of_lists_with_ids, use_async=True):
                if use_async:
                    async_get_object_by_list_tasks = [
                        get_object_existence(redis_roots, i, lists_with_ids)
                        for i, lists_with_ids in enumerate(list_of_lists_with_ids)
                    ]
                    list_of_results = await asyncio.gather(*async_get_object_by_list_tasks)
                else:
                    list_of_results = [
                        await get_object_existence(redis_roots, i, lists_with_ids)
                        for i, lists_with_ids in enumerate(list_of_lists_with_ids)
                    ]
                return list_of_results
            
            async def update_lists(list_of_lists_with_ids, use_async=True):
                if use_async:
                    async_update_list_tasks = [
                        update_list(redis_roots, i, lists_with_ids)
                        for i, lists_with_ids in enumerate(list_of_lists_with_ids)
                    ]
                    list_of_results = await asyncio.gather(*async_update_list_tasks)
                else:
                    list_of_results = [
                        await update_list(redis_roots, i, lists_with_ids)
                        for i, lists_with_ids in enumerate(list_of_lists_with_ids)
                    ]
                return list_of_results
            
            async def delete_lists(list_of_lists_with_ids, use_async=True):
                if use_async:
                    async_delete_list_tasks = [
                        delete_list(redis_roots, i, lists_with_ids['id'])
                        for i, lists_with_ids in enumerate(list_of_lists_with_ids)
                    ]
                    list_of_results = await asyncio.gather(*async_delete_list_tasks)
                else:
                    list_of_results = [
                        await delete_list(redis_roots, i, lists_with_ids)
                        for i, lists_with_ids in enumerate(list_of_lists_with_ids)
                    ]
                return list_of_results
            
            list_of_lists_with_ids = await create_lists(data_count, use_async)
            list_of_results = await get_objects_existence(list_of_lists_with_ids, use_async)
            if all(list_of_results):
                list_of_results = await update_lists(list_of_lists_with_ids, use_async)
                if all(list_of_results):
                    list_of_results = await delete_lists(list_of_lists_with_ids, use_async)
            return all(list_of_results)
        
        data_count = 10
        async_started_in = datetime.datetime.now()
        async_result = asyncio.run(async_task(data_count))
        async_ended_in = datetime.datetime.now()
        async_time = (async_ended_in - async_started_in).total_seconds()
        have_exception = not async_result
        sync_started_in = datetime.datetime.now()
        sync_result = asyncio.run(async_task(data_count, False))
        sync_ended_in = datetime.datetime.now()
        sync_time = (sync_ended_in - sync_started_in).total_seconds()
        
        async_percent = round((async_time / sync_time - 1) * 100, 2)
        async_symbol = ('+' if async_percent > 0 else '')
        print(f'Async gives {async_symbol}{async_percent}% efficiency')
    
    except BaseException as ex:
        print(ex)
    
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
        economy_test,
        use_keys_test,
        list_test,
        dict_test,
        async_test,
        foreign_key_test,
        many_to_many_test,
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
