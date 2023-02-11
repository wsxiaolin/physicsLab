#coding=utf-8
from _fileGlobals import *
from electricity._elementPin import *

# 老版本连接导线函数，不推荐使用
def old_crt_wire(SourceLabel, SourcePin : int, TargetLabel, TargetPin : int, color = "蓝") -> None: # SourceLabel : Union[_element, tuple]
    SourcePin, TargetPin = int(SourcePin), int(TargetPin)
    if (isinstance(SourceLabel, tuple) and len(SourceLabel) == 3):
        SourceLabel = elements_Address[SourceLabel]
    elif (SourceLabel not in elements_Address.values()):
        raise RuntimeError("SourceLabel must be a Positon or self")
    if (isinstance(TargetLabel, tuple) and len(TargetLabel) == 3):
        TargetLabel = elements_Address[TargetLabel]
    elif (TargetLabel not in elements_Address.values()):
        raise RuntimeError("TargetLabel must be a Positon or self")

    if (color not in ["黑", "蓝", "红", "绿", "黄"]):
        raise RuntimeError("illegal color")
    wires.append({"Source": SourceLabel._arguments["Identifier"], "SourcePin": SourcePin,
                   "Target": TargetLabel._arguments["Identifier"], "TargetPin": TargetPin,
                   "ColorName": f"{color}色导线"})

# 检查函数参数是否是导线
def _check_typeWire(func):
    def result(SourcePin, TargetPin, color : str = '蓝') -> None:
        try:
            if isinstance(SourcePin, element_Pin) and isinstance(TargetPin, element_Pin):
                if (color not in ["黑", "蓝", "红", "绿", "黄"]):
                    raise RuntimeError("illegal color")

                func(SourcePin, TargetPin, color)
        except:
            raise RuntimeError('Error type of input function argument')
    return result

# 新版连接导线
@_check_typeWire
def crt_wire(SourcePin, TargetPin, color: str = '蓝') -> None:
    wires.append({"Source": SourcePin.element_self._arguments["Identifier"], "SourcePin": SourcePin.pinLabel,
                   "Target": TargetPin.element_self._arguments["Identifier"], "TargetPin": TargetPin.pinLabel,
                   "ColorName": f"{color}色导线"})

# 删除导线
@_check_typeWire
def del_wire(SourcePin, TargetPin, color : str = '蓝') -> None:
    a_wire = {"Source": SourcePin.element_self._arguments["Identifier"], "SourcePin": SourcePin.pinLabel,
                   "Target": TargetPin.element_self._arguments["Identifier"], "TargetPin": TargetPin.pinLabel,
                   "ColorName": f"{color}色导线"}
    if (a_wire in wires):
        wires.remove(a_wire)
    else:
        raise RuntimeError("Unable to delete a nonexistent wire")