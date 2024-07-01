import os
import re
import hashlib

from core.util import find_most_similar, remove_punctuation
from core.resource.arknightsGameData import ArknightsGameData
from typing import Any, List, Optional, Tuple, Union
from amiyabot.builtin.messageChain import element
from amiyabot.log import LoggerManager

curr_dir = os.path.dirname(__file__)

log = LoggerManager(' \b\b快速响应')


class Symbol:
    class Char:
        name_to_code = {}
        symbol_to_code = {}

    @classmethod
    async def init_item_symbol(cls):

        for name, item in ArknightsGameData.operators.items():
            r = re.search(r'char_(\d+)_(\w+)', item.id)
            if r:
                code = r.group(0)
                charSymbol = r.group(2)

                cls.Char.name_to_code[name] = code
                cls.Char.symbol_to_code[charSymbol] = code

            else:
                log.warning(f'无法识别干员 {name}')
        l = len(cls.Char.name_to_code)
        log.info(f'已注册 {l} 个对象')
        if l == 0:
            log.error('错误: 没有任何对象被注册. 这可能是因为gamedata未下载或解析失败')


def md5(obj: Any) -> str:
    m = hashlib.md5()
    m.update(str(obj).encode(encoding='utf-8'))
    return m.hexdigest()


async def search_char_by_text(text: str) -> Optional[str]:
    source = Symbol.Char.name_to_code.keys()

    res = find_most_similar(text, source)
    if res and remove_punctuation(res) in remove_punctuation(text):
        return res


async def get_char_code(template: str, data: str, factory_name: str) -> Optional[str]:
    effective_factory = [
        'amiyabot-arknights-operator-□',
        'amiyabot-arknights-operator',
        'arknights-operator-m&c',
        'arknights-operator-yb']
    if factory_name not in effective_factory:
        return None

    try:
        r = None
        symbol = ''
        string = ''
        if template == 'operatorInfo':
            string = data['info']['id']
            r = re.search(r'char_\d+_(\w+)', string)

        elif template == 'operatorCost':
            string = os.path.basename(data['skin'])
            r = re.search(r'char_\d+_(\w+)%\w+.png', string)

        elif template == 'skillsDetail':
            string = data['skills'][-1]['skill_no']
            r = re.search(r'skchr_(\w+)_\d', string)        

        elif template == 'operatorModule':
            string = data[0]['uniEquipId']
            r = re.search(r'uniequip_\d+_(\w+)', string)

        elif template == 'operatorToken':
            string = data['id']
            r = re.search(r'char_\d+_(\w+)', string)

        if r:
            symbol = r.group(1)
        
    except (TypeError, IndexError):
        log.warning(f'无法识别的干员')
        return

    try:
        code = Symbol.Char.symbol_to_code[symbol]
        if string and not code:
            log.warning(f'干员代号为空')
        return code
    
    except KeyError:
        return
        

async def get_other_code(template: str, data: dict, factory_name: str) -> Optional[str]:
    try:
        if template == 'enemy':
            return data['info']['enemyId']

        elif template == 'stage':
            difficulty = data['difficulty'] if data['diffGroup'] == 'NONE' else data['diffGroup']
            return 'stage_' + data['code'] + '-' + difficulty
        
    except KeyError:
        return
          

async def get_cache_list(cache_dir: str) -> Tuple[List, int]:

    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    space_occupies = 0
    cacheDict = {}
    for file_name in os.listdir(cache_dir):
        filePath = f'{cache_dir}/{file_name}'

        if os.path.isdir(filePath):
            continue

        if os.path.splitext(filePath)[1] != '.png':
            continue

        space_occupies += os.path.getsize(filePath)
        cacheDict[file_name] = int(os.path.getmtime(filePath))

    space_occupies = round(space_occupies / 1024 / 1024, 2)
    cacheList = sorted(cacheDict, key=cacheDict.get)

    return cacheList, space_occupies


async def match_filename(action: element.Html, factory_name: str=''):
    if factory_name == 'default_factory':
        log.warning('无法识别此插件')
        return None
    
    template = os.path.splitext(os.path.basename(action.url))[0]

    if charCode := await get_char_code(template, action.data, factory_name):
        return f'{charCode}-{template}'

    if otherCode := await get_other_code(template, action.data, factory_name):
        return f'{otherCode}'

    return 'hash_' + md5(action.data)


async def write_cache_and_read(action: element.Html, file_name: str, is_refresh=False, render_time=0, read=True):
    cache_dir = 'resource/plugins/generateCache'

    if file_name.startswith('hash'):
        cache_dir += '/hash'

    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    cache_url = f'{cache_dir}/{file_name}.png'

    if not os.path.exists(cache_url) or is_refresh:
        action.render_time = render_time

        image_content = await action.create_html_image()

        if not image_content:
            log.error(f'{file_name} 渲染失败, 这不应当是此插件引起的')
            return None, False

        with open(cache_url, "wb") as f:  # 写入
            f.write(image_content)
            return image_content, True

    else:
        os.utime(cache_url)
        
        if not read:
            return None, False
        
        with open(cache_url, "rb") as f:  # 读取
            image_content = f.read()
            return image_content, False

