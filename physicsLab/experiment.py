# -*- coding: utf-8 -*-
import os
import json
import copy
import time
import gzip
import requests
import platform
import tempfile

from datetime import datetime
from enum import unique, Enum

from physicsLab import plAR
from physicsLab import  _tools
from physicsLab import errors
from physicsLab import savTemplate
from physicsLab import _colorUtils
from .web import User, _check_response
from .enums import Category, Tag
from .savTemplate import Generate
from .enums import ExperimentType
from .typehint import Union, Optional, List, Dict, numType, Self

def id_to_time(id: str) -> datetime:
    ''' 从 用户id/实验id 中获取其对应的时间
    '''
    seconds = int(id[0:8], 16)
    return datetime.fromtimestamp(seconds)

class stack_Experiment:
    data: List["Experiment"] = []

    def __new__(cls):
        return cls

    @classmethod
    def push(cls, data: "Experiment") -> None:
        if not isinstance(data, Experiment):
            raise TypeError

        cls.data.append(data)

    @classmethod
    def top(cls) -> "Experiment":
        if len(cls.data) == 0:
            raise errors.ExperimentError("no experiment can be operated(experiment stack is empty)")

        return cls.data[-1]

    @classmethod
    def pop(cls) -> "Experiment":
        res = cls.top()
        cls.data.pop()
        return res

def get_Experiment() -> "Experiment":
    ''' 获取当前正在操作的存档 '''
    return stack_Experiment.top()

class Experiment:
    ''' 实验（存档）类 '''
    if os.environ.get("PHYSICSLAB_HOME_PATH"):
        SAV_ROOT_DIR = os.environ["PHYSICSLAB_HOME_PATH"]
    else:
        if platform.system() == "Windows":
            from getpass import getuser
            SAV_ROOT_DIR = f"C:/Users/{getuser()}/AppData/LocalLow/CIVITAS/Quantum Physics/Circuit"
        else:
            SAV_ROOT_DIR = "physicsLabSav"

    @unique
    class PathLoadMode(Enum):
        ''' 打开存档时输入字符串的解析模式 '''
        sav_name = 0 # 存档的名字(在物实内给存档取的名字)
        file_name = 1 # 存档对应的文件名, 完整路径为 os.path.join(FILE_HEAD, file_name)
        path = 2 # 用户自己提供的存档的完整路径

    @property
    def is_open_or_crt(self) -> bool:
        return self.is_opened or self.is_crted

    def __init__(self,
                 sav_name: Optional[str] = None,
                 experiment_type: ExperimentType = ExperimentType.Circuit, # 仅在创建实验时有效
                 ) -> None:
        self.is_opened: bool = False
        self.is_crted: bool = False
        self.is_readed: bool = False

        self.SAV_PATH: Optional[str] = None # 存档的完整路径
        # 通过坐标索引元件
        self.elements_Position: Dict[tuple, list] = {}  # key: self._position, value: List[self...]
        # 通过index（元件生成顺序）索引元件
        from .elementBase import ElementBase
        self.Elements:List[ElementBase] = []

        if sav_name is not None:
            self.open_or_crt(sav_name, experiment_type)

    def get_element_from_identifier(self, identifier: str):
        ''' 通过 原件的["Identifier"]获取元件的引用 '''
        for element in self.Elements:
            assert hasattr(element, "data")
            if element.data["Identifier"] == identifier: # type: ignore -> has attr .data
                return element
        raise errors.ExperimentError

    def __read_CameraSave(self, camera_save: str) -> None:
        self.CameraSave = json.loads(camera_save)
        temp = eval(f"({self.CameraSave['VisionCenter']})")
        self.VisionCenter: _tools.position = _tools.position(temp[0], temp[2], temp[1]) # x, z, y
        temp = eval(f"({self.CameraSave['TargetRotation']})")
        self.TargetRotation: _tools.position = _tools.position(temp[0], temp[2], temp[1]) # x, z, y

    def __open(self) -> None:
        self.is_opened = True
        self.__read_CameraSave(self.PlSav["Experiment"]["CameraSave"])

        if self.PlSav["Summary"] is None:
            self.PlSav["Summary"] = savTemplate.Circuit["Summary"]

        if self.PlSav["Experiment"]["Type"] == ExperimentType.Circuit.value:
            self.experiment_type = ExperimentType.Circuit
            # 该实验是否是元件坐标系
            self.is_elementXYZ: bool = False
            # 元件坐标系的坐标原点
            self.elementXYZ_origin_position: _tools.position = _tools.position(0, 0, 0)
            self.Wires: set = set() # Set[Wire] # 存档对应的导线
            # 存档对应的StatusSave, 存放实验元件，导线（如果是电学实验的话）
            self.StatusSave: dict = {"SimulationSpeed": 1.0, "Elements": Generate, "Wires": Generate}

        elif self.PlSav["Experiment"]["Type"] == ExperimentType.Celestial.value:
            self.experiment_type = ExperimentType.Celestial
            self.StatusSave: dict = {"MainIdentifier": None, "Elements": {}, "WorldTime": 0.0,
                                    "ScalingName": "内太阳系", "LengthScale": 1.0, "SizeLinear": 0.0001,
                                    "SizeNonlinear": 0.5, "StarPresent": False, "Setting": None}

        elif self.PlSav["Experiment"]["Type"] == ExperimentType.Electromagnetism.value:
            self.experiment_type = ExperimentType.Electromagnetism
            self.StatusSave: dict = {"SimulationSpeed": 1.0, "Elements": []}
        else:
            raise errors.InternalError

    def open(self,
             sav_name : str,
             path_load_mode: PathLoadMode = PathLoadMode.sav_name,
             ) -> Self:
        ''' [[该方法为构造函数]]
            打开一个指定的sav文件 (支持输入本地实验的名字或sav文件名)
            @param sav_name: 存档的名字或存档的文件名(.sav)
            @param is_path: True则将sav_name作为存档的路径
        '''
        if self.is_open_or_crt:
            raise errors.ExperimentHasOpenError

        if not isinstance(sav_name, str) \
            or not isinstance(path_load_mode, Experiment.PathLoadMode):
            raise TypeError

        stack_Experiment.push(self)

        # 直接通过文件路径进行导入
        if path_load_mode == Experiment.PathLoadMode.file_name \
                or path_load_mode == Experiment.PathLoadMode.path:

            if path_load_mode == Experiment.PathLoadMode.file_name:
                sav_name = os.path.join(Experiment.SAV_ROOT_DIR, sav_name)
            self.SAV_PATH = os.path.abspath(sav_name)

            if not os.path.exists(self.SAV_PATH):
                stack_Experiment.pop()
                raise errors.ExperimentNotExistError(f"{self.SAV_PATH} not found")

            _temp = _open_sav(self.SAV_PATH)

            assert _temp is not None

            if "Experiment" in _temp.keys():
                self.PlSav = _temp
            else: # 读取物实导出的存档只含有.sav的Experiment部分
                if _temp["Type"] == ExperimentType.Circuit.value:
                    self.PlSav = savTemplate.Circuit
                elif _temp["Type"] == ExperimentType.Celestial.value:
                    self.PlSav = savTemplate.Celestial
                elif _temp["Type"] == ExperimentType.Electromagnetism.value:
                    self.PlSav = savTemplate.Electromagnetism
                else:
                    raise errors.InternalError

                self.PlSav["Experiment"] = _temp
            self.__open()
        elif path_load_mode == Experiment.PathLoadMode.sav_name: # 通过存档名导入
            filename = search_Experiment(sav_name)

            if filename is None:
                stack_Experiment.pop()
                raise errors.ExperimentNotExistError(f'No such experiment "{sav_name}"')

            self.SAV_PATH = os.path.join(Experiment.SAV_ROOT_DIR, filename)
            self.PlSav = search_Experiment.sav
            self.__open()
        else:
            raise AssertionError("Please bug report")

        return self

    def __crt(self,
              sav_name: str,
              experiment_type: ExperimentType = ExperimentType.Circuit
    ) -> None:
        self.is_crted = True
        self.experiment_type = experiment_type

        filename = f"{_tools.randString(34)}.sav"
        self.SAV_PATH = os.path.join(Experiment.SAV_ROOT_DIR, filename)

        if self.experiment_type == ExperimentType.Circuit:
            self.is_elementXYZ: bool = False
            # 元件坐标系的坐标原点
            self.elementXYZ_origin_position: _tools.position = _tools.position(0, 0, 0)
            self.PlSav: dict = copy.deepcopy(savTemplate.Circuit)
            self.Wires: set = set() # Set[Wire] # 存档对应的导线
            # 存档对应的StatusSave, 存放实验元件，导线（如果是电学实验的话）
            self.StatusSave: dict = {"SimulationSpeed": 1.0, "Elements": Generate, "Wires": Generate}
            self.CameraSave: dict = {
                "Mode": 0, "Distance": 2.7, "VisionCenter": Generate, "TargetRotation": Generate
            }
            self.VisionCenter: _tools.position = _tools.position(0, -0.45, 1.08)
            self.TargetRotation: _tools.position = _tools.position(50, 0, 0)

        elif self.experiment_type == ExperimentType.Celestial:
            self.PlSav: dict = copy.deepcopy(savTemplate.Celestial)
            self.StatusSave: dict = {
                "MainIdentifier": None, "Elements": {}, "WorldTime": 0.0,
                "ScalingName": "内太阳系", "LengthScale": 1.0, "SizeLinear": 0.0001,
                "SizeNonlinear": 0.5, "StarPresent": False, "Setting": None
            }
            self.CameraSave: dict = {
                "Mode": 2, "Distance": 2.75, "VisionCenter": Generate, "TargetRotation": Generate
            }
            self.VisionCenter: _tools.position = _tools.position(0 ,0, 1.08)
            self.TargetRotation: _tools.position = _tools.position(90, 0, 0)

        elif self.experiment_type == ExperimentType.Electromagnetism:
            self.PlSav: dict = copy.deepcopy(savTemplate.Electromagnetism)
            self.StatusSave: dict = {"SimulationSpeed": 1.0, "Elements": []}
            self.CameraSave: dict = {
                "Mode": 0, "Distance": 3.25, "VisionCenter": Generate, "TargetRotation": Generate
            }
            self.VisionCenter: _tools.position = _tools.position(0, 0 ,0.88)
            self.TargetRotation: _tools.position = _tools.position(90, 0, 0)
        else:
            raise errors.InternalError

        self.entitle(sav_name)

    def crt(self,
            sav_name: str,
            experiment_type: ExperimentType = ExperimentType.Circuit,
            force_crt: bool = False,
    ) -> Self:
        ''' [[该方法为构造函数]]
            创建存档
            @sav_name: 存档名
            @experiment_type: 实验类型
            @force_crt: 不论实验是否已经存在,强制创建
        '''
        if self.is_open_or_crt:
            raise errors.ExperimentHasOpenError

        if not isinstance(sav_name, str) \
            or not isinstance(experiment_type, ExperimentType) \
            or not isinstance(force_crt, bool):
            raise TypeError

        search = search_Experiment(sav_name)
        if not force_crt and search is not None:
            raise errors.ExperimentHasExistError
        elif force_crt and search is not None:
            path = os.path.join(Experiment.SAV_ROOT_DIR, search)
            os.remove(path)
            if os.path.exists(path.replace(".sav", ".jpg")): # 用存档生成的实验无图片，因此可能删除失败
                os.remove(path.replace(".sav", ".jpg"))

        stack_Experiment.push(self)

        self.__crt(sav_name, experiment_type)
        return self

    def open_or_crt(self,
                    sav_name: str,
                    experiment_type: ExperimentType = ExperimentType.Circuit,
    ) -> Self:
        ''' [[该方法为构造函数]]
            先尝试打开实验, 若失败则创建实验
            @sav_name: 只支持传入存档名
            @experiment_type: 实验类型, 仅在创建实验时有效
        '''
        if self.is_open_or_crt:
            raise errors.ExperimentHasOpenError

        if not isinstance(sav_name, str) \
            or not isinstance(experiment_type, ExperimentType):
            raise TypeError

        stack_Experiment.push(self)

        filename = search_Experiment(sav_name)
        if filename is not None:
            self.SAV_PATH = os.path.join(Experiment.SAV_ROOT_DIR, filename)
            self.PlSav = search_Experiment.sav
            self.__open()
        else:
            self.__crt(sav_name, experiment_type)
        return self

    def __read_element(self, _elements: list) -> None:
        assert isinstance(_elements, list)

        for element in _elements:
            position = eval(f"({element['Position']})")
            x, y, z = position[0], position[2], position[1]

            # 实例化对象
            from physicsLab.element import crt_Element

            if self.experiment_type == ExperimentType.Circuit:
                if element["ModelID"] == "Simple Instrument":
                    from .circuit.elements.otherCircuit import Simple_Instrument
                    obj = Simple_Instrument(
                        x, y, z, elementXYZ=False,
                        instrument=int(element["Properties"]["乐器"]),
                        pitch=int(element["Properties"]["音高"]),
                        velocity=element["Properties"]["音量"],
                        rated_oltage=element["Properties"]["额定电压"],
                        is_ideal_model=bool(element["Properties"]["理想模式"]),
                        is_single=bool(element["Properties"]["脉冲"])
                    )
                    for attr, val in element["Properties"].items():
                        if attr.startswith("音高"):
                            obj.add_note(int(val))
                else:
                    obj = crt_Element(element["ModelID"], x, y, z, elementXYZ=False)
                    obj.data["Properties"] = element["Properties"]
                    obj.data["Properties"]["锁定"] = 1.0
                # 设置角度信息
                rotation = eval(f'({element["Rotation"]})')
                r_x, r_y, r_z = rotation[0], rotation[2], rotation[1]
                obj.set_rotation(r_x, r_y, r_z)
                obj.data['Identifier'] = element['Identifier']

            elif self.experiment_type == ExperimentType.Celestial:
                obj = crt_Element(element["Model"], x, y, z)
                obj.data = element
            elif self.experiment_type == ExperimentType.Electromagnetism:
                obj = crt_Element(element["ModelID"], x, y, z)
                obj.data = element
            else:
                raise errors.InternalError

    def __read_wire(self, _wires: list) -> None:
        assert self.experiment_type == ExperimentType.Circuit

        from .circuit.wire import Wire, Pin
        for wire_dict in _wires:
            self.Wires.add(
                Wire(
                    Pin(self.get_element_from_identifier(wire_dict["Source"]), wire_dict["SourcePin"]),
                    Pin(self.get_element_from_identifier(wire_dict["Target"]), wire_dict["TargetPin"]),
                    wire_dict["ColorName"][0] # e.g. "蓝"
                )
            )

    def read(self, warning_status: Optional[bool] = None) -> Self:
        ''' 读取实验已有状态 '''
        if not self.is_open_or_crt:
            raise errors.ExperimentNotOpenError
        if self.is_readed:
            errors.warning("experiment has been read", warning_status)
            return self
        self.is_readed = True
        if self.is_crted:
            errors.warning("can not read because you create this experiment", warning_status)
            return self

        status_sav = json.loads(self.PlSav["Experiment"]["StatusSave"])

        if self.experiment_type == ExperimentType.Circuit:
            self.__read_element(status_sav["Elements"])
        elif self.experiment_type == ExperimentType.Celestial:
            self.__read_element(list(status_sav["Elements"].values()))
        elif self.experiment_type == ExperimentType.Electromagnetism:
            self.__read_element(status_sav["Elements"])
        else:
            raise errors.InternalError

        if self.experiment_type == ExperimentType.Circuit:
            self.__read_wire(status_sav["Wires"])

        return self

    def read_from_web(self,
                      id: str,
                      category: Category,
                      user: Optional[User] = None,
                      no_read_experiment_status: bool = False,
                      ) -> Self:
        ''' 获取已经发布到物实的实验的实验状态(包括元件, 导线, 发布后的标题, 实验介绍)

            由于存档名与发布后的标题可以不同, 因此该方法只会修改发布后的标题, 不会修改存档名
            @sav_name: 获取到的实验保存到本地存档的名字
            @id: 物实实验的id
            @category: 实验区还是黑洞区
        '''
        if not self.is_open_or_crt:
            raise errors.ExperimentHasOpenError
        if not isinstance(id, str) or \
            not isinstance(category, Category) or \
            not isinstance(no_read_experiment_status, bool):
            raise TypeError

        if user is None:
            user = User()

        _summary = user.get_summary(id, category)["Data"]
        if not no_read_experiment_status:
            _experiment = user.get_experiment(_summary["ContentID"])["Data"]
            _StatusSave = json.loads(_experiment["StatusSave"])
            self.__read_CameraSave(_experiment["CameraSave"])
            self.__read_element(_StatusSave["Elements"])
            self.__read_wire(_StatusSave["Wires"])

        del _summary["$type"]
        _summary["Category"] = category.value
        self.PlSav["Summary"] = _summary
        return self

    def __write(self) -> None:
        self.PlSav["Experiment"]["CreationDate"] = int(time.time() * 1000)
        self.PlSav["Summary"]["CreationDate"] = int(time.time() * 1000)

        self.CameraSave["VisionCenter"] = f"{self.VisionCenter.x},{self.VisionCenter.z},{self.VisionCenter.y}"
        self.CameraSave["TargetRotation"] = f"{self.TargetRotation.x},{self.TargetRotation.z},{self.TargetRotation.y}"
        self.PlSav["Experiment"]["CameraSave"] = json.dumps(self.CameraSave)

        if self.experiment_type == ExperimentType.Circuit:
            self.StatusSave["Elements"] = [a_element.data for a_element in self.Elements]
            self.StatusSave["Wires"] = [a_wire.release() for a_wire in self.Wires]
        elif self.experiment_type == ExperimentType.Celestial:
            self.StatusSave["Elements"] = {a_element.data["Identifier"] : a_element.data
                                           for a_element in self.Elements}
        elif self.experiment_type == ExperimentType.Electromagnetism:
            self.StatusSave["Elements"] = [a_element.data for a_element in self.Elements]
        else:
            raise errors.InternalError

        self.PlSav["Experiment"]["StatusSave"] = json.dumps(self.StatusSave, ensure_ascii=False, separators=(',', ': '))

    def write(self,
              extra_filepath: Optional[str] = None,
              ln: bool = False,
              no_pop: bool = False,
    ) -> Self:
        ''' 以物实存档的格式导出实验
            @param extra_filepath: 自定义保存存档的路径, 但仍会在 SAV_PATH_ROOT 下保存存档
            @param ln: 是否将StatusSave字符串换行
            @param no_pop: write之后不退出对该存档的操作
        '''
        def _format_StatusSave(stringJson: str) -> str:
            ''' 将StatusSave字符串换行
                注意: 换行之后的结果不符合json语法(json无多行字符串)
                     但物实可以读取
                     因此, 仅用于调试
                     暂时只支持电学存档
            '''
            stringJson = stringJson.replace( # format element json
                "{\\\"ModelID", "\n      {\\\"ModelID"
            )
            stringJson = stringJson.replace( # format end element json
                "DiagramRotation\\\": 0}]", "DiagramRotation\\\": 0}\n    ]"
            )
            stringJson = stringJson.replace("{\\\"Source", "\n      {\\\"Source")
            stringJson = stringJson.replace("色导线\\\"}]}", "色导线\\\"}\n    ]}")
            return stringJson

        if self.is_open_or_crt is not True:
            raise errors.ExperimentError("write before open or crt")

        if self.is_opened:
            status: str = "update"
        else: # self.is_crted
            status: str = "create"

        if not no_pop:
            self.is_opened = False
            self.is_crted = False

        assert self.SAV_PATH is not None

        if not no_pop:
            stack_Experiment.pop()

        self.__write()

        context: str = json.dumps(self.PlSav, indent=2, ensure_ascii=False, separators=(',', ':'))
        if ln:
            context = _format_StatusSave(context)

        with open(self.SAV_PATH, "w", encoding="utf-8") as f:
            f.write(context)
        if extra_filepath is not None:
            if not extra_filepath.endswith(".sav"):
                extra_filepath += ".sav"
            with open(extra_filepath, "w", encoding="utf-8") as f:
                f.write(context)

        if self.experiment_type == ExperimentType.Circuit:
            _colorUtils.color_print(
                f"Successfully {status} experiment \"{self.PlSav['InternalName']}\"! "
                f"{self.Elements.__len__()} elements, {self.Wires.__len__()} wires.",
                color=_colorUtils.COLOR.GREEN
            )
        elif self.experiment_type == ExperimentType.Celestial \
                or self.experiment_type == ExperimentType.Electromagnetism:
            _colorUtils.color_print(
                f"Successfully {status} experiment \"{self.PlSav['InternalName']}\"! "
                f"{self.Elements.__len__()} elements.",
                color=_colorUtils.COLOR.GREEN
            )
        else:
            raise errors.InternalError

        return self

    def delete(self, warning_status: Optional[bool] = None) -> None:
        ''' 删除存档 '''
        if not self.is_open_or_crt:
            raise errors.ExperimentNotOpenError

        assert self.SAV_PATH is not None

        if os.path.exists(self.SAV_PATH): # 如果一个实验被创建但还未被写入, 就会触发错误
            os.remove(self.SAV_PATH)
            _colorUtils.color_print(
                f"Successfully delete experiment {self.PlSav['InternalName']}({self.SAV_PATH})!",
                _colorUtils.COLOR.BLUE
            )
        elif not self.is_crted:
            if warning_status is None:
                warning_status = errors._warning_status
            errors.warning(
                f"experiment {self.PlSav['InternalName']}({self.SAV_PATH}) do not exist.",
                warning_status
            )

        if os.path.exists(self.SAV_PATH.replace(".sav", ".jpg")): # 用存档生成的实验无图片，因此可能删除失败
            os.remove(self.SAV_PATH.replace(".sav", ".jpg"))

        stack_Experiment.pop()

    def exit(self) -> None:
        ''' 退出实验而不进行任何操作 '''
        stack_Experiment.pop()

    def entitle(self, sav_name: str) -> Self:
        ''' 对存档名进行重命名 '''
        if not isinstance(sav_name, str):
            raise TypeError

        if not self.is_open_or_crt:
            raise errors.ExperimentNotOpenError

        self.PlSav["Summary"]["Subject"] = sav_name
        self.PlSav["InternalName"] = sav_name

        return self

    def show(self) -> Self:
        ''' 使用notepad打开改存档 '''
        if not self.is_open_or_crt:
            raise errors.ExperimentNotOpenError

        assert self.is_open_or_crt

        if platform.system() != "Windows":
            return self

        self.__write()
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as f:
            f.write(json.dumps(self.PlSav, indent=2, ensure_ascii=False, separators=(',', ': ')))

        os.system(f'notepad "{f.name}"')
        os.remove(f.name)
        return self

    def edit_publish_info(self,
                title: Optional[str] = None,
                introduction: Optional[str] = None,
                wx: bool = False,
                ) -> Self:
        ''' 生成与发布实验有关的存档内容
            @param title: 标题
            @param introduction: 简介
            @param wx: 是否续写简介
        '''
        def introduce_Experiment(introduction: Union[str, None]) -> None:
            '''  发布实验时输入实验介绍 '''
            if introduction is not None:
                if self.PlSav['Summary']['Description'] is not None and wx:
                    self.PlSav['Summary']['Description'] += introduction.split('\n')
                else:
                    self.PlSav['Summary']['Description'] = introduction.split('\n')

        def name_Experiment(title: Union[str, None]) -> None:
            ''' 发布实验时输入实验标题 '''
            if title is not None:
                self.PlSav['Summary']['Subject'] = title

        if not self.is_open_or_crt:
            raise errors.ExperimentNotOpenError

        assert self.SAV_PATH is not None

        introduce_Experiment(introduction)
        name_Experiment(title)

        return self

    def edit_tags(self, *tags: Tag) -> Self:
        if not all(isinstance(tag, Tag) for tag in tags):
            raise TypeError

        temp = self.PlSav["Summary"]["Tags"] + [tag.value for tag in tags]
        self.PlSav["Summary"]["Tags"] = list(set(temp))

        return self

    def __upload(self,
            user: User,
            category: Optional[Category],
            image_path: Optional[str],
            warning_status: Optional[bool],
            ):
        if image_path is not None and not isinstance(image_path, str) or \
            category is not None and not isinstance(category, Category) or \
            not isinstance(user, User):
            raise TypeError
        if image_path is not None and (not os.path.exists(image_path) or not os.path.isfile(image_path)):
            raise FileNotFoundError
        if user.is_anonymous:
            raise PermissionError("you must register first")

        self.__write()
        workspace = copy.deepcopy(self.PlSav)
        workspace["Summary"] = None
        _summary = self.PlSav["Summary"]

        if _summary["Language"] is None:
            _summary["Language"] = "Chinese"
        _summary["User"]["ID"] = user.user_id
        _summary["User"]["Nickname"] = user.nickname
        _summary["User"]["Signature"] = user.signature
        _summary["User"]["Avatar"] = user.avatar
        _summary["User"]["AvatarRegion"] = user.avatar_region
        _summary["User"]["Decoration"] = user.decoration
        _summary["User"]["Verification"] = user.verification

        if category is not None:
            _summary["Category"] = category.value

        plar_ver = plAR.get_plAR_version()
        if plar_ver is not None:
            plar_ver = int(plar_ver.replace(".", ""))
        else:
            plar_ver = 2411
        _summary["Version"] = plar_ver

        # 请求更新实验
        submit_data = {
            "Summary": _summary,
            "Workspace": workspace,
        }

        if image_path is not None:
            image_size = os.path.getsize(image_path)
            if image_size >= 1048576:
                errors.warning("image size is bigger than 1MB", warning_status)
                image_size = -image_size # 利用物实bug发布大图片
            submit_data["Request"] = {
                "FileSize": image_size,
                'Extension': ".jpg",
            }

        submit_response = requests.post(
            "https://physics-api-cn.turtlesim.com/Contents/SubmitExperiment",
            data=gzip.compress(json.dumps(submit_data).encode("utf-8")),
            headers={
                "x-API-Token": user.token,
                "x-API-AuthCode": user.auth_code,
                "x-API-Version": str(plar_ver),
                "Accept-Encoding": "gzip",
                "Content-Type": "gzipped/json",
            }
        )
        def callback(status_code):
            if status_code == 403:
                _colorUtils.color_print(
                    "you can't submit experiment because you are not the author "
                    "or experiment status(elements, tags...) is invalid",
                    _colorUtils.COLOR.RED,
                )
        _check_response(submit_response, callback)

        return submit_response.json(), submit_data

    def upload(self,
                user: User,
                category: Category,
                image_path: Optional[str] = None,
                warning_status: Optional[bool] = None,
                ) -> Self:
        ''' 发布新实验
            @user: 不允许匿名登录
            @param category: 实验区还是黑洞区
            @param image_path: 图片路径
        '''
        if not isinstance(category, Category) or \
            image_path is not None and not isinstance(image_path, str):
            raise TypeError
        if self.PlSav["Summary"]["ID"] is not None:
            raise Exception(
                "upload can only be used to upload a brand new experiment, try using update instead"
            )

        submit_response, submit_data = self.__upload(user, category, image_path, warning_status)

        submit_data["Summary"]["Image"] += 1
        user.confirm_experiment(
            submit_response["Data"]["Summary"]["ID"], {
                Category.Experiment.value: Category.Experiment,
                Category.Discussion.value: Category.Discussion,
            }[category.value], submit_data["Summary"]["Image"]
        )

        if image_path is not None:
            user.upload_image(submit_response["Data"]["Token"]["Policy"],
                            submit_response["Data"]["Token"]["Authorization"],
                            image_path)

        return self

    def update(self,
               user: User,
               image_path: Optional[str] = None,
               warning_status: Optional[bool] = None,
               ) -> Self:
        ''' 更新实验到物实
            @user: 不允许匿名登录
            @param image_path: 图片路径
        '''
        if self.PlSav["Summary"]["ID"] is None:
            raise Exception(
                "update can only be used to upload an exist experiment, try using upload instead"
            )

        submit_response, submit_data = self.__upload(user, None, image_path, warning_status)

        submit_data["Summary"]["Image"] += 1
        response = requests.post(
            "https://physics-api-cn.turtlesim.com/Contents/SubmitExperiment",
            data=gzip.compress(json.dumps(submit_data).encode("utf-8")),
            headers={
                "x-API-Token": user.token,
                "x-API-AuthCode": user.auth_code,
                "x-API-Version": str(submit_data["Summary"]["Version"]),
                "Accept-Encoding": "gzip",
                "Content-Type": "gzipped/json",
            }
        )
        _check_response(response)

        if image_path is not None:
            user.upload_image(submit_response["Data"]["Token"]["Policy"],
                            submit_response["Data"]["Token"]["Authorization"],
                            image_path)

        return self

    def observe(self,
                x: Optional[numType] = None,
                y: Optional[numType] = None,
                z: Optional[numType] = None,
                distance: Optional[numType] = None,
                rotation_x: Optional[numType] = None,
                rotation_y: Optional[numType] = None,
                rotation_z: Optional[numType] = None
    ) -> Self:
        ''' 设置实验者的视角
            x, y, z : 实验者观察的坐标
            distance: 实验者到(x, y, z)的距离
            rotation: 实验者观察的角度
        '''
        if not self.is_open_or_crt:
            raise errors.ExperimentNotOpenError

        if x is None:
            x = self.VisionCenter.x
        if y is None:
            y = self.VisionCenter.y
        if z is None:
            z = self.VisionCenter.z
        if distance is None:
            distance = self.CameraSave["Distance"]
        if rotation_x is None:
            rotation_x = self.TargetRotation.x
        if rotation_y is None:
            rotation_y = self.TargetRotation.y
        if rotation_z is None:
            rotation_z = self.TargetRotation.z

        if not isinstance(x, (int, float)):
            raise TypeError
        if not isinstance(y, (int, float)):
            raise TypeError
        if not isinstance(z, (int, float)):
            raise TypeError
        if not isinstance(distance, (int, float)):
            raise TypeError
        if not isinstance(rotation_x, (int, float)):
            raise TypeError
        if not isinstance(rotation_y, (int, float)):
            raise TypeError
        if not isinstance(rotation_z, (int, float)):
            raise TypeError

        self.VisionCenter = _tools.position(x, y, z)
        self.CameraSave["Distance"] = distance
        self.TargetRotation = _tools.position(rotation_x, rotation_y, rotation_z)

        return self

    def paused(self, status: bool = True) -> Self:
        ''' 暂停或解除暂停实验 '''
        if not self.is_open_or_crt:
            raise errors.ExperimentNotOpenError
        if not isinstance(status, bool):
            raise TypeError

        self.PlSav["Paused"] = status
        self.PlSav["Experiment"]["Paused"] = status

        return self

    def graph(self) -> Optional[list]: # List[chart.Plot]
        ''' 获取物实示波器图表的封装类 '''
        from physicsLab import chart
        if not self.is_open_or_crt:
            raise errors.ExperimentNotOpenError

        if self.PlSav["Plots"] is None:
            return None

        res = [chart.Plot(a_graph) for a_graph in self.PlSav["Plots"]]
        return res

    def export(self, output_path: str = "temp.pl.py", sav_name: str = "temp") -> Self:
        ''' 以physicsLab代码的形式导出实验 '''
        if not self.is_open_or_crt:
            raise errors.ExperimentNotOpenError

        res: str = f"from physicsLab import *\nexp = Experiment('{sav_name}')\n"

        for a_element in self.Elements:
            res += f"e{a_element.get_Index()} = {str(a_element)}\n"
        for a_wire in self.Wires:
            res += str(a_wire) + '\n'
        res += "\nexp.write()"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(res)

        return self

    def merge(self,
              other: "Experiment",
              x: numType = 0,
              y: numType = 0,
              z: numType = 0,
              elementXYZ: Optional[bool] = None
    ) -> Self:
        ''' 合并另一实验
            x, y, z, elementXYZ为重新设置要合并的实验的坐标系原点在self的坐标系的位置
            不是电学实验时, elementXYZ参数无效
        '''
        if not isinstance(other, Experiment) or \
                not isinstance(x, (int, float)) or \
                not isinstance(y, (int, float)) or \
                not isinstance(z, (int, float)) or \
                not isinstance(elementXYZ, (bool, type(bool))):
            raise TypeError
        if not self.is_open_or_crt or not other.is_open_or_crt:
            raise errors.ExperimentNotOpenError
        if self.experiment_type != other.experiment_type:
            raise errors.ExperimentTypeError

        assert self.SAV_PATH is not None and other.SAV_PATH is not None

        if self is other:
            return self

        identifier_to_element: dict = {}

        for a_element in other.Elements:
            a_element = copy.deepcopy(a_element, memo={id(a_element.experiment): self})
            e_x, e_y, e_z = a_element.get_position()
            if self.experiment_type == ExperimentType.Circuit:
                from .circuit.elementXYZ import xyzTranslate, translateXYZ
                if elementXYZ and not a_element.is_elementXYZ:
                    e_x, e_y, e_z = translateXYZ(e_x, e_y, e_z, a_element.is_bigElement)
                elif not elementXYZ and a_element.is_elementXYZ:
                    e_x, e_y, e_z = xyzTranslate(e_x, e_y, e_z, a_element.is_bigElement)
            a_element.set_position(e_x + x, e_y + y, e_z + z, elementXYZ)
            # set_Position已处理与elements_Position有关的操作
            self.Elements.append(a_element)

            identifier_to_element[a_element.data["Identifier"]] = a_element

        if self.experiment_type == ExperimentType.Circuit and other.experiment_type == ExperimentType.Circuit:
            for a_wire in other.Wires:
                a_wire = copy.deepcopy(
                    a_wire, memo={
                        id(a_wire.Source.element_self):
                            identifier_to_element[a_wire.Source.element_self.data["Identifier"]],
                        id(a_wire.Target.element_self):
                            identifier_to_element[a_wire.Target.element_self.data["Identifier"]],
                })
                self.Wires.add(a_wire)

        return self

class experiment:
    ''' 仅提供通过with操作存档的高层次api '''
    def __init__(self,
                 sav_name: str, # 实验名(非存档文件名)
                 read: bool = False, # 是否读取存档原有状态
                 delete: bool = False, # 是否删除实验
                 write: bool = True, # 是否写入实验
                 elementXYZ: bool = False, # 元件坐标系
                 experiment_type: ExperimentType = ExperimentType.Circuit, # 若创建实验，支持传入指定实验类型
                 extra_filepath: Optional[str] = None, # 将存档写入额外的路径
                 force_crt: bool = False, # 强制创建一个实验, 若已存在则覆盖已有实验
                 is_exit: bool = False, # 退出试验
                 ):
        if not (
            isinstance(sav_name, str) and
            isinstance(read, bool) and
            isinstance(delete, bool) and
            isinstance(elementXYZ, bool) and
            isinstance(write, bool) and
            isinstance(experiment_type, ExperimentType) and
            isinstance(force_crt, bool) and
            isinstance(is_exit, bool) and
            isinstance(extra_filepath, (str, type(None)))
        ):
            raise TypeError

        self.savName: str = sav_name
        self.read: bool = read
        self.delete: bool = delete
        self.write: bool = write
        self.elementXYZ: bool = elementXYZ
        self.ExperimentType: ExperimentType = experiment_type
        self.extra_filepath: Optional[str] = extra_filepath
        self.force_crt: bool = force_crt
        self.is_exit: bool = is_exit

    def __enter__(self) -> Experiment:
        if not self.force_crt:
            self._Experiment: Experiment = Experiment() \
                .open_or_crt(self.savName, self.ExperimentType)
        else:
            self._Experiment: Experiment = Experiment().crt(self.savName, self.ExperimentType, self.force_crt)

        if self.read:
            self._Experiment.read()
        if self.elementXYZ:
            if self._Experiment.experiment_type != ExperimentType.Circuit:
                stack_Experiment.pop()
                raise errors.ExperimentTypeError
            import physicsLab.circuit.elementXYZ as _elementXYZ
            _elementXYZ.set_elementXYZ(True)

        return self._Experiment

    def __exit__(self, exc_type, exc_val, traceback) -> None:
        if exc_type is not None:
            self._Experiment.exit()
            return

        if self.is_exit:
            self._Experiment.exit()
            return
        if self.write and not self.delete:
            self._Experiment.write(extra_filepath=self.extra_filepath)
        if self.delete:
            self._Experiment.delete()
            return

def getAllSav() -> List[str]:
    ''' 获取所有物实存档的文件名 '''
    from os import walk
    savs = [i for i in walk(Experiment.SAV_ROOT_DIR)][0]
    savs = savs[savs.__len__() - 1]
    return [aSav for aSav in savs if aSav.endswith('sav')]

def _open_sav(sav_path) -> Optional[dict]:
    ''' 打开一个存档, 返回存档对应的dict
        @param sav_path: 存档的绝对路径
    '''
    def encode_sav(path: str, encoding: str) -> Optional[dict]:
        try:
            with open(path, encoding=encoding) as f:
                d = json.loads(f.read().replace('\n', ''))
        except (json.decoder.JSONDecodeError, UnicodeDecodeError): # 文件不是物实存档
            return None
        else:
            return d

    assert os.path.exists(sav_path)

    res = encode_sav(sav_path, "utf-8")
    if res is not None:
        return res

    try:
        import chardet
    except ImportError:
        for encoding in ("utf-8-sig", "gbk"):
            res = encode_sav(sav_path, encoding)
            if res is not None:
                return res
    else:
        with open(sav_path, "rb") as f:
            encoding = chardet.detect(f.read())["encoding"]
        return encode_sav(sav_path, encoding)

def search_Experiment(sav_name: str) -> Optional[str]:
    ''' 检测实验是否存在
        @param sav_name: 存档名

        若存在则返回存档对应的文件名, 若不存在则返回None
    '''
    for aSav in getAllSav():
        sav = _open_sav(os.path.join(Experiment.SAV_ROOT_DIR, aSav))
        if sav is None:
            continue
        if sav["InternalName"] == sav_name:
            search_Experiment.sav = sav
            return aSav

    return None
