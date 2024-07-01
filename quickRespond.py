import os
import re
import json
import asyncio
import time

from core.util import TimeRecorder, any_match
from core.database.bot import Admin
from core import AmiyaBotPluginInstance
from amiyabot import Message, Chain, event_bus
from amiyabot.builtin.messageChain import element
from .cacheControl import log, Symbol, match_filename, write_cache_and_read, get_cache_list, search_char_by_text
from .cacheGenerate import GenerateStatus, batch_generate

curr_dir = os.path.dirname(__file__)


class quickRespondInstance(AmiyaBotPluginInstance):
    def install(self):
        asyncio.create_task(Symbol.init_item_symbol())
        show_clean()
        Config.update()


@event_bus.subscribe('gameDataInitialized')
def update(_):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        bot.install()


bot = quickRespondInstance(
    name='查询快速响应',
    version='2.9.1',
    plugin_id='kkss-quick-respond',
    plugin_type='',
    description='提升查询类功能的响应速度',
    document=f'{curr_dir}/README.md',
    global_config_default=f'{curr_dir}/default.json',
    global_config_schema=f'{curr_dir}/schema.json',
)


class Config:
    render_time = 200
    code_limit = 512
    hash_limit = 64
    weibo_expire = 7
    clear_interval = 60
    show_schedule = False
    force_refresh = False
    target_amount = 0
    interval = 4
    show_debug = False
    width_limit = 0

    @staticmethod
    def update():
        try:
            Config.render_time = int(bot.get_config('renderTime'))
            Config.code_limit = int(bot.get_config('codeLimit'))
            Config.hash_limit = int(bot.get_config('hashLimit'))
            Config.weibo_expire = int(bot.get_config('weiboExpire'))
            Config.clear_interval = float(bot.get_config('clearInterval'))
            Config.show_schedule = bool(bot.get_config('showSchedule'))
            Config.force_refresh = bool(bot.get_config('forceRefresh'))
            Config.target_amount = int(bot.get_config('targetAmount'))
            Config.interval = float(bot.get_config('interval'))  
            Config.show_debug = bool(bot.get_config('showDebug'))
            Config.width_limit = int(bot.get_config('widthLimit'))

        except TypeError:
            log.warning('控制台配置有误, 请检查')

Config.update()
            

@bot.message_before_send
async def _(chain: Chain, factory_name: str, _):

    if type(chain) is not Chain:
        log.warning('不支持的消息类型')
        return chain
    
    try:
        is_refresh = bool(any_match(chain.data.text, ['刷新','重置','重制']))
    except AttributeError:
        return chain

    for action in chain.chain:
        if type(action) is element.Html:
            
            if Config.show_debug:
                debug_dir='resource/plugins/generateCache/debug'
                if not os.path.exists(debug_dir):
                    os.makedirs(debug_dir)
                with open(f'{debug_dir}/action_data.json', 'w', encoding='utf-8') as f:
                    json.dump(action.data, f, ensure_ascii=False)
                    
            if file_name := await match_filename(action=action, factory_name=factory_name):
                Config.update()
                render_time = Config.render_time if Config.render_time > 500 else 500
                image_content, _ = await write_cache_and_read(action, file_name, is_refresh, render_time)

                chain.chain.remove(action)
                chain.chain.append(element.Image(content=image_content))

    return chain


async def cache_verify(data: Message):
    if '缓存' not in data.text:
        return False

    if '生成' in data.text:
        return False

    if not bool(Admin.get_or_none(account=data.user_id)):
        return False

    key = any_match(data.text, ['清除', '查看'])

    if key:
        return True, 6, key


@bot.on_message(verify=cache_verify)
async def _(data: Message):

    key = data.verify.keypoint
    cache_dir = 'resource/plugins/generateCache'
    cacheList, occupies = await get_cache_list(cache_dir)
    cacheListH, occupiesH = await get_cache_list(cache_dir+'/hash')

    if key == '查看':
        Config.update()
        amount = len(cacheList)
        amountH = len(cacheListH)

        content = ''
        if Config.code_limit:
            content = f'● 标准缓存数量: {amount} \n占用 {occupies} MB, 上限 {Config.code_limit} MB \n'
            if occupies > Config.code_limit: 
                content += '(已超过上限, 稍后将自动清理) \n'       
        else: 
            content += f'● 标准缓存数量: {amount} \n占用 {occupies} MB (已禁用自动清理) \n'
        
        if Config.hash_limit:
            content += f'● 随机缓存数量: {amountH} \n占用 {occupiesH} MB, 上限 {Config.hash_limit} MB'
            if occupiesH > Config.hash_limit:
                content += '(已超过上限, 稍后将自动清理) \n'
        else:
            content += f'● 随机缓存数量: {amountH} \n占用 {occupiesH} MB (已禁用自动清理) \n'

        return Chain(data, at=False).text(content)

    if key == '清除':

        if '随机' in data.text:

            cache_dir += '/hash'
            for fileName in cacheListH:
                filePath = f'{cache_dir}/{fileName}'
                os.remove(filePath)

            return Chain(data, at=False).text('已清空随机缓存')

        if '全部' in data.text:
            wait = await data.wait(Chain(data, at=False).text('要清除全部查询缓存, 请回复 确定'), force=False)
            if wait and wait.text == '确定':

                for fileName in cacheList:
                    filePath = f'{cache_dir}/{fileName}'
                    os.remove(filePath)

                cache_dir += '/hash'
                for fileName in cacheListH:
                    filePath = f'{cache_dir}/{fileName}'
                    os.remove(filePath)

                return Chain(data, at=False).text('已清除全部查询缓存')
        
        if '敌人' in data.text or '敌方' in data.text:   
            for fileName in cacheList:
                if not fileName.startswith('enemy'):
                    continue
                filePath = f'{cache_dir}/{fileName}'
                os.remove(filePath)
            return Chain(data, at=False).text('已清空所有敌方单位缓存')

        if '关卡' in data.text:   
            for fileName in cacheList:
                if not fileName.startswith('stage'):
                    continue
                filePath = f'{cache_dir}/{fileName}'
                os.remove(filePath)
            return Chain(data, at=False).text('已清空所有关卡缓存')
        
        name = await search_char_by_text(data.text)

        if not name:
            return Chain(data).markdown(
                '-  `兔兔查看缓存`: 查看已缓存的图片数量和占用空间 \n'
                '-  `兔兔清除缓存 [干员名]`: 清除某个干员的相关缓存 \n'
                '-  `兔兔清除敌方缓存`: 清除所有敌方单位缓存 \n'
                '-  `兔兔清除关卡缓存`: 清除所有关卡缓存 \n'
                '-  `兔兔清除随机缓存`: 清除随机缓存 \n'
                '-  `兔兔清除全部缓存`: 清除全部缓存 \n'
            )

        charCode = Symbol.Char.name_to_code.get(name)

        amount = 0
        for fileName in cacheList:
            filePath = f'{cache_dir}/{fileName}'

            if fileName.startswith(charCode):
                os.remove(filePath)
                amount += 1

        if not amount:
            return Chain(data).text(f'没有干员 {name} 的缓存')

        return Chain(data).text(f'已清除干员 {name} 的 {amount} 个缓存')
    

def show_clean():
    clean_list = []
    if Config.code_limit > 0:
        clean_list.append('标准缓存')
    if Config.hash_limit > 0:
        clean_list.append('随机缓存')
    if Config.weibo_expire  > 0:
        clean_list.append('微博缓存')

    if clean_list:
        log.info(f'缓存自动清理已启用, 范围: {" ".join([i for i in clean_list])}')
    else:
        log.warning('缓存自动清理已禁用')


@bot.timed_task(each=Config.clear_interval*60)
async def _(_):
    Config.update()

    if Config.code_limit > 0:
        log.info('开始清理标准缓存...')

        cache_dir = 'resource/plugins/generateCache'
        cacheList, occupies = await get_cache_list(cache_dir)

        if Config.code_limit:
            for file_name in cacheList:
                if occupies < Config.code_limit:
                    break

                file_path = f'{cache_dir}/{file_name}'
                occupies -= os.path.getsize(file_path)/1024/1024
                os.remove(file_path)

    if Config.hash_limit > 0:
        log.info('开始清理随机缓存...')

        cache_dir = 'resource/plugins/generateCache/hash'
        cacheListH, occupiesH = await get_cache_list(cache_dir)

        if Config.hash_limit:
            for file_name in cacheListH:
                if occupiesH < Config.hash_limit:
                    break

                file_path = f'{cache_dir}/{file_name}'
                occupiesH -= os.path.getsize(file_path)/1024/1024
                os.remove(file_path)

    if Config.weibo_expire > 0:
        cache_dir = 'log/weibo'
        if os.path.exists(cache_dir):
            log.info('开始清理微博缓存...')
       
        for file_name in os.listdir(cache_dir):
            file_path = f'{cache_dir}/{file_name}'

            if os.path.isdir(file_path):
                continue

            if os.path.splitext(file_path)[1] != '.jpg':
                continue

            file_time = os.path.getmtime(file_path)
            if time.time() - file_time > Config.weibo_expire*24*60*60:
                os.remove(file_path)


async def generate_verify(data: Message):

    if '缓存' not in data.text:
        return False

    if not bool(Admin.get_or_none(account=data.user_id)):
        return False

    if '生成' in data.text:
        return True, 5


@bot.on_message(verify=generate_verify)
async def _(data:Message):
    Config.update()
    r = re.compile(r'\D*(\d+).*$').match(data.text_digits)
    if r:
        target_amount = int(r.group(1))
        await data.send(Chain(data).text(f'开始生成, 目标数量: {target_amount}  \n'
        f'强制刷新: {"开启" if Config.force_refresh else "关闭"}  \n'
        f'发送 取消/停止 可中止生成'))

    else:
        target_amount = Config.target_amount
        await data.send(Chain(data).text(f'开始生成, 未指定目标数量, 将使用默认值: {target_amount}  \n'
        f'强制刷新: {"开启" if Config.force_refresh else "关闭"}  \n'
        f'发送 取消/停止 可中止生成'))

    log.info('正在初始化生成...')
    
    GenerateStatus.alive = True
    time_rec = TimeRecorder()
    
    generate_opt = {
        'render_time': Config.render_time if Config.render_time > 1000 else 1000,
        'refresh': Config.force_refresh,
        'interval': Config.interval,
        'width_limit': Config.width_limit,
        'show_schedule': Config.show_schedule,
    }

    res = await batch_generate(target_amount, generate_opt)

    if res[0] == -1:
        return Chain(data).text(f'所有干员缓存均已存在')
    
    if res[0] == -2:
            return Chain(data).text(f'干员查询插件未安装或不支持, 生成失败')
        
    return Chain(data).text(f'成功生成 {res[0]} 个干员的 {res[1]} 个缓存, 耗时{time_rec.total()}')


async def stop_verify(data:Message):
    if not GenerateStatus.alive:
        return False

    if len(data.text) > 4:
        return False

    if not any_match(data.text, ['停止','取消']):
        return False

    if bool(Admin.get_or_none(account=data.user_id)):
        return True, 5


@bot.on_message(verify=stop_verify, check_prefix=False)
async def _(data:Message):
    GenerateStatus.alive = False
    log.info('正在停止生成...')
    return Chain(data).text('正在停止生成...')


