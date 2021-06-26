#!/usr/bin/python3
"""Monitor MTGA logs, display Simplified-Chinese images of on-hovered cards in real time."""
__license__ = 'GPL'
__version__ = 'v0.1.4'
__date__ = '2021-06-26'
__credits__ = ['https://www.iyingdi.com', 'https://www.scryfall.com', 'https://gatherer.wizards.com']
__qq_group__ = '780812745'
__status__ = 'Developing'

from tkinter import *
from tkinter.ttk import *
from PIL import Image, ImageTk
from json import loads, dumps
from datetime import datetime
import os
import platform
import asyncio
import threading

DEBUGGING = False  # 测试开关
HOVER_LOG_DIR = os.sep.join(['.', 'log', ''])
if not os.path.exists(HOVER_LOG_DIR):
    os.mkdir(HOVER_LOG_DIR)
HOVER_LOG_PATH = f'{HOVER_LOG_DIR}[HOVER_LOG] {str(datetime.now())[2:19].replace(":", "_")}.txt'
F_T = (
    (('constructedSeasonOrdinal', 'constructedClass', 'constructedLevel', 'constructedStep', 'constructedMatchesWon',
      'constructedMatchesLost', 'constructedMatchesDrawn', 'constructedPercentile', 'constructedLeaderboardPlace'),
     '构组'),
    (('limitedSeasonOrdinal', 'limitedClass', 'limitedLevel', 'limitedStep', 'limitedMatchesWon',
      'limitedMatchesLost', 'limitedMatchesDrawn', 'limitedPercentile', 'limitedLeaderboardPlace'), '限制')
)
INVENTORY_ITEMS = ('gems', 'gold', 'sealedTokens', 'draftTokens', 'vaultProgress', 'wcTrackPosition',
                   'wcMythic', 'wcRare', 'wcUncommon', 'wcCommon')  # 'boosters'
_10_to_TF = {'1': True, '0': False}
_TF_to_01 = {True: '1', False: '0'}
global_list = []
global_select = 0
side_state = {}


def print_log(contents):
    with open(HOVER_LOG_PATH, 'a', encoding='utf-8') as f:
        if isinstance(contents, tuple):
            for content in contents:
                print(content, file=f)
        else:
            print(contents, file=f)


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
            self.title('A')
            self.loop = None
            global side_state
            if 'w' in side_state:
                self.width = side_state['w']
            else:
                self.width = 180
            if 'h' in side_state:
                self.height = side_state['h']
            else:
                self.height = 350
            if 'x' in side_state:
                self.x = side_state['x']
            else:
                self.x = 80
            if 'y' in side_state:
                self.y = side_state['y']
            else:
                self.y = 520
            self.geometry(f'{str(self.width)}x{str(self.height)}+{str(self.x)}+{str(self.y)}')
            self.protocol('WM_DELETE_WINDOW', self.alt_f)
            self['bg'] = 'white'
            self.wm_attributes('-topmost', True)
            self.list_box_str = StringVar()
            self.local_list = []

            self.List_box = Listbox(self, listvariable=self.list_box_str)
            self.List_box.pack(side=LEFT, expand=1, fill=BOTH)
            self.List_box.bind('<<ListboxSelect>>', self.listbox_click)
            self.Scrollbar = Scrollbar(self, command=self.List_box.yview)
            self.List_box.config(yscrollcommand=self.Scrollbar.set)
            self.Scrollbar.pack(side=RIGHT, fill=Y)
            self.Button = Button(self, text='监测轮抽', width=9, command=self.side_start)
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
                global side_state
                side_state = {
                    'w': self.winfo_width(),
                    'h': self.winfo_height(),
                    'x': self.winfo_x(),
                    'y': self.winfo_y()
                }
                with open('mtga_hover_draft.ini', 'w', encoding='utf-8') as f:
                    print(dumps(side_state, separators=(',', ':')), file=f)
            except Exception as e:
                print_log((f'【严重】存储子窗口配置出错：{e}', e.args))

        def alt_f(self):
            self.save()
            self.withdraw()

        def listbox_click(self, event):
            global global_select
            global_select = self.List_box.get(self.List_box.curselection())

        def get_loop(self, loop):
            self.loop = loop
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()

        async def checking(self):
            global global_list
            while True:
                await asyncio.sleep(0.01)
                global side_state
                side_state = {
                    'w': self.winfo_width(),
                    'h': self.winfo_height(),
                    'x': self.winfo_x(),
                    'y': self.winfo_y()
                }
                temp_global_list = global_list
                if self.local_list != temp_global_list:
                    self.local_list = temp_global_list
                    self.List_box.delete(0, END)
                    if temp_global_list:
                        for item in temp_global_list:
                            self.List_box.insert(END, item)
                        self.deiconify()
                    else:
                        self.withdraw()

    def __init__(self):
        try:
            super().__init__()
            self.title(f'MTGA卡图悬浮工具 {__version__} {__date__}')
            self.protocol('WM_DELETE_WINDOW', self.alt_f4)
            self.loop = None
            self.data_dir = os.sep.join(['.', 'card'])
            self.token_dir = os.sep.join(['.', 'token'])
            self.default_png_path = os.path.join('.', 'card', '0.png')
            self.last_size = os.path.getsize(MTGA_LOG_PATH)
            self.last_pos = 0
            self.initialized = not DEBUGGING  # True表示还没初始化完毕，没必要更新卡图
            try:
                with open('mtga_hover.ini', 'r', encoding='utf-8') as f:
                    data = loads(f.read())
                    if 'mt' in data:
                        self.topmost_mode = data['mt']
                    if 'ma' in data:
                        self.alpha_mode = data['ma']
                    if 'mo' in data:
                        self.monitor_opponent_mode = data['mo']
                    if 'mw' in data:
                        self.withdraw_mode = data['mw']
                    if 'w' in data:
                        self.width = data['w']
                    if 'h' in data:
                        self.height = data['h']
                    if 'x' in data:
                        self.x = data['x']
                    if 'y' in data:
                        self.y = data['y']
            except Exception as e:
                print_log((f'【严重】读取配置文件出错：{e}', e.args))
                self.topmost_mode = True  # mt
                self.alpha_mode = True  # ma
                self.monitor_opponent_mode = False  # mo
                self.withdraw_mode = False  # mw
                self.width = 269  # w
                self.height = 374  # h
                self.x = 10  # x
                self.y = 80  # y
            try:
                with open('mtga_hover_draft.ini', 'r', encoding='utf-8') as f:
                    global side_state
                    side_state = loads(f.read())
            except Exception as e:
                print_log((f'【严重】读取子窗口配置文件出错：{e}', e.args))
            self.topmost_mode_v = StringVar(value=_TF_to_01[self.topmost_mode])
            self.alpha_mode_v = StringVar(value=_TF_to_01[self.alpha_mode])
            self.monitor_opponent_mode_v = StringVar(value=_TF_to_01[self.monitor_opponent_mode])
            self.withdraw_mode_v = StringVar(value=_TF_to_01[self.withdraw_mode])
            self.geometry(f'{str(self.width)}x{str(self.height)}+{str(self.x)}+{str(self.y)}')
            self.single_flag = True
            self['bg'] = 'white'
            self.card_grp_id_2_title_id_map = {}
            self.card_grp_id_2_rarity_map = {}
            self.card_grp_id_2_order_map = {}
            self.card_grp_id_2_cost_map = {}  # 下个版本弄
            self.double_face_map = {}
            self.single_face_map = {}
            self.title_id_2_name_map = {}
            self.name_2_title_id_map = {}
            self.card_title_id_set = set()
            self.token_grp_ids_set = set()
            self.instance_id_2_title_id_in_match = {}
            self.instance_id_2_grpid_in_match = {}
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

            self.Check3 = Checkbutton(self, text='监测对手鼠标悬浮，按需勾选。',
                                      variable=self.monitor_opponent_mode_v, width=30)
            self.Check3.pack()
            self.Check3.place(x=10, y=100)

            t_t = '无悬浮就隐藏窗口，不太建议。'
            self.Check4 = Checkbutton(self, text=t_t, variable=self.withdraw_mode_v, width=30)
            self.Check4.pack()
            self.Check4.place(x=10, y=127)

            t_t = 'MTGA中右上角【Options】，\n左下角【Account】，\r勾选【Detailed Logs】。' \
                  '\r\rmtga_hover.ini存配置\r删除ini=恢复默认\r反馈群：780812745'
            self.Label_text = Label(self, text=t_t)
            self.Label_text.pack()
            self.Label_text.place(x=10, y=154)

            self.Button = Button(self, text='开始监测', width=9, command=self.change_form_state)
            self.Button.pack()
            self.Button.place(x=70, y=300)

            self.local_select = ''
            self.sw = self.SideWindow()

            self.mainloop()
        except Exception as e:
            print_log((f'【严重】类初始化出错：{e}', e.args))
            exit()

    def alt_f4(self):
        try:
            state = {
                'mt': _10_to_TF[self.topmost_mode_v.get()],
                'ma': _10_to_TF[self.alpha_mode_v.get()],
                'mo': _10_to_TF[self.monitor_opponent_mode_v.get()],
                'mw': _10_to_TF[self.withdraw_mode_v.get()],
                'w': self.winfo_width(),
                'h': self.winfo_height(),
                'x': self.winfo_x(),
                'y': self.winfo_y()
            }
            with open('mtga_hover.ini', 'w', encoding='utf-8') as f:
                print(dumps(state, separators=(',', ':')), file=f)
            with open('mtga_hover_draft.ini', 'w', encoding='utf-8') as f:
                print(dumps(side_state, separators=(',', ':')), file=f)
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
                            continue
                            # self.token_grp_ids_set.add(card['grpid'])
                            # 衍生物直接从图片文件夹扫，有文件就是支持，没有就当不存在。
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

    def hover(self, obj_id):
        if self.initialized:
            # 初始化时，默认不加载图片
            return
        if not self.instance_id_2_title_id_in_match:
            # 对局结束后，字典会清空，不用加载
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
                    f'【没存】{obj_id} {len(self.instance_id_2_title_id_in_match)} {self.instance_id_2_title_id_in_match.keys()} '
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
                self.hover(object_id)
        else:
            self.hover(0)

    def log_data_handler(self, data):
        global global_list
        global global_select
        match_game_room_state_event = data.get('matchGameRoomStateChangedEvent')
        if match_game_room_state_event:
            self.instance_id_2_title_id_in_match = {}
            self.instance_id_2_grpid_in_match = {}
            self.hover(0)
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
            elif state_type == 'MatchGameRoomStateType_MatchCompleted':
                print_log(f'【清空】结束：编号 {match_id} 模式 {match_mode}')

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
                except Exception as e:
                    print_log((f'【严重】读玩家收藏信息出错：{e}', e.args))
            draft_status = payload.get('DraftStatus')
            if draft_status:
                if draft_status == 'Draft.PickNext':
                    draft_pack = payload.get('DraftPack')
                    draft_pack = [int(card) for card in draft_pack]
                    draft_sorted = sorted(draft_pack, key=lambda x: (
                        self.card_grp_id_2_rarity_map[x],
                        self.card_grp_id_2_order_map[x],
                        self.title_id_2_name_map[self.card_grp_id_2_title_id_map[x]]))
                    global_list = [self.title_id_2_name_map[
                                       self.card_grp_id_2_title_id_map[card]] for card in draft_sorted]
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
            draft_pack = [int(card) for card in cards]
            draft_sorted = sorted(draft_pack, key=lambda x: (
                self.card_grp_id_2_rarity_map[x],
                self.card_grp_id_2_order_map[x],
                self.title_id_2_name_map[self.card_grp_id_2_title_id_map[x]]))
            global_list = [self.title_id_2_name_map[
                               self.card_grp_id_2_title_id_map[int(card)]] for card in draft_sorted]
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

    async def log_handler(self):
        while True:
            await asyncio.sleep(0)
            try:
                with open(MTGA_LOG_PATH, 'r', encoding='utf-8') as f:
                    f.seek(self.last_pos)
                    while True:
                        txt = f.read()
                        self.last_pos = f.tell()
                        if txt:
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
                            if self.initialized:
                                self.initialized = False
                            try:
                                now_size = os.path.getsize(MTGA_LOG_PATH)
                                if now_size < self.last_size:  # 通常是因为开着插件重启游戏
                                    print_log('【重要】MTGA日志变小，似乎重启了MTGA。')
                                    self.last_size = now_size
                                    # self.cards_in_match = {}  # 可能正在对局中
                                    f.seek(0)
                            except Exception as e:
                                print_log((f'【严重】获取MTGA日志大小失败：{e}', e.args))
                            if global_select != self.local_select and global_select in self.name_2_title_id_map:
                                self.local_select = global_select
                                self.update_img(self.name_2_title_id_map[global_select])
                            await asyncio.sleep(0.01)  # 明显降低CPU使用，略微增加刷新延迟
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

    def change_form_state(self):
        self.topmost_mode = _10_to_TF[self.topmost_mode_v.get()]
        self.alpha_mode = _10_to_TF[self.alpha_mode_v.get()]
        self.monitor_opponent_mode = _10_to_TF[self.monitor_opponent_mode_v.get()]
        self.withdraw_mode = _10_to_TF[self.withdraw_mode_v.get()]
        if self.topmost_mode:
            self.wm_attributes('-topmost', True)
        if self.alpha_mode:
            self.bind('<Enter>', self.alpha_min)
            self.bind('<Leave>', self.alpha_max)
        self.update_img()
        self.Check1.destroy()
        self.Check2.destroy()
        self.Check3.destroy()
        self.Check4.destroy()
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
'''
★★★版本说明★★
v0.1.4 轮抽卡牌简单排序。存储子窗口设置。修补代码。
v0.1.3 存储设置。依靠全局变量+子窗口实现轮抽支持。
v0.1.2 透明模式。
v0.1.1 补全衍生物，修改饼干牌卡图，支持双面牌显示。
v0.1.0 补全卡牌，补充衍生物。调整初始化方式。
v0.0.8 图片不再频闪。支持显示213种衍生物。
v0.0.7 隐藏命令行。
v0.0.6 记得用PY38。
v0.0.5 检查除数。忘了用PY38。
v0.0.4 改进入口选项设置。默认捕捉对手鼠标悬浮。将玩家收藏和赛季信息输出到插件日志。
v0.0.3 补全MTGA日志的读取编码。修复漏牌没存的漏洞。降低CPU使用。
v0.0.2 改进插件日志函数。改用python3.8打包。
v0.0.1 修补代码。
v0.0.0 凑合发布。

★★★已知问题★★★
1.系统环境兼容差。
2.改变窗口没有立刻缩放图片。
3.放大图片太模糊，可以准备更大的数据包。
4.部分卡图质量差。衍生物原画版本对不上。
5.MTGA排序可以尽量模拟，但本身有很多问题，

★★★也许可以★★★
1.轮抽卡牌评分。
2.现开和轮抽后组牌建议。
3.改进玩家收藏、赛季战绩和类似信息的整理、展示和存储。
'''
