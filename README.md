# mtga_hover
* 监测MTGA的输出日志和游戏画面，尽可能在小窗口中显示优质的简中卡图，方便新玩家认识卡牌。
# 使用说明
1. 正确安装MTGA。
2. 将`mtga_hover.exe`、`card/`文件夹和`token/`文件夹放在与`MTGA.exe`平齐的路径。
3. 打开`mtga_hover.exe`，勾选所需功能，单击按钮开始运行。
4. 如不需支持轮抽，关闭子窗口即可，否则需点击按钮开始运行。
5. `mtga_hover.ini`和`mtga_hover_draft.ini`记录最近运行的窗口信息。
6. `hash_data.json`用于支持收藏和组牌界面的显示。
# 已知问题
1. 系统环境兼容差。
2. 改变窗口没有立刻缩放图片。
3. 放大图片太模糊。可以准备更大的数据包。用更好的滤镜。
4. 部分卡图质量差。衍生物原画版本对不上。
5. MTGA排序可以尽量模拟，但本身有很多问题。
6. LOG缺轮抽第一包信息，威shit智。
7. 继续提升对收藏和组牌界面的支持。
# 也许可以
1. 轮抽卡牌评分。
2. 现开和轮抽后组牌建议。
3. 改进玩家收藏、赛季战绩和类似信息的整理、展示和存储。
# 版本说明
* v0.1.6 初步支持收藏和组牌界面的显示。快速移入可提高成功率。失败移出重试。目前只支持1920x1080全屏。
* v0.1.5 大幅减少无意义的更新卡图操作。轮抽小窗显示法术力费用。轮抽支持显示双面牌。
* v0.1.4 轮抽卡牌简单排序。存储子窗口设置。修补代码。
* v0.1.3 存储设置。依靠全局变量+子窗口实现轮抽支持。
* v0.1.2 透明模式。
* v0.1.1 补全衍生物，修改饼干牌卡图，支持双面牌显示。
* v0.1.0 补全卡牌，补充衍生物。调整初始化方式。
* v0.0.8 图片不再频闪。支持显示213种衍生物。
* v0.0.7 隐藏命令行。
* v0.0.6 记得用PY38。
* v0.0.5 检查除数。忘了用PY38。
* v0.0.4 改进入口选项设置。默认捕捉对手鼠标悬浮。将玩家收藏和赛季信息输出到插件日志。
* v0.0.3 补全MTGA日志的读取编码。修复漏牌没存的漏洞。降低CPU使用。
* v0.0.2 改进插件日志函数。改用python3.8打包。
* v0.0.1 修补代码。
* v0.0.0 凑合发布。