# coding=utf-8

import os
from ctypes import *

# 支持相对导入和绝对导入
try:
    from .HCNetSDK import sys_platform, system_type, C_DWORD, get_hk_lib_path
except ImportError:
    from HCNetSDK import sys_platform, system_type, C_DWORD, get_hk_lib_path

if sys_platform == 'linux':
    load_library = cdll.LoadLibrary
    fun_ctype = CFUNCTYPE
elif sys_platform == 'windows':
    load_library = windll.LoadLibrary
    fun_ctype = WINFUNCTYPE
else:
    print("************不支持的平台**************")
    exit(0)

hk_lib_dir = get_hk_lib_path()
playM4dllpath_dict = {'windows64': os.path.join(hk_lib_dir, 'PlayCtrl.dll'),
                      'windows32': os.path.join(hk_lib_dir, 'PlayCtrl.dll'),
                      'linux64': os.path.join(hk_lib_dir, 'libPlayCtrl.so'),
                      'linux32': os.path.join(hk_lib_dir, 'libPlayCtrl.so')}
playM4dllpath = playM4dllpath_dict[system_type]


# 定义预览参数结构体
class FRAME_INFO(Structure):
    _fields_ = [
        ('nWidth', c_uint32),
        ('nHeight', c_uint32),
        ('nStamp', c_uint32),
        ('nType', c_uint32),
        ('nFrameRate', c_uint32),
        ('dwFrameNum', c_uint32)
    ]


LPFRAME_INFO = POINTER(FRAME_INFO)

# 显示回调函数
DISPLAYCBFUN = fun_ctype(None, c_long, c_char_p, c_long, c_long, c_long, c_long, c_long, c_long)
# 解码回调函数
DECCBFUNWIN = fun_ctype(None, c_long, POINTER(c_char), c_long, POINTER(FRAME_INFO), c_long, c_long)
