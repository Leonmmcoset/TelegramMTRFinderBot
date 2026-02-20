import os
import sys
import hashlib
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DATA_FILE = 'user_data.json'


class UserDataManager:
    def __init__(self, data_file):
        self.data_file = data_file
        self.data = {}
        self.load()
    
    def load(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except Exception as e:
                print(f'加载数据失败: {e}')
                self.data = {}
        else:
            self.data = {}
    
    def save(self):
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f'保存数据失败: {e}')
    
    def get_user_data(self, user_id):
        if str(user_id) not in self.data:
            self.data[str(user_id)] = {}
        return self.data[str(user_id)]
    
    def update_user_data(self, user_id, data):
        self.data[str(user_id)] = data
        self.save()


user_data_manager = UserDataManager(DATA_FILE)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mtr-pathfinder'))
from mtr_pathfinder_v4 import main, station_name_to_id, station_num_to_name

LINK = 'http://leonmmcoset.jjxmm.win:8888'
MAX_WILD_BLOCKS = 1500
MAX_HOUR = 3

link_hash = hashlib.md5(LINK.encode('utf-8')).hexdigest()
LOCAL_FILE_PATH = os.path.join('mtr-pathfinder', f'mtr-station-data-{link_hash}-mtr4-v4.json')
DEP_PATH = os.path.join('mtr-pathfinder', f'mtr-route-data-{link_hash}-mtr4-v4.json')
BASE_PATH = os.path.join('mtr-pathfinder', 'mtr_pathfinder_data')
PNG_PATH = os.path.join('mtr-pathfinder', 'mtr_pathfinder_data')

TRANSFER_ADDITION = {}
WILD_ADDITION = {}
STATION_TABLE = {}
ORIGINAL_IGNORED_LINES = []

UPDATE_DATA = True
GEN_DEPARTURE = False

IGNORED_LINES = []
AVOID_STATIONS = []
CALCULATE_HIGH_SPEED = True
CALCULATE_BOAT = True
CALCULATE_WALKING_WILD = False
ONLY_LRT = False

START_STATION, END_STATION, ROUTE_NAME, DEL_ROUTE_NAME, SET_MAP_LINK = range(5)


def load_station_data(link=None):
    if link is None:
        link = LINK
    
    link_hash = hashlib.md5(link.encode('utf-8')).hexdigest()
    local_file_path = os.path.join('mtr-pathfinder', f'mtr-station-data-{link_hash}-mtr4-v4.json')
    
    if not os.path.exists(local_file_path):
        return None
    
    try:
        with open(local_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f'加载车站数据失败: {e}')
        return None


def get_user_settings(user_id):
    user_data = user_data_manager.get_user_data(user_id)
    if 'settings' not in user_data:
        user_data['settings'] = {
            'DETAIL': False,
            'CALCULATE_HIGH_SPEED': True,
            'CALCULATE_BOAT': True,
            'CALCULATE_WALKING_WILD': False,
            'ONLY_LRT': False,
            'MAX_HOUR': 3,
            'MIN_HOUR': 0,
            'MAX_TRANSFERS': 10,
            'PREFER_FAST': True,
            'PREFER_LESS_TRANSFER': False,
            'TIMEZONE': 8,
            'MAP_LINK': 'http://leonmmcoset.jjxmm.win:8888'
        }
        user_data_manager.update_user_data(user_id, user_data)
    else:
        settings = user_data['settings']
        if 'MIN_HOUR' not in settings:
            settings['MIN_HOUR'] = 0
        if 'MAX_TRANSFERS' not in settings:
            settings['MAX_TRANSFERS'] = 10
        if 'PREFER_FAST' not in settings:
            settings['PREFER_FAST'] = True
        if 'PREFER_LESS_TRANSFER' not in settings:
            settings['PREFER_LESS_TRANSFER'] = False
        if 'TIMEZONE' not in settings:
            settings['TIMEZONE'] = 8
        if 'MAP_LINK' not in settings:
            settings['MAP_LINK'] = 'http://leonmmcoset.jjxmm.win:8888'
        user_data['settings'] = settings
        user_data_manager.update_user_data(user_id, user_data)
    return user_data['settings']


def save_user_settings(user_id, settings):
    user_data = user_data_manager.get_user_data(user_id)
    user_data['settings'] = settings
    user_data_manager.update_user_data(user_id, user_data)


def get_user_history(user_id):
    user_data = user_data_manager.get_user_data(user_id)
    if 'history' not in user_data:
        user_data['history'] = []
        user_data_manager.update_user_data(user_id, user_data)
    return user_data['history']


def add_to_history(user_id, start_station, end_station):
    user_data = user_data_manager.get_user_data(user_id)
    if 'history' not in user_data:
        user_data['history'] = []
    
    history = user_data['history']
    route = {
        'start': start_station,
        'end': end_station,
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    for i, h in enumerate(history):
        if h['start'] == start_station and h['end'] == end_station:
            history.pop(i)
            break
    
    history.insert(0, route)
    
    if len(history) > 10:
        history.pop()
    
    user_data['history'] = history
    user_data_manager.update_user_data(user_id, user_data)


def get_user_routes(user_id):
    user_data = user_data_manager.get_user_data(user_id)
    if 'routes' not in user_data:
        user_data['routes'] = {}
        user_data_manager.update_user_data(user_id, user_data)
    return user_data['routes']


def save_user_routes(user_id, routes):
    user_data = user_data_manager.get_user_data(user_id)
    user_data['routes'] = routes
    user_data_manager.update_user_data(user_id, user_data)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = '''🚇 MTR 路径导航机器人

欢迎使用MTR路径导航机器人！以下是可用命令：

📍 路线查询
/path - 查询两个车站之间的路线

📜 历史记录
/history - 查看最近10条查询历史

🚀 快捷命令
/addroute - 添加快捷命令
/route - 查看所有快捷命令列表
/route <命令名> - 使用快捷命令查询
/delroute - 删除快捷命令

🔍 搜索
/search <关键词> - 搜索车站或线路

🚉 车站信息
/station <车站名> - 查询车站详情

🗺️ 地图设置
/setmap - 设置地图链接
/seemap - 查看当前地图链接

⚙️ 设置
/settings - 打开设置面板

❓ 其他
/start - 显示此帮助信息
/cancel - 取消当前操作

所有数据会自动保存，重启服务器后不会丢失！'''

    await update.message.reply_text(help_text)


async def path_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f'用户 {user_id} 开始查询路线')
    await update.message.reply_text('请输入起点车站名称：')
    return START_STATION


async def start_station(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    start_station = update.message.text
    logger.info(f'用户 {user_id} 输入起点：{start_station}')
    context.user_data['start_station'] = start_station
    await update.message.reply_text('请输入终点车站名称：')
    return END_STATION


async def end_station(update: Update, context: ContextTypes.DEFAULT_TYPE):
    end_station = update.message.text
    start_station = context.user_data['start_station']
    user_id = update.effective_user.id
    settings = get_user_settings(user_id)
    
    logger.info(f'用户 {user_id} 查询路线：{start_station} → {end_station}')
    logger.info(f'调用main函数参数：')
    logger.info(f'  station1: {start_station}')
    logger.info(f'  station2: {end_station}')
    logger.info(f'  LINK: {settings["MAP_LINK"]}')
    logger.info(f'  LOCAL_FILE_PATH: {LOCAL_FILE_PATH}')
    logger.info(f'  DEP_PATH: {DEP_PATH}')
    logger.info(f'  BASE_PATH: {BASE_PATH}')
    logger.info(f'  PNG_PATH: {PNG_PATH}')
    logger.info(f'  MAX_WILD_BLOCKS: {MAX_WILD_BLOCKS}')
    logger.info(f'  TRANSFER_ADDITION: {TRANSFER_ADDITION}')
    logger.info(f'  WILD_ADDITION: {WILD_ADDITION}')
    logger.info(f'  STATION_TABLE: {STATION_TABLE}')
    logger.info(f'  ORIGINAL_IGNORED_LINES: {ORIGINAL_IGNORED_LINES}')
    logger.info(f'  UPDATE_DATA: {UPDATE_DATA}')
    logger.info(f'  GEN_DEPARTURE: {GEN_DEPARTURE}')
    logger.info(f'  IGNORED_LINES: {IGNORED_LINES}')
    logger.info(f'  AVOID_STATIONS: {AVOID_STATIONS}')
    logger.info(f'  CALCULATE_HIGH_SPEED: {settings["CALCULATE_HIGH_SPEED"]}')
    logger.info(f'  CALCULATE_BOAT: {settings["CALCULATE_BOAT"]}')
    logger.info(f'  CALCULATE_WALKING_WILD: {settings["CALCULATE_WALKING_WILD"]}')
    logger.info(f'  ONLY_LRT: {settings["ONLY_LRT"]}')
    logger.info(f'  DETAIL: {settings["DETAIL"]}')
    logger.info(f'  MAX_HOUR: {settings["MAX_HOUR"]}')
    logger.info(f'  gen_image: True')
    logger.info(f'  show: False')
    
    await update.message.reply_text('正在生成路线图，请稍候...')
    
    try:
        result = main(
            start_station, end_station, settings['MAP_LINK'], LOCAL_FILE_PATH, DEP_PATH,
            BASE_PATH, PNG_PATH, MAX_WILD_BLOCKS, TRANSFER_ADDITION,
            WILD_ADDITION, STATION_TABLE, ORIGINAL_IGNORED_LINES,
            UPDATE_DATA, GEN_DEPARTURE, IGNORED_LINES, AVOID_STATIONS,
            settings['CALCULATE_HIGH_SPEED'], settings['CALCULATE_BOAT'], 
            settings['CALCULATE_WALKING_WILD'], settings['ONLY_LRT'], 
            settings['DETAIL'], settings['MAX_HOUR'], gen_image=True, show=False
        )
    except Exception as e:
        logger.error(f'用户 {user_id} 查询路线失败：{e}')
        await update.message.reply_text('查询路线时发生错误，请稍后重试。')
        return ConversationHandler.END
    
    if result is False:
        logger.warning(f'用户 {user_id} 未找到路线：{start_station} → {end_station}')
        await update.message.reply_text('找不到路线，请检查车站名称是否正确。')
    elif result is None:
        logger.warning(f'用户 {user_id} 车站名称错误')
        await update.message.reply_text('车站输入错误，请重新输入。')
    elif not isinstance(result, tuple) or len(result) != 2:
        logger.error(f'用户 {user_id} 查询结果格式错误：{type(result)}')
        await update.message.reply_text('查询结果格式错误，请稍后重试。')
    else:
        logger.info(f'用户 {user_id} 路线查询成功：{start_station} → {end_station}')
        add_to_history(user_id, start_station, end_station)
        image, base64_str = result
        from io import BytesIO
        import base64 as b64
        img_bytes = b64.b64decode(base64_str)
        await update.message.reply_photo(photo=BytesIO(img_bytes))
    
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f'用户 {user_id} 取消操作')
    await update.message.reply_text('已取消操作。')
    return ConversationHandler.END


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f'用户 {user_id} 打开设置')
    settings = get_user_settings(user_id)
    
    keyboard = [
        [
            InlineKeyboardButton(
                f"详细模式: {'✅' if settings['DETAIL'] else '❌'}", 
                callback_data='toggle_DETAIL'
            ),
            InlineKeyboardButton(
                f"高铁: {'✅' if settings['CALCULATE_HIGH_SPEED'] else '❌'}", 
                callback_data='toggle_CALCULATE_HIGH_SPEED'
            )
        ],
        [
            InlineKeyboardButton(
                f"船: {'✅' if settings['CALCULATE_BOAT'] else '❌'}", 
                callback_data='toggle_CALCULATE_BOAT'
            ),
            InlineKeyboardButton(
                f"越野步行: {'✅' if settings['CALCULATE_WALKING_WILD'] else '❌'}", 
                callback_data='toggle_CALCULATE_WALKING_WILD'
            )
        ],
        [
            InlineKeyboardButton(
                f"仅轻轨: {'✅' if settings['ONLY_LRT'] else '❌'}", 
                callback_data='toggle_ONLY_LRT'
            ),
            InlineKeyboardButton(
                f"最大时长: {settings['MAX_HOUR']}小时", 
                callback_data='change_MAX_HOUR'
            )
        ],
        [
            InlineKeyboardButton(
                f"最小时长: {settings['MIN_HOUR']}小时", 
                callback_data='change_MIN_HOUR'
            ),
            InlineKeyboardButton(
                f"最大换乘: {settings['MAX_TRANSFERS']}次", 
                callback_data='change_MAX_TRANSFERS'
            )
        ],
        [
            InlineKeyboardButton(
                f"优先快速: {'✅' if settings['PREFER_FAST'] else '❌'}", 
                callback_data='toggle_PREFER_FAST'
            ),
            InlineKeyboardButton(
                f"优先少换乘: {'✅' if settings['PREFER_LESS_TRANSFER'] else '❌'}", 
                callback_data='toggle_PREFER_LESS_TRANSFER'
            )
        ],
        [
            InlineKeyboardButton(
                f"时区: UTC{'+' if settings['TIMEZONE'] >= 0 else ''}{settings['TIMEZONE']}", 
                callback_data='change_TIMEZONE'
            ),
            InlineKeyboardButton(
                f"地图链接: {'自定义' if settings['MAP_LINK'] != 'http://leonmmcoset.jjxmm.win:8888' else '默认'}", 
                callback_data='toggle_MAP_LINK'
            )
        ],
        [InlineKeyboardButton("重置默认设置", callback_data='reset_settings')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('⚙️ 设置', reply_markup=reply_markup)


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    settings = get_user_settings(user_id)
    
    if query.data == 'toggle_DETAIL':
        settings['DETAIL'] = not settings['DETAIL']
        logger.info(f'用户 {user_id} 切换详细模式：{settings["DETAIL"]}')
    elif query.data == 'toggle_CALCULATE_HIGH_SPEED':
        settings['CALCULATE_HIGH_SPEED'] = not settings['CALCULATE_HIGH_SPEED']
        logger.info(f'用户 {user_id} 切换高铁：{settings["CALCULATE_HIGH_SPEED"]}')
    elif query.data == 'toggle_CALCULATE_BOAT':
        settings['CALCULATE_BOAT'] = not settings['CALCULATE_BOAT']
        logger.info(f'用户 {user_id} 切换船：{settings["CALCULATE_BOAT"]}')
    elif query.data == 'toggle_CALCULATE_WALKING_WILD':
        settings['CALCULATE_WALKING_WILD'] = not settings['CALCULATE_WALKING_WILD']
        logger.info(f'用户 {user_id} 切换越野步行：{settings["CALCULATE_WALKING_WILD"]}')
    elif query.data == 'toggle_ONLY_LRT':
        settings['ONLY_LRT'] = not settings['ONLY_LRT']
        logger.info(f'用户 {user_id} 切换仅轻轨：{settings["ONLY_LRT"]}')
    elif query.data == 'change_MAX_HOUR':
        settings['MAX_HOUR'] = settings['MAX_HOUR'] + 1 if settings['MAX_HOUR'] < 12 else 1
        logger.info(f'用户 {user_id} 修改最大时长：{settings["MAX_HOUR"]}')
    elif query.data == 'change_MIN_HOUR':
        settings['MIN_HOUR'] = settings['MIN_HOUR'] + 1 if settings['MIN_HOUR'] < 12 else 0
        logger.info(f'用户 {user_id} 修改最小时长：{settings["MIN_HOUR"]}')
    elif query.data == 'change_MAX_TRANSFERS':
        settings['MAX_TRANSFERS'] = settings['MAX_TRANSFERS'] + 1 if settings['MAX_TRANSFERS'] < 20 else 0
        logger.info(f'用户 {user_id} 修改最大换乘：{settings["MAX_TRANSFERS"]}')
    elif query.data == 'toggle_PREFER_FAST':
        settings['PREFER_FAST'] = not settings['PREFER_FAST']
        logger.info(f'用户 {user_id} 切换优先快速：{settings["PREFER_FAST"]}')
    elif query.data == 'toggle_PREFER_LESS_TRANSFER':
        settings['PREFER_LESS_TRANSFER'] = not settings['PREFER_LESS_TRANSFER']
        logger.info(f'用户 {user_id} 切换优先少换乘：{settings["PREFER_LESS_TRANSFER"]}')
    elif query.data == 'change_TIMEZONE':
        settings['TIMEZONE'] = settings['TIMEZONE'] + 1 if settings['TIMEZONE'] < 12 else -12
        logger.info(f'用户 {user_id} 修改时区：UTC{settings["TIMEZONE"]}')
    elif query.data == 'toggle_MAP_LINK':
        if settings['MAP_LINK'] == 'http://leonmmcoset.jjxmm.win:8888':
            await query.message.reply_text('请使用 /setmap 命令设置自定义地图链接。')
            return
        else:
            settings['MAP_LINK'] = 'http://leonmmcoset.jjxmm.win:8888'
            logger.info(f'用户 {user_id} 恢复默认地图链接')
    elif query.data == 'reset_settings':
        settings.update({
            'DETAIL': False,
            'CALCULATE_HIGH_SPEED': True,
            'CALCULATE_BOAT': True,
            'CALCULATE_WALKING_WILD': False,
            'ONLY_LRT': False,
            'MAX_HOUR': 3,
            'MIN_HOUR': 0,
            'MAX_TRANSFERS': 10,
            'PREFER_FAST': True,
            'PREFER_LESS_TRANSFER': False,
            'TIMEZONE': 8,
            'MAP_LINK': 'http://leonmmcoset.jjxmm.win:8888'
        })
        logger.info(f'用户 {user_id} 重置设置')
    
    save_user_settings(user_id, settings)
    
    keyboard = [
        [
            InlineKeyboardButton(
                f"详细模式: {'✅' if settings['DETAIL'] else '❌'}", 
                callback_data='toggle_DETAIL'
            ),
            InlineKeyboardButton(
                f"高铁: {'✅' if settings['CALCULATE_HIGH_SPEED'] else '❌'}", 
                callback_data='toggle_CALCULATE_HIGH_SPEED'
            )
        ],
        [
            InlineKeyboardButton(
                f"船: {'✅' if settings['CALCULATE_BOAT'] else '❌'}", 
                callback_data='toggle_CALCULATE_BOAT'
            ),
            InlineKeyboardButton(
                f"越野步行: {'✅' if settings['CALCULATE_WALKING_WILD'] else '❌'}", 
                callback_data='toggle_CALCULATE_WALKING_WILD'
            )
        ],
        [
            InlineKeyboardButton(
                f"仅轻轨: {'✅' if settings['ONLY_LRT'] else '❌'}", 
                callback_data='toggle_ONLY_LRT'
            ),
            InlineKeyboardButton(
                f"最大时长: {settings['MAX_HOUR']}小时", 
                callback_data='change_MAX_HOUR'
            )
        ],
        [
            InlineKeyboardButton(
                f"最小时长: {settings['MIN_HOUR']}小时", 
                callback_data='change_MIN_HOUR'
            ),
            InlineKeyboardButton(
                f"最大换乘: {settings['MAX_TRANSFERS']}次", 
                callback_data='change_MAX_TRANSFERS'
            )
        ],
        [
            InlineKeyboardButton(
                f"优先快速: {'✅' if settings['PREFER_FAST'] else '❌'}", 
                callback_data='toggle_PREFER_FAST'
            ),
            InlineKeyboardButton(
                f"优先少换乘: {'✅' if settings['PREFER_LESS_TRANSFER'] else '❌'}", 
                callback_data='toggle_PREFER_LESS_TRANSFER'
            )
        ],
        [
            InlineKeyboardButton(
                f"时区: UTC{'+' if settings['TIMEZONE'] >= 0 else ''}{settings['TIMEZONE']}", 
                callback_data='change_TIMEZONE'
            ),
            InlineKeyboardButton(
                f"地图链接: {'自定义' if settings['MAP_LINK'] != 'http://leonmmcoset.jjxmm.win:8888' else '默认'}", 
                callback_data='toggle_MAP_LINK'
            )
        ],
        [InlineKeyboardButton("重置默认设置", callback_data='reset_settings')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_reply_markup(reply_markup=reply_markup)


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    history = get_user_history(user_id)
    
    if not history:
        await update.message.reply_text('暂无查询历史。')
        return
    
    text = '📜 查询历史（最近10条）：\n\n'
    keyboard = []
    
    for i, route in enumerate(history, 1):
        text += f'{i}. {route["start"]} → {route["end"]}\n   {route["time"]}\n\n'
        keyboard.append([InlineKeyboardButton(
            f'{i}. {route["start"]} → {route["end"]}',
            callback_data=f'history_{i-1}'
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)


async def history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    index = int(query.data.split('_')[1])
    history = get_user_history(user_id)
    
    if index >= len(history):
        await query.edit_message_text('该记录不存在。')
        return
    
    route = history[index]
    settings = get_user_settings(user_id)
    
    logger.info(f'用户 {user_id} 从历史查询：{route["start"]} → {route["end"]}')
    logger.info(f'调用main函数参数：')
    logger.info(f'  station1: {route["start"]}')
    logger.info(f'  station2: {route["end"]}')
    logger.info(f'  LINK: {settings["MAP_LINK"]}')
    logger.info(f'  LOCAL_FILE_PATH: {LOCAL_FILE_PATH}')
    logger.info(f'  DEP_PATH: {DEP_PATH}')
    logger.info(f'  BASE_PATH: {BASE_PATH}')
    logger.info(f'  PNG_PATH: {PNG_PATH}')
    logger.info(f'  MAX_WILD_BLOCKS: {MAX_WILD_BLOCKS}')
    logger.info(f'  TRANSFER_ADDITION: {TRANSFER_ADDITION}')
    logger.info(f'  WILD_ADDITION: {WILD_ADDITION}')
    logger.info(f'  STATION_TABLE: {STATION_TABLE}')
    logger.info(f'  ORIGINAL_IGNORED_LINES: {ORIGINAL_IGNORED_LINES}')
    logger.info(f'  UPDATE_DATA: {UPDATE_DATA}')
    logger.info(f'  GEN_DEPARTURE: {GEN_DEPARTURE}')
    logger.info(f'  IGNORED_LINES: {IGNORED_LINES}')
    logger.info(f'  AVOID_STATIONS: {AVOID_STATIONS}')
    logger.info(f'  CALCULATE_HIGH_SPEED: {settings["CALCULATE_HIGH_SPEED"]}')
    logger.info(f'  CALCULATE_BOAT: {settings["CALCULATE_BOAT"]}')
    logger.info(f'  CALCULATE_WALKING_WILD: {settings["CALCULATE_WALKING_WILD"]}')
    logger.info(f'  ONLY_LRT: {settings["ONLY_LRT"]}')
    logger.info(f'  DETAIL: {settings["DETAIL"]}')
    logger.info(f'  MAX_HOUR: {settings["MAX_HOUR"]}')
    logger.info(f'  gen_image: True')
    logger.info(f'  show: False')
    
    await query.edit_message_text(f'正在查询 {route["start"]} → {route["end"]}...')
    
    try:
        result = main(
            route['start'], route['end'], settings['MAP_LINK'], LOCAL_FILE_PATH, DEP_PATH,
            BASE_PATH, PNG_PATH, MAX_WILD_BLOCKS, TRANSFER_ADDITION,
            WILD_ADDITION, STATION_TABLE, ORIGINAL_IGNORED_LINES,
            UPDATE_DATA, GEN_DEPARTURE, IGNORED_LINES, AVOID_STATIONS,
            settings['CALCULATE_HIGH_SPEED'], settings['CALCULATE_BOAT'], 
            settings['CALCULATE_WALKING_WILD'], settings['ONLY_LRT'], 
            settings['DETAIL'], settings['MAX_HOUR'], gen_image=True, show=False
        )
    except Exception as e:
        logger.error(f'用户 {user_id} 历史查询失败：{e}')
        await query.message.reply_text('查询路线时发生错误，请稍后重试。')
        return
    
    if result is False:
        logger.warning(f'用户 {user_id} 历史查询未找到路线')
        await query.message.reply_text('找不到路线，请检查车站名称是否正确。')
    elif result is None:
        logger.warning(f'用户 {user_id} 历史查询车站名称错误')
        await query.message.reply_text('车站输入错误，请重新输入。')
    elif not isinstance(result, tuple) or len(result) != 2:
        logger.error(f'用户 {user_id} 历史查询结果格式错误：{type(result)}')
        await query.message.reply_text('查询结果格式错误，请稍后重试。')
    else:
        logger.info(f'用户 {user_id} 历史查询成功')
        add_to_history(user_id, route['start'], route['end'])
        image, base64_str = result
        from io import BytesIO
        import base64 as b64
        img_bytes = b64.b64decode(base64_str)
        await query.message.reply_photo(photo=BytesIO(img_bytes))


async def add_route_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('请输入快捷命令名称：')
    return ROUTE_NAME


async def add_route_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['add_route_name'] = update.message.text
    await update.message.reply_text('请输入起点车站名称：')
    return START_STATION


async def add_route_start_station(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['add_route_start'] = update.message.text
    await update.message.reply_text('请输入终点车站名称：')
    return END_STATION


async def add_route_end_station(update: Update, context: ContextTypes.DEFAULT_TYPE):
    end_station = update.message.text
    start_station = context.user_data['add_route_start']
    route_name = context.user_data['add_route_name']
    user_id = update.effective_user.id
    
    logger.info(f'用户 {user_id} 添加快捷命令：{route_name} ({start_station} → {end_station})')
    
    routes = get_user_routes(user_id)
    routes[route_name] = {
        'start': start_station,
        'end': end_station
    }
    
    save_user_routes(user_id, routes)
    await update.message.reply_text(f'✅ 快捷命令 "/route {route_name}" 已添加！\n路线：{start_station} → {end_station}')
    return ConversationHandler.END


async def route_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not context.args:
        logger.info(f'用户 {user_id} 查看快捷命令列表')
        routes = get_user_routes(user_id)
        if not routes:
            await update.message.reply_text('暂无快捷命令。\n使用 /addroute 添加快捷命令。')
            return
        
        text = '🚀 快捷命令列表：\n\n'
        for name, route in routes.items():
            text += f'/route {name} - {route["start"]} → {route["end"]}\n'
        
        text += '\n使用 /delroute 删除快捷命令。'
        await update.message.reply_text(text)
        return
    
    route_name = context.args[0]
    routes = get_user_routes(user_id)
    
    if route_name not in routes:
        logger.warning(f'用户 {user_id} 快捷命令不存在：{route_name}')
        await update.message.reply_text(f'快捷命令 "/route {route_name}" 不存在。')
        return
    
    route = routes[route_name]
    settings = get_user_settings(user_id)
    
    logger.info(f'用户 {user_id} 使用快捷命令：{route_name}')
    logger.info(f'调用main函数参数：')
    logger.info(f'  station1: {route["start"]}')
    logger.info(f'  station2: {route["end"]}')
    logger.info(f'  LINK: {settings["MAP_LINK"]}')
    logger.info(f'  LOCAL_FILE_PATH: {LOCAL_FILE_PATH}')
    logger.info(f'  DEP_PATH: {DEP_PATH}')
    logger.info(f'  BASE_PATH: {BASE_PATH}')
    logger.info(f'  PNG_PATH: {PNG_PATH}')
    logger.info(f'  MAX_WILD_BLOCKS: {MAX_WILD_BLOCKS}')
    logger.info(f'  TRANSFER_ADDITION: {TRANSFER_ADDITION}')
    logger.info(f'  WILD_ADDITION: {WILD_ADDITION}')
    logger.info(f'  STATION_TABLE: {STATION_TABLE}')
    logger.info(f'  ORIGINAL_IGNORED_LINES: {ORIGINAL_IGNORED_LINES}')
    logger.info(f'  UPDATE_DATA: {UPDATE_DATA}')
    logger.info(f'  GEN_DEPARTURE: {GEN_DEPARTURE}')
    logger.info(f'  IGNORED_LINES: {IGNORED_LINES}')
    logger.info(f'  AVOID_STATIONS: {AVOID_STATIONS}')
    logger.info(f'  CALCULATE_HIGH_SPEED: {settings["CALCULATE_HIGH_SPEED"]}')
    logger.info(f'  CALCULATE_BOAT: {settings["CALCULATE_BOAT"]}')
    logger.info(f'  CALCULATE_WALKING_WILD: {settings["CALCULATE_WALKING_WILD"]}')
    logger.info(f'  ONLY_LRT: {settings["ONLY_LRT"]}')
    logger.info(f'  DETAIL: {settings["DETAIL"]}')
    logger.info(f'  MAX_HOUR: {settings["MAX_HOUR"]}')
    logger.info(f'  gen_image: True')
    logger.info(f'  show: False')
    
    await update.message.reply_text(f'正在查询 {route["start"]} → {route["end"]}...')
    
    try:
        result = main(
            route['start'], route['end'], settings['MAP_LINK'], LOCAL_FILE_PATH, DEP_PATH,
            BASE_PATH, PNG_PATH, MAX_WILD_BLOCKS, TRANSFER_ADDITION,
            WILD_ADDITION, STATION_TABLE, ORIGINAL_IGNORED_LINES,
            UPDATE_DATA, GEN_DEPARTURE, IGNORED_LINES, AVOID_STATIONS,
            settings['CALCULATE_HIGH_SPEED'], settings['CALCULATE_BOAT'], 
            settings['CALCULATE_WALKING_WILD'], settings['ONLY_LRT'], 
            settings['DETAIL'], settings['MAX_HOUR'], gen_image=True, show=False
        )
    except Exception as e:
        logger.error(f'用户 {user_id} 快捷命令查询失败：{e}')
        await update.message.reply_text('查询路线时发生错误，请稍后重试。')
        return
    
    if result is False:
        logger.warning(f'用户 {user_id} 快捷命令查询未找到路线')
        await update.message.reply_text('找不到路线，请检查车站名称是否正确。')
    elif result is None:
        logger.warning(f'用户 {user_id} 快捷命令查询车站名称错误')
        await update.message.reply_text('车站输入错误，请重新输入。')
    elif not isinstance(result, tuple) or len(result) != 2:
        logger.error(f'用户 {user_id} 快捷命令查询结果格式错误：{type(result)}')
        await update.message.reply_text('查询结果格式错误，请稍后重试。')
    else:
        logger.info(f'用户 {user_id} 快捷命令查询成功')
        add_to_history(user_id, route['start'], route['end'])
        image, base64_str = result
        from io import BytesIO
        import base64 as b64
        img_bytes = b64.b64decode(base64_str)
        await update.message.reply_photo(photo=BytesIO(img_bytes))


async def del_route_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    routes = get_user_routes(user_id)
    
    if not routes:
        await update.message.reply_text('暂无快捷命令。\n使用 /addroute 添加快捷命令。')
        return ConversationHandler.END
    
    text = '请选择要删除的快捷命令：\n\n'
    keyboard = []
    
    for name, route in routes.items():
        text += f'/route {name} - {route["start"]} → {route["end"]}\n'
        keyboard.append([InlineKeyboardButton(
            f'/route {name} - {route["start"]} → {route["end"]}',
            callback_data=f'del_{name}'
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)
    return DEL_ROUTE_NAME


async def del_route_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    route_name = query.data.split('_')[1]
    routes = get_user_routes(user_id)
    
    logger.info(f'用户 {user_id} 删除快捷命令：{route_name}')
    
    if route_name not in routes:
        logger.warning(f'用户 {user_id} 删除的快捷命令不存在：{route_name}')
        await query.edit_message_text(f'快捷命令 "/route {route_name}" 不存在。')
        return ConversationHandler.END
    
    del routes[route_name]
    save_user_routes(user_id, routes)
    await query.edit_message_text(f'✅ 快捷命令 "/route {route_name}" 已删除。')
    return ConversationHandler.END


async def station_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not context.args:
        logger.info(f'用户 {user_id} 查看车站信息帮助')
        await update.message.reply_text('用法：/station <车站名>\n例如：/station 莱恩再新城')
        return
    
    station_name = ' '.join(context.args)
    logger.info(f'用户 {user_id} 查询车站信息：{station_name}')
    
    settings = get_user_settings(user_id)
    map_link = settings['MAP_LINK']
    
    link_hash = hashlib.md5(map_link.encode('utf-8')).hexdigest()
    local_file_path = os.path.join('mtr-pathfinder', f'mtr-station-data-{link_hash}-mtr4-v4.json')
    
    logger.info(f'用户 {user_id} 更新车站数据：{map_link}')
    await update.message.reply_text('正在更新车站数据，请稍候...')
    
    try:
        from mtr_pathfinder_v4 import fetch_data
        data = fetch_data(map_link, local_file_path, MAX_WILD_BLOCKS)
        logger.info(f'用户 {user_id} 车站数据更新成功')
    except Exception as e:
        logger.error(f'用户 {user_id} 车站数据更新失败：{e}')
        await update.message.reply_text('更新车站数据失败，请稍后重试。')
        return
    
    station_id = station_name_to_id(data, station_name, STATION_TABLE)
    
    if not station_id:
        logger.warning(f'用户 {user_id} 车站不存在：{station_name}')
        await update.message.reply_text(f'找不到车站 "{station_name}"。')
        return
    
    station_info = data['stations'][station_id]
    station_name_display = station_info['name'].replace('|', ' / ')
    
    routes = data['station_routes'].get(station_id, [])
    connections = station_info.get('connections', [])
    
    text = f'🚉 车站信息\n\n'
    text += f'📍 车站名称：{station_name_display}\n'
    text += f'🆔 车站ID：{station_info["station"]}\n\n'
    
    if routes:
        text += f'🚃 经过路线：\n'
        for route_id in routes:
            if route_id in data['routes']:
                route = data['routes'][route_id]
                route_name = route['name'].replace('|', ' / ')
                route_type = route.get('type', 'unknown')
                type_emoji = {
                    'train_normal': '🚂',
                    'train_high_speed': '🚄',
                    'train_light_rail': '🚃',
                    'boat_normal': '⛴',
                    'boat_high_speed': '🚤',
                    'boat_light_rail': '🚥',
                    'cable_car_normal': '🚠',
                    'airplane_normal': '✈️'
                }.get(route_type, '🚂')
                text += f'{type_emoji} {route_name}\n'
        text += '\n'
    
    if connections:
        text += f'🔄 可换乘车站：\n'
        for conn_id in connections:
            if conn_id in data['stations']:
                conn_name = data['stations'][conn_id]['name'].replace('|', ' / ')
                text += f'• {conn_name}\n'
    else:
        text += '🔄 可换乘车站：无\n'
    
    logger.info(f'用户 {user_id} 车站信息查询成功：{station_name}')
    await update.message.reply_text(text)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not context.args:
        logger.info(f'用户 {user_id} 查看搜索帮助')
        await update.message.reply_text('用法：/search <关键词>\n例如：/search 莱恩\n搜索车站或线路')
        return
    
    keyword = ' '.join(context.args).lower()
    logger.info(f'用户 {user_id} 搜索：{keyword}')
    
    settings = get_user_settings(user_id)
    map_link = settings['MAP_LINK']
    
    link_hash = hashlib.md5(map_link.encode('utf-8')).hexdigest()
    local_file_path = os.path.join('mtr-pathfinder', f'mtr-station-data-{link_hash}-mtr4-v4.json')
    
    logger.info(f'用户 {user_id} 更新车站数据：{map_link}')
    await update.message.reply_text('正在更新车站数据，请稍候...')
    
    try:
        from mtr_pathfinder_v4 import fetch_data
        data = fetch_data(map_link, local_file_path, MAX_WILD_BLOCKS)
        logger.info(f'用户 {user_id} 车站数据更新成功')
    except Exception as e:
        logger.error(f'用户 {user_id} 车站数据更新失败：{e}')
        await update.message.reply_text('更新车站数据失败，请稍后重试。')
        return
    
    stations = data.get('stations', {})
    routes = data.get('routes', {})
    
    station_results = []
    route_results = []
    
    for station_id, station_info in stations.items():
        station_name = station_info.get('name', '').lower()
        if keyword in station_name:
            station_results.append({
                'id': station_id,
                'name': station_info['name'],
                'station_code': station_info.get('station', '')
            })
    
    for route_id, route_info in routes.items():
        route_name = route_info.get('name', '').lower()
        if keyword in route_name:
            route_results.append({
                'id': route_id,
                'name': route_info['name'],
                'type': route_info.get('type', 'unknown'),
                'number': route_info.get('number', '')
            })
    
    if not station_results and not route_results:
        logger.warning(f'用户 {user_id} 搜索无结果：{keyword}')
        await update.message.reply_text(f'未找到包含 "{keyword}" 的车站或线路。')
        return
    
    text = f'🔍 搜索结果："{keyword}"\n\n'
    
    if station_results:
        text += f'🚉 车站（{len(station_results)}个）：\n'
        for i, station in enumerate(station_results[:10], 1):
            station_name_display = station['name'].replace('|', ' / ')
            text += f'{i}. {station_name_display} (ID: {station["station_code"]})\n'
        if len(station_results) > 10:
            text += f'... 还有 {len(station_results) - 10} 个车站\n'
        text += '\n'
    
    if route_results:
        text += f'🚃 线路（{len(route_results)}条）：\n'
        for i, route in enumerate(route_results[:10], 1):
            route_name_display = route['name'].replace('|', ' / ')
            type_emoji = {
                'train_normal': '🚂',
                'train_high_speed': '🚄',
                'train_light_rail': '🚃',
                'boat_normal': '⛴',
                'boat_high_speed': '🚤',
                'boat_light_rail': '🚥',
                'cable_car_normal': '🚠',
                'airplane_normal': '✈️'
            }.get(route['type'], '🚂')
            text += f'{i}. {type_emoji} {route_name_display}\n'
        if len(route_results) > 10:
            text += f'... 还有 {len(route_results) - 10} 条线路\n'
    
    logger.info(f'用户 {user_id} 搜索成功：{keyword}（{len(station_results)}个车站，{len(route_results)}条线路）')
    await update.message.reply_text(text)


async def set_map_link_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f'用户 {user_id} 开始设置地图链接')
    await update.message.reply_text('请输入新的地图链接：')
    return SET_MAP_LINK


async def set_map_link_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    new_link = update.message.text.strip()
    
    if not new_link:
        logger.warning(f'用户 {user_id} 地图链接为空')
        await update.message.reply_text('地图链接不能为空。')
        return ConversationHandler.END
    
    logger.info(f'用户 {user_id} 设置地图链接：{new_link}')
    
    settings = get_user_settings(user_id)
    settings['MAP_LINK'] = new_link
    save_user_settings(user_id, settings)
    
    await update.message.reply_text(f'✅ 地图链接已更新为：{new_link}')
    return ConversationHandler.END


async def see_map_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f'用户 {user_id} 查看地图链接')
    
    settings = get_user_settings(user_id)
    current_link = settings['MAP_LINK']
    
    is_default = current_link == 'http://leonmmcoset.jjxmm.win:8888'
    
    text = f'🗺️ 当前地图链接\n\n'
    text += f'📍 链接：{current_link}\n'
    text += f'📌 类型：{"默认" if is_default else "自定义"}\n\n'
    
    if is_default:
        text += '💡 使用 /setmap 命令可以设置自定义地图链接。'
    else:
        text += '💡 在设置面板中点击"地图链接"按钮可以恢复默认链接。'
    
    await update.message.reply_text(text)


def main_bot():
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    if not TOKEN:
        print('请设置环境变量 TELEGRAM_BOT_TOKEN')
        return
    
    application = Application.builder().token(TOKEN).base_url('https://r8gmzg.mc-cloud.org/bot').build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('path', path_start)],
        states={
            START_STATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_station)],
            END_STATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, end_station)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    add_route_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('addroute', add_route_start)],
        states={
            ROUTE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_route_name)],
            START_STATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_route_start_station)],
            END_STATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_route_end_station)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    del_route_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('delroute', del_route_start)],
        states={
            DEL_ROUTE_NAME: [CallbackQueryHandler(del_route_callback, pattern='^del_')],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    set_map_link_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('setmap', set_map_link_start)],
        states={
            SET_MAP_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_map_link_end)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(add_route_conv_handler)
    application.add_handler(del_route_conv_handler)
    application.add_handler(set_map_link_conv_handler)
    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('station', station_command))
    application.add_handler(CommandHandler('search', search_command))
    application.add_handler(CommandHandler('settings', settings))
    application.add_handler(CommandHandler('history', history))
    application.add_handler(CommandHandler('route', route_command))
    application.add_handler(CommandHandler('seemap', see_map_link))
    application.add_handler(CallbackQueryHandler(settings_callback, pattern='^toggle_|^change_|^reset_'))
    application.add_handler(CallbackQueryHandler(history_callback, pattern='^history_'))
    
    print('Bot已启动...')
    application.run_polling()


if __name__ == '__main__':
    main_bot()
