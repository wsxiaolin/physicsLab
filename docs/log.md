## 历史重大成就
1. 2023-1-5 改存档实验成功
2. 2023-1-12 physicsLab上传至gitee
3. 2023-2-25 引入git管理physicsLab
4. 2023-3-17 physicsLab上传至pypi（不可使用）
5. 2023-3-19 physicsLab上传至pypi的版本可以使用
6. 2023-4-8 physicsLab上传至github
7. 2023-4-15 python调用dll实验成功
8. 2023-4-30 增加模块化电路：D触流水灯
9. 2023-5-4 ```python build``` c拓展实验成功
10. 2023-6-18 将```@element_Init_HEAD```改为metaclass: ```electricityMeta```
11. 2023-6-18 c/cpp调用Python实验成功

## 1.3.0
1. 增加android的支持
2. 增加对电与磁实验的简单支持
3. 增加了模块化电路命名空间union
4. 增加了模块化电路音乐电路与music命名空间
5. experiment()新增write参数

## 1.3.0.1 & 1.3.1
1.  增加对`P-MOSFET`元件的支持
2.  增加`from physicsLab.union import *`来省略union命名空间的书写
3.  增加单个元件判断是否为元件坐标系的方法：`self.is_elementXYZ`
4.  新增只读非门`Const_NoGate`
5.  `crt_Wire`支持传入英文color参数
6.  新增`_fileGlobals`命名空间（不推荐访问）

## 1.3.2
1.  实装Midi类（与piece类的转换与导出midi，播放midi）
2.  Track类增加append方法
3.  优化了乐器矩阵的基础架构
4.  `self.set_Position`增加了对元件坐标系的支持
5.  增加了`Midi.set_tempo`方法

## 1.3.3
1.  完成`Midi.write_plm`的主要逻辑

## 1.3.4
1.  进一步完善了Midi类（translate_to_piece）
2.  优化了plmidi的播放效果（使用pybind11代替了Python.h）

## 1.3.5
1.  改进`Midi.sound`的播放机制,使`plmidi`与`pygame`的播放效果相同

## 1.3.6
1.  使用了物实`v2.4.7`的特性优化模块化音乐电路，这也意味着旧版本物实不支持`physicsLab`生成的电路
2.  修复了颜色打印的Bug，增加了`close_color_print()`以关闭颜色打印
3.  更改了在`Android`上创建存档的行为，同时理论上支持了其他操作系统
4.  更新了`write_Experiment`的`extra_filepath`
5.  更新了`Piece.write_midi`, `Piece.traslate_to_midi`
6.  更新了简单乐器播放多个音符的机制:`Simple_Instrument.add_note`与获取简单乐器的和弦:`Simple_Instrument.get_chord()`
7.  实装了`Chord`类，同时禁止了旧有的和弦表示方式

## 1.3.7
1.  修复了由`typing`导致的问题
2.  实装了支持`Chord`的`Piece.write_midi`

# 1.4.0
1. `traslate_to_midi`增加了对音量的支持
2. 移除了`Note.time=0`的表示方式
3. 将`.plm.py`更名为`.pl.py`
4. 将传统的函数式实验存档读写改为了`class Experiment`的形式
5. 在一些小的行为上进行了优化, 使编写更加直观

# 1.4.1
1. 优化了`Experiment.delete()`的行为
2. 优化了`Player`生成音符的音量的效果

# 1.4.2
1.  新增了`get_Experiment`
2.  修复了`Experiment.read`的bug

# 1.4.3
1.  `plmidi`新增播放进度条
2.  一些bugfix

# 1.4.4
1.  与`plmidi`兼容性更好的调用方式
2.  部分优化了和弦的音量生成规则, 但更好的音量生成需等待物实增加单独控制简单乐器中的每个音符的音量的支持
3.  删除导线不再需要提供颜色信息
4.  全局设置警告状态
5.  `Simple_Instrument`新增在init时设置和弦的方法

# 1.4.5
1.  增加了更多的元件
2.  重复连接的导线将不会被连接
3.  删除旧式函数调用的`xxx_Experiment`等api (不兼容更新)
4.  删除自动增加`# -*- coding: utf-8 -*-`的机制

# 1.4.6
1.  修复重复连接导线时的bug
2.  将`music.Midi`的`read_midopy`移动到`__init__`中
3.  修复`export`的bug
4.  将`Piece.translate_to_midi`改名为`Piece.to_midi`，`Midi.translate_to_piece`改名为`Midi.to_piece`（不兼容更新）

# 1.4.7
1.  新增`Experiment.merge`
2.  元件新增`experiment`属性
3.  `get_Element`增加`default`参数
4.  重命名`unit`为`lib` （不兼容更新）
5.  `crt_Element`新增`*args`与`**kwargs`用来传递创建一些元件需要的额外的参数

# 1.4.8
1.  删除`Piece`类的冗余参数
2.  新增休止符类`Rest_symbol`
3.  `to_piece`新增`is_optimize`参数，用来控制是否优化为和弦
4.  `to_piece`新增`is_fix_strange_note`参数，用来控制是否修正一些midi中奇怪的音符
5.  新增设置环境变量`PHYSICSLAB_HOME_PATH`
6.  增加`crt_Wire`自连接导线的检查

# 1.4.9
1.  重命名`Midi.to_piece`的`is_fix_strange_note`参数为`fix_strange_note`（不兼容更新）
2.  更智能的`Midi`的`div_time`参数的自动推测

# 1.4.10
1.  `Midi`类支持直接导入文件对象(io.IOBase)
2.  `Midi.to_piece`与`Midi.write_plpy`新增`notes_filter`参数，该参数要求传入一个2个参数（第一个为instrument, 第二个为velocity），输出为bool的函数，用来过滤音符
3.  `Note`支持`C3`这种风格的构造
4.  增加`lib.Rising_edge_trigger`, `lib.Falling_edge_trigger`, `lib.Edge_trigger`
5.  增加`Experiment.paused`
6.  增加对`web-api`的操作的更高级api
7.  增加`Tag`(enum class)
8.  增加`Category`
9.  增加`lib.Super_AndGate`, `lib.Tick_Counter`

# 1.4.11
1.  更多`web`api
2.  增加`Experiment.read_from_web`
3.  增加`Experiment.upload`, `Experiment.update`

# 1.4.12
1.  增加`lib.MultiElements`等等
2.  增强了减号连接导线的功能(`Pin` - `unitPin`)
3.  修复`CircuitBase.is_bigElement`
4.  新增`Experiment.edit_tags`
5.  新增对`sensor`的支持

## 1.4.13
1.  `web.get_comments`增加`take`与`skip`参数

## 1.4.14
1.  公开了`id_to_time`
2.  新增`get_warned_messages`, `get_banned_messages`

# 1.4.15
1.  重命名`set_Position`为`set_position`, `set_Rotation`为`set_rotation`, `get_Position`为`get_position`, `get_Index`为`get_index` (不兼容更新)
2.  实装部分对天体物理实验的支持
3.  电学原件新增`.rename`方法
4.  电阻与电阻箱增加`set_resistor`
5.  修复了`music`的鼓点生成规则的bug
6.  新增`web.CommentsIter`

# 1.4.16
1.  完善了`web.CommentsIter`
2.  新增了电与磁实验的支持

# 1.4.17
1.  新增`web.get_avatar`, `get_avatars`
