#!/bin/bash
# 停止液位检测系统服务

echo " 停止API服务...\
pkill -f 'liquid-api' && echo \API服务已停止\ || echo \API服务未运行\

echo \停止推理服务...\
pkill -f 'python.*8085' && echo \推理服务已停止\ || echo \推理服务未运行\

echo \所有服务已停止\
