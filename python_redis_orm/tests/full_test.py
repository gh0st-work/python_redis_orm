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
            max_value = max(map(lambda instance: instance['multiplied_max_field'], all_instances))
            new_value = max_value * 2
        self.set(multiplied_max_field=new_value)
        return super().save()


class SomeAbstractModel(RedisModel):
    abstract_field = RedisString(default='hello')


class InheritanceTestModel(SomeAbstractModel):
    some_field = RedisBool(default=True)


def clean_db_after_test(connection_pool, prefix):
    redis_instance = redis.Redis(connection_pool=connection_pool)
    keys_to_delete = [
        *list(redis_instance.keys(f'{prefix}*')),
        *list(redis_instance.keys(f'*{prefix}')),
        *list(redis_instance.keys(f'*{prefix}*')),
    ]
    if keys_to_delete:
        redis_instance.delete(*keys_to_delete)


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
        count = 5
        for i in range(count):
            TaskChallenge(
                redis_root=redis_root,
                status='in_work',
            ).save()
        task_challenges_without_keys = redis_root.get(TaskChallenge)
        task_challenges_with_keys = redis_root.get(TaskChallenge, return_dict=True)
        have_exception = False
        if not len(task_challenges_without_keys) == count:
            have_exception = True
        if not len(task_challenges_with_keys) == count:
            have_exception = True
        else:
            if not task_challenges_with_keys.keys():
                have_exception = True
            else:
                if len(list(task_challenges_with_keys.keys())) != len(task_challenges_without_keys):
                    have_exception = True
    except BaseException as ex:
        have_exception = True
        print(ex)
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
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        task_challenges_with_same_token = redis_root.get(BotSession, session_token=same_token, created__gte=yesterday)
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
        ignore_deserialization_errors=False
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
    
    try:
        
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
            if set([
                task_challenge['id']
                for task_challenge in many_to_many_check_instance['task_challenges']
            ]) != set([
                task_challenge['id']
                for task_challenge in task_challenges
            ]):
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


def inheritance_test(connection_pool, prefix):
    redis_root = RedisRoot(
        prefix=prefix,
        connection_pool=connection_pool,
        ignore_deserialization_errors=False,
    )
    have_exception = False
    try:
        instance_1 = redis_root.create(InheritanceTestModel)
        instance_2 = redis_root.create(InheritanceTestModel, abstract_field='nice')
        instance_1 = redis_root.get(InheritanceTestModel, abstract_field='hello')
        instance_2 = redis_root.get(InheritanceTestModel, abstract_field='nice')
        if not instance_1 or not instance_2:
            have_exception = True
    except BaseException as ex:
        print(ex)
        have_exception = True
    
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def performance_test(connection_pool, prefix):
    have_exception = False
    
    try:
        
        def run_test(count):
            
            def test(count, **test_params):
                real_test_params = test_params
                
                def run_exact_test(redis_root, count, use_non_blocking):
                    
                    update_data = [
                        redis_root.create(TaskChallenge, account_checks_count=100)
                        for i in range(count)
                    ]
                    
                    started_in = datetime.datetime.now()
                    if use_non_blocking:
                        
                        create_results = [
                            redis_root.create_nb(TaskChallenge)
                            for i in range(count)
                        ]
                        update_results = [
                            redis_root.update_nb(TaskChallenge, update_data, account_checks_count=200)
                            for i in range(count)
                        ]
                    else:
                        create_results = [
                            redis_root.create(TaskChallenge)
                            for i in range(count)
                        ]
                        update_results = [
                            redis_root.update(TaskChallenge, update_data, account_checks_count=200)
                            for i in range(count)
                        ]
                    ended_in = datetime.datetime.now()
                    
                    time_took = (ended_in - started_in).total_seconds()
                    fields_count = len(results[0].keys()) * count
                    clean_db_after_test(connection_pool, prefix)
                    return [time_took, count, fields_count]
                
                print(prefix)
                redis_root = RedisRoot(
                    prefix=prefix,
                    connection_pool=connection_pool,
                    ignore_deserialization_errors=True,
                    use_keys=real_test_params['use_keys'],
                    solo_usage=real_test_params['solo_usage'],
                    save_type=('fields' if real_test_params['use_fields'] else 'instances'),
                )
                
                test_result = run_exact_test(redis_root, count, real_test_params['use_non_blocking'])
                
                return test_result
            
            test_confs = []
            
            for use_keys_variant in [True, False]:
                for use_non_blocking_variant in [True, False]:
                    for solo_usage_variant in [True, False]:
                        for use_fields_variant in [True, False]:
                            test_confs.append({
                                'use_keys': use_keys_variant,
                                'use_non_blocking': use_non_blocking_variant,
                                'solo_usage': solo_usage_variant,
                                'use_fields': use_fields_variant,
                            })
            
            test_confs_results = [
                test(count, **test_conf)
                for test_conf in test_confs
            ]
            
            print(f'\n\n\n'
                  f'The performance test results on your machine:\n'
                  f'Every test creates and updates {test_confs_results[0][1]} instances ({test_confs_results[0][2]} fields) of TaskChallenge model,\n'
                  f'Here are the results:\n'
                  f'\n')
            
            min_time = min(list(map(lambda result: result[0], test_confs_results)))
            min_conf_text = ''
            for i, test_confs_result in enumerate(test_confs_results):
                test_conf_text = ", ".join([f"{k} = {v}" for k, v in test_confs[i].items()])
                print(f'The configuration: {test_conf_text} took {test_confs_result[0]}s')
                if test_confs_result[0] == min_time:
                    min_conf_text = test_conf_text
            print(f'\n\n'
                  f'The best configuration: {min_conf_text}\n')
        
        count = 1000
        run_test(count)
    except BaseException as ex:
        print(ex)
        have_exception = True
    
    clean_db_after_test(connection_pool, prefix)
    return have_exception


def flood_performance_test(connection_pool, prefix):
    have_exception = False
    redis_root = RedisRoot(
        prefix=prefix,
        connection_pool=connection_pool,
        ignore_deserialization_errors=True,
        use_keys=True
    )
    clean_db_after_test(connection_pool, prefix)
    execs_count = 6
    count = 100
    
    def run_flood_test(use_fields):
        clean_db_after_test(connection_pool, prefix)
        completion_time_list = []
        for exec in range(execs_count):
            time_start = datetime.datetime.now()
            for i in range(count):
                task_challenges_qs = redis_root.create(TaskChallenge, account_checks_count=i)
            for i in range(count):
                task_challenges_qs = redis_root.get(TaskChallenge, account_checks_count=i)
            time_end = datetime.datetime.now()
            completion_time_list.append((time_end - time_start).total_seconds())
        first_test = completion_time_list[0]
        last_test = completion_time_list[-1]
        print(f'\n'
              f'Use fields: {use_fields}\n'
              f'0 -> {(execs_count - 1) * count} stored instances changes execution time like:\n'
              f'{"s -> ".join((str(completion_time) for completion_time in completion_time_list))}s\n'
              f'+{(last_test / first_test - 1) * 100}% of time spent')
        clean_db_after_test(connection_pool, prefix)
    
    print('Running test, that floods your redis database and checking create and filter time...')
    run_flood_test(True)
    run_flood_test(False)
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
        use_keys_test,
        list_test,
        dict_test,
        non_blocking_test,
        foreign_key_test,
        many_to_many_test,
        save_override_test,
        inheritance_test,
        performance_test,
        flood_performance_test,
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