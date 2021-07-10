#!/usr/bin/python3
"""Monitor MTGA logs and display Simplified-Chinese images of on-hovered cards in real time."""
__license__ = 'GPL'
__version__ = 'v0.1.8'
__date__ = '2021-07-10'
__credits__ = ['https://www.iyingdi.com', 'https://www.scryfall.com', 'https://gatherer.wizards.com']
__qq_group__ = '780812745'
__status__ = 'Developing'

import asyncio
import os
import platform
import threading
from datetime import datetime
from json import loads, dumps
from tkinter import *
from tkinter.ttk import *

import win32gui
from PIL import Image, ImageTk, ImageGrab, ImageChops
from imagehash import average_hash, dhash, hex_to_hash  # phash, whash
from ctypes import windll, Structure, c_long, byref

# import numpy
# import pyautogui
# from time import time

DEBUGGING = False  # 测试开关
HOVER_LOG_DIR = os.sep.join(['.', 'log', ''])
if not os.path.exists(HOVER_LOG_DIR):
    os.mkdir(HOVER_LOG_DIR)
HOVER_LOG_PATH = f'{HOVER_LOG_DIR}[HOVER_LOG] {str(datetime.now())[2:19].replace(":", "_")}.txt'
F_T = ((('constructedSeasonOrdinal', 'constructedClass', 'constructedLevel', 'constructedStep', 'constructedMatchesWon',
         'constructedMatchesLost', 'constructedMatchesDrawn', 'constructedPercentile', 'constructedLeaderboardPlace'),
        '构组'),
       (('limitedSeasonOrdinal', 'limitedClass', 'limitedLevel', 'limitedStep', 'limitedMatchesWon',
         'limitedMatchesLost', 'limitedMatchesDrawn', 'limitedPercentile', 'limitedLeaderboardPlace'), '限制'))
INVENTORY_ITEMS = ('gems', 'gold', 'sealedTokens', 'draftTokens', 'vaultProgress', 'wcTrackPosition',
                   'wcMythic', 'wcRare', 'wcUncommon', 'wcCommon')  # 'boosters'
_10_to_TF = {'1': True, '0': False}
_TF_to_01 = {True: '1', False: '0'}
global_list = []
global_select = 0
side_window_params = {}
mtga_box = (0, 0, 1, 1)


def print_log(contents):
    with open(HOVER_LOG_PATH, 'a', encoding='utf-8') as f:
        if isinstance(contents, tuple):
            for content in contents:
                print(content, file=f)
        else:
            print(contents, file=f)


def screenshot_a():
    toplist, winlist = [], []

    def enum_cb(hwnd, results):
        winlist.append((hwnd, win32gui.GetWindowText(hwnd)))

    win32gui.EnumWindows(enum_cb, toplist)
    mtga_window = [(hwnd, title) for hwnd, title in winlist if 'MTGA' == title]
    if mtga_window:
        hwnd = mtga_window[0][0]
        bbox = win32gui.GetWindowRect(hwnd)
        global mtga_box
        mtga_box = bbox
        # win32gui.SetForegroundWindow(hwnd)
        img = ImageGrab.grab(bbox, all_screens=True)
        return img


class POINT(Structure):
    _fields_ = [('x', c_long), ('y', c_long)]


def mouse_pos():
    pt = POINT()
    windll.user32.GetCursorPos(byref(pt))
    return pt.x, pt.y


print_log(f'【初始】插件：{__version__} {__date__}')
print_log(f'【初始】系统：{platform.platform()}')  # {platform.system()} {platform.version()}
print_log(f'【初始】系统：{str(platform.architecture())}')
APPDATA_DIR = ''
try:
    APPDATA_DIR = os.getenv("APPDATA")
except Exception as _e:
    print_log((f'【严重】获取APPDATA失败：{_e}', _e.args))
    exit()
if len(APPDATA_DIR) < 8 or APPDATA_DIR[-7:] != 'Roaming':
    print_log(f'【严重】获取APPDATA：{APPDATA_DIR}，不知道MTGA日志路径')
    exit()
MTGA_LOG_PATH = os.sep.join([APPDATA_DIR[:-8], 'LocalLow', 'Wizards Of The Coast', 'MTGA', 'Player.log'])
if not os.path.exists(MTGA_LOG_PATH):
    print_log(f'【严重】拼接游戏MTGA日志路径：{MTGA_LOG_PATH}，文件不存在。打开MTGA再试一次。')
    exit()  # 可能没开过游戏，可以尝试建文件夹，建空文件


class MainWindow(Tk):
    class SideWindow(Toplevel):
        def __init__(self):
            super().__init__()
            self.title('轮抽小窗')
            self.loop = None
            global side_window_params
            if 'w' in side_window_params:
                self.width = side_window_params['w']
            else:
                self.width = 180
            if 'h' in side_window_params:
                self.height = side_window_params['h']
            else:
                self.height = 350
            if 'x' in side_window_params:
                self.x = side_window_params['x']
            else:
                self.x = 80
            if 'y' in side_window_params:
                self.y = side_window_params['y']
            else:
                self.y = 520
            self.geometry(f'{str(self.width)}x{str(self.height)}+{str(self.x)}+{str(self.y)}')
            self.protocol('WM_DELETE_WINDOW', self.alt_f)
            self['bg'] = 'white'
            self.wm_attributes('-topmost', True)
            self.local_list = [(0, '', '')]  # 和全局变量初始值不同，运行一次隐藏掉

            self.Tree = Treeview(self, select=BROWSE, columns=('A', 'B'))
            self.Tree['show'] = 'headings'
            self.Tree.column('A', width=30, anchor=W)
            self.Tree.column('B', width=10, anchor=W)
            self.Tree.heading('A', text='牌名')
            self.Tree.heading('B', text='费用')
            self.Tree.grid()
            self.Tree.pack(side=LEFT, expand=1, fill=BOTH)
            self.Tree.bind('<<TreeviewSelect>>', self.treeview_select)
            self.Scrollbar = Scrollbar(self, command=self.Tree.yview)
            self.Tree.config(yscrollcommand=self.Scrollbar.set)
            self.Scrollbar.pack(side=RIGHT, fill=Y)
            self.Button = Button(self, text='点击监测轮抽\n不然关掉小窗', width=13, command=self.side_start)
            self.Button.pack()
            self.Button.place(x=0, y=0)
            self.mainloop()

        def side_start(self):
            self.Button.destroy()
            coroutine1 = self.checking()
            new_loop = asyncio.new_event_loop()
            t = threading.Thread(target=self.get_loop, args=(new_loop,))
            t.daemon = True
            t.start()
            asyncio.run_coroutine_threadsafe(coroutine1, new_loop)

        def save(self):  # 手动关闭小窗口，或者开启检测轮抽后关闭主窗口才会保存信息，不点小窗口按钮直接关闭主窗口不会保存
            try:
                global side_window_params
                side_window_params = {
                    'w': self.winfo_width(),
                    'h': self.winfo_height(),
                    'x': self.winfo_x(),
                    'y': self.winfo_y()
                }
                with open('mtga_hover_draft.ini', 'w', encoding='utf-8') as f:
                    print(dumps(side_window_params, separators=(',', ':')), file=f)
            except Exception as e:
                print_log((f'【严重】存储子窗口配置出错：{e}', e.args))

        def alt_f(self):
            self.save()
            self.withdraw()

        def treeview_select(self, event):
            global global_select
            selection = self.Tree.selection()
            if selection:
                item = self.Tree.item(selection)
                global_select = int(item['text'])

        def get_loop(self, loop):
            self.loop = loop
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()

        async def checking(self):
            while True:
                await asyncio.sleep(0.005)
                global side_window_params
                side_window_params = {
                    'w': self.winfo_width(),
                    'h': self.winfo_height(),
                    'x': self.winfo_x(),
                    'y': self.winfo_y()
                }
                global global_list
                temp_global_list = global_list
                if self.local_list != temp_global_list:
                    self.local_list = temp_global_list
                    self.Tree.delete(*self.Tree.get_children())
                    if temp_global_list:
                        for item in temp_global_list:
                            self.Tree.insert('', END, text=str(item[0]), values=item[1:])
                        self.deiconify()  # 启动时读取之前的轮抽记录会闪若干次= =
                    else:
                        self.withdraw()

    def __init__(self):
        try:
            super().__init__()
            self.title(f'MTGA卡图悬浮工具 {__version__} {__date__}')
            self.loop = None
            self.protocol('WM_DELETE_WINDOW', self.alt_f)
            self.data_dir = os.sep.join(['.', 'card'])
            self.token_dir = os.sep.join(['.', 'token'])
            self.default_png_path = os.path.join('.', 'card', '0.png')
            self.last_size = os.path.getsize(MTGA_LOG_PATH)
            self.last_pos = 0
            self.topmost_mode = True  # mt
            self.alpha_mode = True  # ma
            self.monitor_opponent_mode = False  # mo
            self.withdraw_mode = False  # mw
            self.collection_mode = False  # mc
            self.width = 269  # w
            self.height = 374  # h
            self.x = 10  # x
            self.y = 80  # y
            try:
                with open('mtga_hover.ini', 'r', encoding='utf-8') as f:
                    data = loads(f.read())
            except Exception as e:
                print_log((f'【严重】读取配置文件出错：{e}', e.args))
                data = {}
            if isinstance(data, dict):
                if 'mt' in data:
                    self.topmost_mode = data['mt']
                if 'ma' in data:
                    self.alpha_mode = data['ma']
                if 'mo' in data:
                    self.monitor_opponent_mode = data['mo']
                if 'mw' in data:
                    self.withdraw_mode = data['mw']
                if 'mc' in data:
                    self.collection_mode = data['mc']
                if 'w' in data:
                    self.width = data['w']
                if 'h' in data:
                    self.height = data['h']
                if 'x' in data:
                    self.x = data['x']
                if 'y' in data:
                    self.y = data['y']
            try:
                with open('mtga_hover_draft.ini', 'r', encoding='utf-8') as f:
                    global side_window_params
                    side_window_params = loads(f.read())
            except Exception as e:
                print_log((f'【严重】读取子窗口配置文件出错：{e}', e.args))
                side_window_params = {}
            self.topmost_mode_v = StringVar(value=_TF_to_01[self.topmost_mode])
            self.alpha_mode_v = StringVar(value=_TF_to_01[self.alpha_mode])
            self.monitor_opponent_mode_v = StringVar(value=_TF_to_01[self.monitor_opponent_mode])
            self.withdraw_mode_v = StringVar(value=_TF_to_01[self.withdraw_mode])
            self.collection_mode_v = StringVar(value=_TF_to_01[self.collection_mode])
            self.geometry(f'{str(self.width)}x{str(self.height)}+{str(self.x)}+{str(self.y)}')
            self.single_flag = True
            self['bg'] = 'white'
            self.card_grp_id_2_title_id_map = {}
            self.card_grp_id_2_rarity_map = {}
            self.card_grp_id_2_order_map = {}
            self.card_grp_id_2_cost_map = {}
            self.double_face_map = {}
            self.single_face_map = {}
            self.title_id_2_name_map = {}
            self.art_id_2_ti_map = {}
            self.name_2_title_id_map = {}
            self.card_title_id_set = set()
            self.token_grp_ids_set = set()
            self.instance_id_2_title_id_in_match = {}
            self.instance_id_2_grpid_in_match = {}
            self.out_of_match = False  # 日志暂不提供，先默认False吧
            self.ahash_list = []
            self.dhash_list = []
            self.last_image_0 = None
            self.last_image_x = 0
            self.last_image_y = 0
            self.last_image = None
            self.index = 0
            self.load_mtga_files()
            self.load_plugin_files()
            with Image.open(self.default_png_path) as im:
                self.image = ImageTk.PhotoImage(im)
            self.Label_image_0 = Label(self, image=self.image)
            self.Label_image_0.pack()
            self.Label_image_0.place(x=0, y=0)
            self.Check1 = Checkbutton(self, text='永远置顶，适合游玩。\n直播或录像建议不置顶，捕捉窗口。',
                                      variable=self.topmost_mode_v, width=30)
            self.Check1.pack()
            self.Check1.place(x=10, y=10)
            self.Check2 = Checkbutton(self, text='鼠标进入窗口时高度透明，\n方便查看游戏界面。',
                                      variable=self.alpha_mode_v, width=30)
            self.Check2.pack()
            self.Check2.place(x=10, y=55)
            self.Check3 = Checkbutton(self, text='（无效）监测对手鼠标悬浮，按需勾选。',
                                      variable=self.monitor_opponent_mode_v, width=30)
            self.Check3.pack()
            self.Check3.place(x=10, y=100)
            self.Check4 = Checkbutton(self, text='无悬浮就隐藏窗口，不太建议。', variable=self.withdraw_mode_v, width=30)
            self.Check4.pack()
            self.Check4.place(x=10, y=127)
            self.Check5 = Checkbutton(self, text='全局模式。目前版本需要开启，\n不然只支持轮抽中。', variable=self.collection_mode_v, width=30)
            self.Check5.pack()
            self.Check5.place(x=10, y=155)
            self.Label_text = Label(self, text='MTGA中右上角【Options】，\n左下角【Account】，\r勾选【Detailed Logs】。'
                                               '\r\rmtga_hover.ini存配置\r删除ini=恢复默认\r反馈群：780812745')
            self.Label_text.pack()
            self.Label_text.place(x=10, y=199)
            self.Button = Button(self, text='开始监测', width=9, command=self.main_start)
            self.Button.pack()
            self.Button.place(x=70, y=335)
            self.local_select = 0
            self.last_grp_id = 0
            self.now_grp_id = 0
            self.sw = self.SideWindow()
            self.mainloop()
        except Exception as e:
            print_log((f'【严重】类初始化出错：{e}', e.args))
            exit()

    def alt_f(self):
        try:
            main_window_params = {
                'mt': _10_to_TF[self.topmost_mode_v.get()],
                'ma': _10_to_TF[self.alpha_mode_v.get()],
                'mo': _10_to_TF[self.monitor_opponent_mode_v.get()],
                'mw': _10_to_TF[self.withdraw_mode_v.get()],
                'mc': _10_to_TF[self.collection_mode_v.get()],
                'w': self.winfo_width(),
                'h': self.winfo_height(),
                'x': self.winfo_x(),
                'y': self.winfo_y()
            }
            with open('mtga_hover.ini', 'w', encoding='utf-8') as f:
                print(dumps(main_window_params, separators=(',', ':')), file=f)
            with open('mtga_hover_draft.ini', 'w', encoding='utf-8') as f:
                print(dumps(side_window_params, separators=(',', ':')), file=f)
        except Exception as e:
            print_log((f'【严重】存储配置出错：{e}', e.args))
        self.destroy()

    def load_mtga_files(self):
        if DEBUGGING:
            mtga_files_dir = r'C:\Program Files\Wizards of the Coast\MTGA\MTGA_Data\Downloads\Data\\'
        else:
            mtga_files_dir = os.sep.join(['.', 'MTGA_Data', 'Downloads', 'Data'])  # 不同系统环境的路径可能有区别
        if not os.path.exists(mtga_files_dir):
            print_log(f'【严重】游戏文件路径不存在：{mtga_files_dir}')
            print_log(f'当前路径：{os.path.abspath(".")}')
            print_log(f'发现文件（夹）：{os.listdir(".")}')
            exit()
        files = os.listdir(mtga_files_dir)
        card_title_ids_set = set()
        # 从Manifest读也许更好，但不一定
        for file in files:
            if len(file) > 15 and file[:10] == 'data_cards' and file[-4:] == 'mtga':  # 预更新可能读新文件，行不行？
                with open(os.path.join(mtga_files_dir, file), 'r', encoding='utf-8') as f:
                    data = loads(f.read())
                    for card in data:
                        if card['isToken']:
                            continue  # 衍生物直接从图片文件夹扫，有文件就是支持，没有就当不存在。
                            # self.token_grp_ids_set.add(card['grpid'])
                        linked_type = card['linkedFaceType']
                        grp_id = card['grpid']
                        title_id = card['titleId']
                        rarity = card['rarity']  # 5 4 3 2 1 = M R U C L 后面取负简化排序计算
                        if 5 in card['types']:  # 快速规则：0 无 1-5 白-绿 6 多 7 神器 8 地
                            order = 8  # MTGA没有生物地
                        else:
                            colors = card['colors']
                            if len(colors) == 1:
                                order = colors[0]
                            elif len(colors) == 0:
                                if 1 in card['types']:
                                    order = 7
                                else:
                                    order = 0
                            else:
                                order = 6
                        self.card_grp_id_2_title_id_map[grp_id] = title_id
                        self.card_grp_id_2_rarity_map[grp_id] = - rarity
                        self.card_grp_id_2_order_map[grp_id] = order
                        self.card_grp_id_2_cost_map[grp_id] = card['castingcost'].replace('o', '')
                        card_title_ids_set.add(title_id)
                        if linked_type == 0 or linked_type == 5 or linked_type == 7:  # in (0, 5, 7) 运行效率？
                            continue
                        if linked_type == 6 or linked_type == 8:
                            for face in card['linkedFaces']:
                                self.single_face_map[face] = title_id
                        else:
                            for face in card['linkedFaces']:
                                other_title_id = self.card_grp_id_2_title_id_map.get(face)
                                if other_title_id:
                                    self.double_face_map[title_id] = other_title_id
                                    self.double_face_map[other_title_id] = title_id
                break
        print_log(f'【初始】加载MTGA卡牌，不同名称数量：{len(card_title_ids_set)}')
        for file in files:
            if len(file) > 13 and file[:8] == 'data_loc' and file[-4:] == 'mtga':
                with open(os.path.join(mtga_files_dir, file), 'r', encoding='utf-8') as f:
                    raw = f.read()
                    data = loads(raw)
                    for key in data[0]['keys']:
                        if key['id'] in card_title_ids_set:
                            self.title_id_2_name_map[key['id']] = key['text']
                            self.name_2_title_id_map[key['text']] = key['id']
                break

    def load_plugin_files(self):
        if not os.path.exists(self.data_dir):
            print_log(f'【严重】找不到文件卡图文件夹：{self.data_dir}')
            exit()
        self.load_image()
        if not os.path.exists(self.token_dir):
            print_log(f'【严重】找不到文件衍生物卡图文件夹：{self.token_dir}')
        try:
            token_list = os.listdir(self.token_dir)
            for token in token_list:
                x, y = token.split('.')
                if y == 'png':
                    try:
                        self.token_grp_ids_set.add(int(x))
                    except Exception as e:
                        print_log((f'【严重】加载简中衍生物卡图异常：{e}', e.args))
            print_log(f'【初始】加载简中衍生物卡图：{len(self.token_grp_ids_set)}')
        except Exception as e:
            print_log((f'【严重】加载简中衍生物卡图异常：{e}', e.args))

    def load_image(self):
        try:
            cards_list = os.listdir(self.data_dir)
            for card in cards_list:
                x, y = card.split('.')
                if y == 'png':
                    try:
                        self.card_title_id_set.add(int(x))
                    except Exception as e:
                        print_log((f'【严重】加载简中卡图异常：{e}', e.args))
            self.card_title_id_set.remove(0)
            print_log(f'【初始】加载简中卡图：{len(self.card_title_id_set)}')
        except Exception as e:
            print_log((f'【严重】加载简中卡图异常：{e}', e.args))
            exit()

    def hover(self, obj_id):
        if not self.instance_id_2_title_id_in_match:
            # 对局结束后，字典会清空，不用加载，但是轮抽时需要加载。
            if self.withdraw_mode:
                self.withdraw()
            else:
                self.update_img()  # 可以根据胜负显示不同的图片，或者从随机的趣图池中抽取
            return
        if obj_id == 0:
            if DEBUGGING:
                print_log('【失焦】')
            if self.withdraw_mode:
                self.withdraw()
        else:
            if obj_id in self.instance_id_2_title_id_in_match:
                # 卡牌
                title_id = self.instance_id_2_title_id_in_match[obj_id]
                single_title_id = self.single_face_map.get(title_id)
                if single_title_id:
                    title_id = single_title_id

                if title_id in self.card_title_id_set:
                    double_tile_id = self.double_face_map.get(title_id)
                    if double_tile_id:
                        self.update_img(title_id, double=double_tile_id)
                    else:
                        self.update_img(title_id)
                    if DEBUGGING:
                        print_log(f'【置顶】{obj_id} {title_id}')
                    if self.withdraw_mode:
                        self.deiconify()
                else:
                    self.update_img()
                    print_log(f'【无图】{obj_id} {title_id}')
                    if self.withdraw_mode:
                        self.withdraw()
            elif obj_id in self.instance_id_2_grpid_in_match:
                # 衍生物
                grp_id = self.instance_id_2_grpid_in_match[obj_id]
                if grp_id in self.token_grp_ids_set:
                    self.update_img(grp_id, True)
                if self.withdraw_mode:
                    self.deiconify()
            else:
                if DEBUGGING:
                    print_log(f'【没存】{obj_id} {len(self.instance_id_2_title_id_in_match)}'
                              f'{self.instance_id_2_title_id_in_match.keys()}')
                if self.withdraw_mode:
                    self.withdraw()

    def update_img(self, g_id=0, token=False, double=0):
        try:
            if self.single_flag:
                w_o, h_o = self.winfo_width(), self.winfo_height()
                w_rate, h_rate = max(159, w_o - 4) / 265, max(222, h_o - 4) / 370
                rate = min(w_rate, h_rate)
                w_n, h_n = round(265 * rate), round(370 * rate)
            else:
                w_o, h_o = self.winfo_width(), self.winfo_height()
                w_rate, h_rate = max(318, w_o - 4) / 530, max(222, h_o - 4) / 370
                rate = min(w_rate, h_rate)
                w_n, h_n = round(265 * rate), round(370 * rate)
            if token:
                img_path = os.path.join('.', 'token', str(g_id) + '.png')
            else:
                img_path = os.path.join('.', 'card', str(g_id) + '.png')
            if double:
                d_img_path = os.path.join('.', 'card', str(double) + '.png')
                with Image.open(img_path) as im1:
                    result = Image.new('RGBA', (w_n * 2, h_n))
                    result.paste(im1.convert('RGBA').resize((w_n, h_n), Image.LANCZOS), (0, 0))
                    with Image.open(d_img_path) as im2:
                        result.paste(im2.convert('RGBA').resize((w_n, h_n), Image.LANCZOS), (w_n, 0))
                    self.image = ImageTk.PhotoImage(result)
                    self.Label_image_0.configure(image=self.image)
                    self.Label_image_0.image = self.image
                    self.single_flag = False
                    w_n *= 2
                    self.geometry(f'{str(w_n + 4)}x{str(h_n + 4)}')
            else:
                with Image.open(img_path) as im:
                    self.image = ImageTk.PhotoImage(im.resize((w_n, h_n), Image.LANCZOS))
                    self.Label_image_0.configure(image=self.image)
                    self.Label_image_0.image = self.image
                self.single_flag = True
                self.geometry(f'{str(w_n + 4)}x{str(h_n + 4)}')
        except Exception as e:
            print_log((f'【严重】更新卡图失败：{e}', e.args))

    def instance_change_name(self, a, b, c):
        a_name = self.title_id_2_name_map.get(a)
        b_name = self.title_id_2_name_map.get(b)
        if not a_name and b_name:
            self.instance_id_2_title_id_in_match[c] = b_name
        if a_name:
            a_name = f'({a_name})'
        else:
            a_name = ''
        if b_name:
            b_name = f'({b_name})'
        else:
            b_name = ''
        print_log(f'【改名】物件({c}) 从 {a}{a_name} 变成 {b}{b_name}')

    def obj_grp_handler(self, obj, instance_id):
        obj_type = obj.get('type')
        if obj_type == 'GameObjectType_Ability':
            grp_id = obj.get('objectSourceGrpId')
        else:
            grp_id = obj.get('grpId')
        if grp_id:
            title_id = self.card_grp_id_2_title_id_map.get(grp_id)
            if title_id:
                title_id_in_map = self.instance_id_2_title_id_in_match.get(instance_id)
                if title_id_in_map:
                    if title_id_in_map != title_id and DEBUGGING:  # 最好总是检查？
                        self.instance_change_name(title_id_in_map, title_id, instance_id)
                else:
                    if title_id in self.card_title_id_set:
                        self.instance_id_2_title_id_in_match[instance_id] = title_id
        else:
            if DEBUGGING:
                print_log(f'【问题】instance_id({instance_id})，类型({obj_type})，没grp_id')

    def game_state_message_handler(self, event_game_state_message):
        game_objs = event_game_state_message.get('gameObjects')
        if game_objs:
            for obj in game_objs:
                instance_id = obj.get('instanceId')
                if instance_id:
                    title_id = obj.get('name')
                    grpid = obj.get('grpId')
                    if title_id:  # 忽略不认识的卡牌
                        title_id_in_map = self.instance_id_2_title_id_in_match.get(instance_id)
                        if title_id_in_map:
                            if title_id_in_map != title_id and DEBUGGING:  # 最好总是检查？
                                self.instance_change_name(title_id_in_map, title_id, instance_id)
                        else:
                            if title_id in self.card_title_id_set:  # 会有文件里没有的吗？威世智，没有不可能
                                self.instance_id_2_title_id_in_match[instance_id] = title_id
                            else:
                                s_title_id = self.single_face_map.get(grpid)
                                if s_title_id:
                                    if s_title_id in self.card_title_id_set:
                                        self.instance_id_2_title_id_in_match[instance_id] = s_title_id
                    else:
                        self.obj_grp_handler(obj, instance_id)
                    self.instance_id_2_grpid_in_match[instance_id] = grpid  # 给衍生物用，所有物件都存进来

    def ui_message_handler(self, ui_message):
        # seat_ids = ui_message.get('seatIds')
        on_hover = ui_message.get('onHover')
        if on_hover:
            object_id = on_hover.get('objectId')
            if object_id:
                self.now_grp_id = object_id
        else:
            self.now_grp_id = 0

    def log_data_handler(self, data):
        global global_list
        global global_select
        match_game_room_state_event = data.get('matchGameRoomStateChangedEvent')
        if match_game_room_state_event:
            self.instance_id_2_title_id_in_match = {}
            self.instance_id_2_grpid_in_match = {}
            self.now_grp_id = 0
            room_info = match_game_room_state_event['gameRoomInfo']
            room_config = room_info['gameRoomConfig']
            match_id = room_config['matchId']
            match_mode = room_config['eventId']
            state_type = room_info['stateType']
            if state_type == 'MatchGameRoomStateType_Playing':
                players_string = ''
                for player in room_config['reservedPlayers']:
                    players_string += player['playerName'] + ' '
                print_log(f'【清空】开始：编号 {match_id} 模式 {match_mode} 玩家 {players_string}')
                self.out_of_match = False
            elif state_type == 'MatchGameRoomStateType_MatchCompleted':
                print_log(f'【清空】结束：编号 {match_id} 模式 {match_mode}')
                self.out_of_match = True

        # v0.0.0中判断对局开始
        # match_endpoint_host = match_game_room_state_event.get('matchEndpointHost')
        # if match_endpoint_host:
        #     self.cards_in_match = {}

        game_state_message = data.get('gameStateMessage')
        if game_state_message:
            self.game_state_message_handler(game_state_message)

        payload = data.get('payload')
        if payload and isinstance(payload, dict):  # 如果不是字典，可能是：空，牌组，赛制，当前活动
            ui_message = payload.get('uiMessage')
            if ui_message:
                system_seat_ids = payload.get('systemSeatIds')
                if system_seat_ids is None or self.monitor_opponent_mode:
                    self.ui_message_handler(ui_message)
            player_id = payload.get('playerId')
            if player_id:
                try:
                    constructed_season_ordinal = payload.get('constructedSeasonOrdinal')  # 赛季空隙会怎样？
                    if constructed_season_ordinal:
                        for i in range(2):
                            j = [payload[F_T[i][0][n]] for n in range(9)]
                            k = j[4] + j[5] + j[6]
                            print_log(f'【信息】{F_T[i][1]}赛制 第{j[0]}赛季 {j[1]}-{j[2]}-{j[3]}(#{j[8]}|{j[7]}%) '
                                      f'{j[4]}胜{j[5]}负{j[6]}平 '
                                      f'胜率{0 if k == 0 else (j[4] + j[6] / 2) / k}')
                except Exception as e:
                    print_log((f'【严重】读玩家赛季信息出错：{e}', e.args))
                try:
                    vault_progress = payload.get('vaultProgress')  # 赛季空隙会怎样？
                    if vault_progress:
                        j = [payload[INVENTORY_ITEMS[n]] for n in range(10)]
                        print_log(f'【信息】{j[0]}宝石 {j[1]}金币 {j[2]}现开|{j[3]}轮抽票 {j[4]}%宝库进度 {j[5]}保底万用开包位 '
                                  f'{j[6]}M|{j[7]}R|{j[8]}U|{j[9]}C万用牌')
                        self.out_of_match = True
                except Exception as e:
                    print_log((f'【严重】读玩家收藏信息出错：{e}', e.args))
            draft_status = payload.get('DraftStatus')
            if draft_status:
                if draft_status == 'Draft.PickNext':
                    draft_pack = payload.get('DraftPack')
                    self.pack_2_list(draft_pack)
                elif draft_status == 'Draft.Complete':
                    global_list = []
                    global_select = 0
            pick_completed = payload.get('IsPickingCompleted')
            if pick_completed:
                global_list = []
                global_select = 0
        pack_cards = data.get('PackCards')
        if pack_cards:
            cards = pack_cards.split(',')
            self.pack_2_list(cards)
        # 玩家操作，最好注释掉再导出
        # if DEBUGGING:
        #     perform_action_resp = payload.get('performActionResp')
        #     if perform_action_resp:
        #         print_log(f'【操作】{dumps(perform_action_resp, separators=(",",":"))}')
        gre_to_client_event = data.get('greToClientEvent')
        if gre_to_client_event:
            gre_to_client_messages = gre_to_client_event.get('greToClientMessages')
            if gre_to_client_messages:
                for message in gre_to_client_messages:
                    ui_message = message.get('uiMessage')
                    if ui_message:
                        system_seat_ids = message.get('systemSeatIds')
                        # 可能没有systemSeatIds，这时有systemSeatId
                        if system_seat_ids is None or self.monitor_opponent_mode:
                            self.ui_message_handler(ui_message)

                    game_state_message = message.get('gameStateMessage')
                    if game_state_message:
                        self.game_state_message_handler(game_state_message)

                    actions_available_req = message.get('actionsAvailableReq')
                    if actions_available_req:
                        actions = actions_available_req.get('actions')
                        if actions:
                            for action in actions:
                                instance_id = action.get('instanceId')
                                if instance_id:
                                    self.obj_grp_handler(action, instance_id)
                                else:
                                    pass  # 存在没id的action咯？
        connect_resp = data.get('connectResp')
        if connect_resp:
            self.out_of_match = False



    def pack_2_list(self, draft_pack):
        global global_list
        draft_p = [int(card) for card in draft_pack]
        draft_sorted = sorted(draft_p, key=lambda x: (
            self.card_grp_id_2_rarity_map[x],
            self.card_grp_id_2_order_map[x],
            self.title_id_2_name_map[self.card_grp_id_2_title_id_map[x]]))
        global_list = [(card, self.title_id_2_name_map[self.card_grp_id_2_title_id_map[card]],
                        self.card_grp_id_2_cost_map[card]) for card in draft_sorted]

    async def log_handler(self):
        while True:
            await asyncio.sleep(0.005)
            try:
                with open(MTGA_LOG_PATH, 'r', encoding='utf-8') as f:
                    f.seek(self.last_pos)
                    while True:
                        txt = f.read()
                        self.last_pos = f.tell()
                        if txt:  # 有更新就不显示
                            # print_log(f'[{str(datetime.now())[2:17]}] 读取{len(txt)}个字符')  # 测试用
                            json_start_pos = 0
                            brackets_count = 0
                            for i in range(len(txt)):
                                if brackets_count == 0:
                                    if txt[i] == '{':
                                        json_start_pos = i
                                        brackets_count += 1
                                else:
                                    if txt[i] == '{':
                                        brackets_count += 1
                                    elif txt[i] == '}':
                                        brackets_count -= 1
                                        if brackets_count == 0:
                                            json_raw = txt[json_start_pos:i + 1]
                                            data = loads(json_raw)
                                            if DEBUGGING:
                                                print_log((f'[{str(datetime.now())[2:19]}]', dumps(
                                                    data, separators=(',', ':'))))
                                            if isinstance(data, dict):
                                                self.log_data_handler(data)
                        else:
                            try:
                                now_size = os.path.getsize(MTGA_LOG_PATH)
                                if now_size < self.last_size:  # 通常是因为开着插件重启游戏
                                    print_log('【重要】MTGA日志变小，似乎重启了MTGA。')
                                    self.last_size = now_size
                                    # self.cards_in_match = {}  # 可能正在对局中
                                    f.seek(0)
                            except Exception as e:
                                print_log((f'【严重】获取MTGA日志大小失败：{e}', e.args))
                            if global_select != self.local_select:
                                self.local_select = global_select
                                title_id = self.card_grp_id_2_title_id_map[self.local_select]
                                double_tile_id = self.double_face_map.get(title_id)
                                if double_tile_id:
                                    self.update_img(title_id, double=double_tile_id)
                                else:
                                    self.update_img(title_id)
                        if self.collection_mode:  # and self.out_of_match v0.1.8开放对局内识别
                            # v0.1.6 按照1920x1080定的参数
                            image_new_0 = screenshot_a()
                            if image_new_0 is None:
                                self.last_image_0 = None
                                self.last_image_x = 0
                                self.last_image_y = 0
                                self.last_image = None
                            else:
                                if self.last_image is not None:
                                    _x, _y = image_new_0.size
                                    image_x = _x // 4  # 1920/4=480  # 性能差，减少数据提速
                                    image_y = _y // 4  # 1080/4=270
                                    image_new = image_new_0.resize((image_x, image_y), Image.ANTIALIAS)
                                    if self.out_of_match:
                                        image_diff = ImageChops.difference(image_new, self.last_image).point(
                                            lambda n: 255 if n else 0).convert('L')
                                    else:
                                        image_diff = ImageChops.difference(image_new, self.last_image).point(
                                            lambda n: 255 if n > 18 else 0).convert('L')
                                    image_diff_load = image_diff.load()
                                    image_x, image_y = image_diff.size
                                    x = [0] * image_x
                                    y = [0] * image_y
                                    for i in range(image_x):
                                        for j in range(image_y):
                                            if image_diff_load[i, j] != 0:
                                                x[i] += 1
                                                y[j] += 1
                                    xm = [1 if x[i] * 5 > image_y else 0 for i in range(image_x)]  # 收藏 2 对局 5
                                    ym = [1 if y[i] * 9 > image_x else 0 for i in range(image_y)]  # 收藏 5 对局 7
                                    # print_log(''.join([str(ii) for ii in xm]))
                                    # print_log(''.join([str(ii) for ii in ym]))
                                    if DEBUGGING:
                                        image_diff.save('./tem/' + str(self.index) + '.png')
                                    self.index += 1
                                    try:
                                        x1_out = xm.index(1)
                                        xd_out = xm[x1_out:].index(0)
                                        x2_out = x1_out + xd_out
                                        y1_out = ym.index(1)
                                        yd_out = ym[y1_out:].index(0)
                                        if xd_out * 9 > image_x:  # 水平距离超过七分之一
                                            global mtga_box
                                            b_x1, b_y1, b_x2, b_y2 = mtga_box
                                            mouse_x, mouse_y = mouse_pos()
                                            x_rate = (mouse_x - b_x1) / (b_x2 - b_x1)
                                            y_rate = (mouse_y - b_y1) / (b_y2 - b_y1)
                                            if 0 <= y_rate <= 1 and x_rate >= 0:
                                                if x_rate < 0.5:
                                                    x_sign = 0
                                                elif x_rate <= 1:
                                                    x_sign = 1
                                                else:
                                                    x_sign = 2
                                            else:
                                                x_sign = 3
                                            passed = True
                                            if x_sign == 0:
                                                y1 = y1_out * 4 - 5
                                                yd = yd_out * 4 + 10
                                                y2 = y1 + yd
                                                x1 = x1_out * 4 - 5
                                                x2 = x1 + int(yd / 1.4) + 10
                                            elif x_sign == 1:
                                                y1 = y1_out * 4 - 5
                                                yd = yd_out * 4 + 10
                                                y2 = y1 + yd
                                                x2 = x2_out * 4 + 5
                                                x1 = x2 - int(yd / 1.4) - 10
                                            else:
                                                passed = False
                                            if passed:
                                                box = (x1, y1, x2, y2)
                                                image_new_0_crop = image_new_0.crop(box)
                                                image_diff_0 = ImageChops.difference(image_new_0_crop,
                                                                                     self.last_image_0.crop(box)).point(
                                                    lambda n: 255 if n else 0).convert('L')
                                                diff_x, diff_y = image_diff_0.size
                                                x_80 = diff_x * 0.65  # 待测参数 [0.70, 0.95]
                                                y_80 = diff_y * 0.65
                                                image_diff_0_load = image_diff_0.load()
                                                x = [0] * diff_x
                                                y = [0] * diff_y
                                                for i in range(diff_x):
                                                    for j in range(diff_y):
                                                        if image_diff_0_load[i, j] != 0:
                                                            x[i] += 1
                                                            y[j] += 1
                                                xm = [1 if x[i] > y_80 else 0 for i in range(diff_x)]  # 520
                                                ym = [1 if y[i] > x_80 else 0 for i in range(diff_y)]  # 330
                                                try:
                                                    x1 = xm.index(1)
                                                    x2 = diff_x - xm[::-1].index(1)
                                                    y1 = ym.index(1)
                                                    y2 = diff_y - ym[::-1].index(1)
                                                    if x_sign == 0:
                                                        x2 = x1 + int((y2 - y1) / 1.4) + 1
                                                    elif x_sign == 1:
                                                        x1 = x2 - int((y2 - y1) / 1.4) - 1
                                                    if y2 - y1 > 210 and x2 - x1 > 150:
                                                        image_crop = image_new_0_crop.crop((x1, y1, x2, y2))
                                                        art_crop = image_crop.resize((150, 210), Image.ANTIALIAS).crop((11, 24, 139, 117))
                                                        art_hash = dhash(art_crop, 16)
                                                        hash_compare = [(item[0], art_hash - item[1]) for item in self.dhash_list]
                                                        hash_min = min(hash_compare, key=lambda xx: xx[1])
                                                        title_id = hash_min[0]
                                                        if DEBUGGING:
                                                            image_crop.save('./temp/' + str(self.index) + '.png')
                                                            art_crop.save('./temp/' + str(self.index) + 'a.png')
                                                            name = self.title_id_2_name_map.get(title_id)
                                                            print('[dhash]', self.index, name, title_id, hash_min[1],
                                                                  mouse_x, mouse_y, x_rate, y_rate)
                                                        self.index += 1
                                                        if hash_min[1] < 80:
                                                            double_tile_id = self.double_face_map.get(title_id)
                                                            if double_tile_id:
                                                                self.update_img(title_id, double=double_tile_id)
                                                            else:
                                                                self.update_img(title_id)
                                                        elif hash_min[1] < 90:
                                                            art_hash = average_hash(art_crop, 16)
                                                            hash_compare = [(item[0], art_hash - item[1]) for item in self.ahash_list]
                                                            hash_min = min(hash_compare, key=lambda xx: xx[1])
                                                            title_id = hash_min[0]
                                                            if DEBUGGING:
                                                                image_crop.save('./temp/' + str(self.index) + '.png')
                                                                art_crop.save('./temp/' + str(self.index) + 'a.png')
                                                                name = self.title_id_2_name_map.get(title_id)
                                                                print('[dhash]', self.index, name, title_id, hash_min[1],
                                                                      mouse_x, mouse_y, x_rate, y_rate)
                                                            self.index += 1
                                                            if hash_min[1] < 40:
                                                                double_tile_id = self.double_face_map.get(title_id)
                                                                if double_tile_id:
                                                                    self.update_img(title_id, double=double_tile_id)
                                                                else:
                                                                    self.update_img(title_id)
                                                except ValueError:
                                                    pass
                                    except ValueError:
                                        pass
                                    except Exception as e:
                                        print_log((f'【严重】图片分析出错：{e}', e.args))
                                    self.last_image_x = image_x
                                    self.last_image_y = image_y
                                    self.last_image_0 = image_new_0
                                    self.last_image = image_new
                        if self.now_grp_id != self.last_grp_id:
                            self.last_grp_id = self.now_grp_id
                            self.hover(self.last_grp_id)
                        await asyncio.sleep(0.005)
            except Exception as e:
                print_log((f'【严重】读MTGA日志出错：{e}', e.args))

    def alpha_max(self, event):
        self.attributes('-alpha', 1.0)

    def alpha_min(self, event):
        self.attributes('-alpha', 0.05)

    def get_loop(self, loop):
        self.loop = loop
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def main_start(self):
        self.topmost_mode = _10_to_TF[self.topmost_mode_v.get()]
        self.alpha_mode = _10_to_TF[self.alpha_mode_v.get()]
        self.monitor_opponent_mode = _10_to_TF[self.monitor_opponent_mode_v.get()]
        self.withdraw_mode = _10_to_TF[self.withdraw_mode_v.get()]
        self.collection_mode = _10_to_TF[self.collection_mode_v.get()]
        if self.topmost_mode:
            self.wm_attributes('-topmost', True)
        if self.alpha_mode:
            self.bind('<Enter>', self.alpha_min)
            self.bind('<Leave>', self.alpha_max)
        if self.collection_mode:
            try:
                with open('ahash_data.json', 'r', encoding='utf-8') as f:
                    _hash_list = loads(f.read())
                    self.ahash_list = [[item[0], hex_to_hash(item[1])] for item in _hash_list]
                with open('dhash_data.json', 'r', encoding='utf-8') as f:
                    _hash_list = loads(f.read())
                    self.dhash_list = [[item[0], hex_to_hash(item[1])] for item in _hash_list]
            except Exception as e:
                print_log((f'【严重】加载哈希数组出错：{e}', e.args))
                self.collection_mode = False
            self.last_image_0 = screenshot_a()
            if self.last_image_0 is None:
                self.last_image_x = 0
                self.last_image_y = 0
                self.last_image = None
            else:
                _x, _y = self.last_image_0.size
                self.last_image_x = _x // 4
                self.last_image_y = _y // 4
                self.last_image = self.last_image_0.resize((self.last_image_x, self.last_image_y), Image.ANTIALIAS)
        self.update_img()
        self.Check1.destroy()
        self.Check2.destroy()
        self.Check3.destroy()
        self.Check4.destroy()
        self.Check5.destroy()
        self.Button.destroy()
        self.Label_text.destroy()
        coroutine1 = self.log_handler()
        new_loop = asyncio.new_event_loop()
        t = threading.Thread(target=self.get_loop, args=(new_loop,))
        t.daemon = True
        t.start()
        asyncio.run_coroutine_threadsafe(coroutine1, new_loop)


if __name__ == '__main__':
    this_main = MainWindow()
