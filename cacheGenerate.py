import os
import asyncio
import importlib
from dataclasses import dataclass

from core import bot as main_bot
from core.resource.arknightsGameData import ArknightsGameData
from amiyabot import Chain
from amiyabot.util import temp_sys_path
from amiyabot.log import LoggerManager
from .cacheControl import match_filename, write_cache_and_read

curr_dir = os.path.dirname(__file__)

log = LoggerManager(' \b\b缓存生成')

async def import_op(): 
    dir_path = []

    if (target := 'arknights-operator-yb') in main_bot.plugins.keys():
        dir_path.append( main_bot.plugins[target].path[1])
    if (target := 'arknights-operator-m&c') in main_bot.plugins.keys():
        dir_path.append( main_bot.plugins[target].path[1])
    for plug_name in main_bot.plugins.keys():
        if 'amiyabot-arknights-operator' in plug_name:
            dir_path.append( main_bot.plugins[plug_name].path[1])

    if not dir_path:
        return None
    
    log.info(f'使用依赖: {os.path.split(dir_path[0])[1]}')

    with temp_sys_path(os.path.dirname(os.path.abspath(dir_path[0]))):    
        return importlib.import_module(os.path.basename(dir_path[0]))           


@dataclass
class CharInfo:
    name: str = ''


class GenerateStatus:
    alive = False


async def generate_char(char_name: str, OP, generate_opt: dict):
    GenerateStatus.alive = True
    
    plug_dir = OP.__path__[0]
    OPData = OP.main.OperatorData
    show_schedule = generate_opt['show_schedule']
   
    official = 'amiyabot' in plug_dir
    is_yb = 'yb' in plug_dir

    template = [
            f'{plug_dir}/template/operatorInfo.html',
            f'{plug_dir}/template/skillsDetail.html',
            f'{plug_dir}/template/operatorModule.html',
            f'{plug_dir}/template/operatorToken.html',
            f'{plug_dir}/template/operatorCost.html',
    ]
    
    char_info = CharInfo(name=char_name)
    info, token = await OPData.get_operator_detail(char_info)
    data_set = [
        info,
        await OPData.get_skills_detail(char_info),
        OPData.find_operator_module(char_info, False),
        token if token['tokens'] else None,
    ]

    if is_yb:
        data_set.append(None)
    else:
        data_set.append(await OPData.get_level_up_cost(char_info))
    
    template_name = ['详情','技能','模组','召唤物','材料']
    
    count = 0
    for index in range(5):
        if not GenerateStatus.alive:
            return count
        
        if not data_set[index]:
            continue
        
        width=100
        
        if index == 0 and not is_yb:
            width = 1600 if official else 1280
        
        if generate_opt['width_limit']:
            width = 500

        chain = Chain().html(template[index], data_set[index], width, height=100)
        
        file_name = await match_filename(chain.chain[0], factory_name='amiyabot-arknights-operator')

        if file_name.startswith('hash_'):
            continue

        res = await write_cache_and_read(chain.chain[0], file_name=file_name,
                                         is_refresh=generate_opt['refresh'], 
                                         render_time=generate_opt['render_time'],
                                         read=False)
        if res[1]:
            count += 1
            if show_schedule: 
                log.info(f'已生成 {char_name}-{template_name[index]}')
            await asyncio.sleep(generate_opt['interval'])
            
    if not count and show_schedule:
        log.info(f'跳过 {char_name} 已存在的缓存') 
            
    return count


async def batch_generate(target_amount: int, generate_opt: dict):

    OP = await import_op()
    if not OP:
        log.error('干员查询插件未安装或不支持, 生成失败')
        return -2, 0

    char_list = list(ArknightsGameData.operators)[::-1]

    count = 0
    count_char = 0
    for char_name in char_list:
        if not GenerateStatus.alive:
            return count_char, count
        
        res = await generate_char(char_name, OP, generate_opt)
        if res:
            count += res
            count_char += 1

        if count >= target_amount :
            break
    
    else:
        if count == 0:
            count_char = -1
    
    return count_char, count

