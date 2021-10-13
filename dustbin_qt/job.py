"""
流程类：
    read_id_list: 读取excel表格中的ID，生成user列表和admin列表 
    init_hardware：读取配置列表
    entranceThread：门禁线程，循环读取串口上的ID，判断是否与user/admin中的一致
    userThread：用户倒垃圾的工作线程
    adminThread：管理员处理线程
"""

from PyQt5.QtCore import QThread, pyqtSignal
import time
from device import adc, motor, switch, output_switch, timer, mqtt_device
import os
import yaml
import xlrd
import serial
import modbus_tk
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu
import sys
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler

def read_id_list(): # 读取用户名单
    fileNamePath = os.path.split(os.path.realpath(__file__))[0]    ### 获取当前执行脚本的绝对路径，取当前路径的前部分（即除去改文件部分）
    xlPath = os.path.join(fileNamePath,'./user_list.xlsx')         ### 拼接成Excel表的绝对路径
    data = xlrd.open_workbook(xlPath)                              ### 打开Excel文件
    table = data.sheet_by_name('Sheet1')                           ### 按sheet名称获取sheet内容
    user = []
    admin = []
    for i in range (0,table.ncols):                                ### ncols列 nrows行 cell(x,y)单元格
        if table.cell(0,i).value=="ID":
            id_col = i
        elif table.cell(0,i).value=="GROUP":
            group_col = i
    for i in range (1, table.nrows):
        if table.cell(i, group_col).value.lower() == "user":       ### lower() 所有大写转化为小写
            user.append(table.cell(i,id_col).value)
        elif table.cell(i, group_col).value.lower() == "admin":
            admin.append(table.cell(i,id_col).value)
    return user,admin

def init_hardware(bin_type): # 读取设备配置
    fileNamePath = os.path.split(os.path.realpath(__file__))[0]
    fileName = "./config/config_type_" + bin_type + ".yaml"
    print("config fileName : {}".format(fileName))                 ### filename代替{}
    yamlPath = os.path.join(fileNamePath, fileName)
    with open(yamlPath,'r',encoding='utf-8') as f:
        result = f.read()
        config = yaml.load(result,Loader=yaml.FullLoader)          ### yaml 数据序列化标准，以对齐表示同级，缩进为下一级
        print(config)                                              ### 加上Loader=yaml.FullLoader 因为python认为直接使用yaml.load()不安全
    return config

class entranceThread(QThread):
    log = pyqtSignal(str) # 日志                                   ###定义了一个日志信号
    start_user = pyqtSignal(bool) # 开始用户工作流程
    start_admin = pyqtSignal(bool) # 开始管理员工作流程
    stop_user = pyqtSignal(bool)
    def __init__(self, ser, user, admin):
        super(entranceThread, self).__init__()
        self.ser = None
        self.ser = ser        ###?????????????????????????????????
        self.run_flag = False
        self.admin = admin
        self.user = user
        self.working_state = -1 # 状态码 0 表示正常工作， 1 表示 压缩故障暂停使用， 2表示箱体已满， -1 表示没有工作, 
                                        #3表示userThread接受entranceThread控制提前终止

    def threadStop(self):
        self.run_flag = False

    def run(self):
        print("Start Reading Entrance")
        self.run_flag = True
        while self.run_flag:
            time.sleep(0.1) # 防止CPU占用过高
            try:
                if self.ser.in_waiting:
                    read_str=self.ser.read(self.ser.in_waiting)
                    # read_str=self.ser.read(self.ser.in_waiting ).hex()
                    self.log.emit(str("[Read ] {}".format(read_str))) #
                    input_id = str(read_str,'utf-8').split("'")[0]
                    self.log.emit(str("[Door ] get input id =  {}".format(input_id))) #
                else:
                    # self.log.emit(str("[ENTER] Don`t scan twice {}".format(input_id))) # 
                    print("Dont scan twice")
            except Exception as e:
                print(str(e))
        print("Thread died")

# class adminThread(QThread):
#     log = pyqtSignal(str) # 日志
#     end = pyqtSignal(bool)
#     def __init__(self, master, bin_type):
#         super(userThread, self).__init__()


class userThread(QThread):
    log = pyqtSignal(str) # 日志
    end = pyqtSignal(int)
    def __init__(self, master, bin_type):
        super(userThread, self).__init__()
        self.master = master
        self.type = str(bin_type)
        self.init_hardware()
        self.init_timer()
        self.run_flag = True
        # self.reset_timer()

    def reset_timer(self):
        self.timer_2.reset()
        self.timer_5.reset()
        self.timer_7.reset()

    def init_timer(self):
        self.timer_2 = timer(120, self.timer_cnt, 2) # 开始投递
        self.timer_5 = timer(120, self.timer_cnt, 3) # 关门失败
        self.timer_7 = timer(120, self.timer_cnt, 4) # 开始压缩

    def init_hardware(self):
        config = init_hardware(self.type) # 初始化要根据垃圾桶类型选择  
        if self.type == "1": # 干垃圾
            # d01-d03 3个电机
            for i in range (1,4):
                exec("print(tuple(config['digital_device']['output']['d0{}']))".format(i))
                exec("self.motor_{0} = motor(config['digital_device']['addr'],tuple(config['digital_device']['output']['d0{0}']), self.master)".format(i))
                print("motor_{} init".format(i))
            # 为方便起见，直接构造output_switch_4和10，分别对应d04和d10
            self.output_switch_4 = output_switch(config['digital_device']['addr'],config['digital_device']['output']['d04'], self.master)
            self.output_switch_10 = output_switch(config['digital_device']['addr'],config['digital_device']['output']['d10'], self.master)
            # td01 - 12
            for i in range (1,13):
                exec("self.switch_{0} = switch(config['digital_device']['addr'],config['digital_device']['input']['td0{0}'], self.master)".format(i))
            self.adc = adc(config['analog_device']['addr'],config['analog_device']['input']['force'],self.master)
        elif self.type == "2": # 湿垃圾
            # 2个电机
            for i in range (1,3):
                exec("print(tuple(config['digital_device']['output']['d0{}']))".format(i))
                exec("self.motor_{0} = motor(config['digital_device']['addr'],tuple(config['digital_device']['output']['d0{0}']), self.master)".format(i))
                print("motor_{} init".format(i))
            # d04,d08,d09
            self.output_switch_4 = output_switch(config['digital_device']['addr'],config['digital_device']['output']['d04'], self.master)
            self.output_switch_8 = output_switch(config['digital_device']['addr'],config['digital_device']['output']['d08'], self.master)
            self.output_switch_9 = output_switch(config['digital_device']['addr'],config['digital_device']['output']['d09'], self.master)
            # td01 -07
            for i in range (1,8):
                exec("self.switch_{0} = switch(config['digital_device']['addr'],config['digital_device']['input']['td0{0}'], self.master)".format(i))
            self.adc = adc(config['analog_device']['addr'],config['analog_device']['input']['force'],self.master)

    def test_1(self): # 干垃圾测试
        for i in range (1,4): 
            time.sleep(0.5)
            exec("self.motor_{}.forward()".format(i))
            time.sleep(1.5)
            exec("self.motor_{}.reverse()".format(i))
            time.sleep(1.5)
            exec("self.motor_{}.stop()".format(i))
        output_switch_list = [4,10]
        for i in output_switch_list:
            time.sleep(0.5)
            exec("self.output_switch_{0}.set_state(1)".format(i))
            time.sleep(1.0)
            exec("self.output_switch_{0}.set_state(0)".format(i))
            time.sleep(1.0)
            exec("self.output_switch_{0}.set_state(1)".format(i))
        for i in range(1,13):
            exec("print(self.switch_{0}.check_on())".format(i))
        print(self.adc.get_value())

    def test_2(self):
        for i in range (1,3): 
            time.sleep(0.5)
            exec("self.motor_{}.forward()".format(i))
            time.sleep(1.5)
            exec("self.motor_{}.stop()".format(i))
            time.sleep(1.5)
            exec("self.motor_{}.reverse()".format(i))
        output_switch_list = [4,8,9]
        for i in output_switch_list:
            time.sleep(0.5)
            exec("self.output_switch_{0}.set_state(1)".format(i))
            time.sleep(1.0)
            exec("self.output_switch_{0}.set_state(0)".format(i))
            time.sleep(1.0)
            exec("self.output_switch_{0}.set_state(1)".format(i))
        for i in range(1,8):
            exec("print(self.switch_{0}.check_on())".format(i))
        print(self.adc.get_value())

    def run(self):
        if self.type == "1":
            self.test_1()
        elif self.type =="2":
            self.test_2()
        print("test user thread died type {0}".format(self.type))

def test_entrance():
    print("Start test entrance")
    config = init_hardware('1') # 测试配置读取
    user,admin  = read_id_list()
    try:
        ser=serial.Serial(port="/dev/ttyS1",baudrate=9600,bytesize=8,parity='N',stopbits=1)
    except Exception as e:
        print("Test failed, check modbus device and serial comm")
        sys.exit()
    print("Start test entrance thread")
    thread_1 = entranceThread(ser, user, admin)
    thread_1.start()
    cnt = 0
    while cnt<1:
        cnt+=1
        time.sleep(10.0)
        print("Release scanner")
        thread_1.release_user() # 释放门禁
    ser.flush()
    if ser.isOpen():
        thread_1.threadStop()
        thread_1.quit()
        while not thread_1.wait(): # run结束后通过wait判断线程是否成功退出
            time.sleep(0.1)
        ser.close()
        print("Serial and thread quit safely")

def test_user():
    print("Start test user thread")
    # config = init_hardware() # 测试配置读取
    # user,admin  = read_id_list()
    try:
        ser=serial.Serial(port="/dev/ttyS1",baudrate=9600,bytesize=8,parity='N',stopbits=1)
    except Exception as e:
        print("Test failed, check modbus device and serial comm")
        sys.exit()
    master = modbus_rtu.RtuMaster(ser)
    master.set_timeout(5.0) # 需要设置，否则可能没有返回值
    thread_2 = userThread(master,1)
    thread_2.start()
    print("Start test type1 dustbin")
    while not thread_2.wait():
        time.sleep(1.0)
    thread_2 = userThread(master,2)
    thread_2.start()
    print("Start test type2 dustbin")
    while not thread_2.wait():
        time.sleep(1.0)


if __name__ == "__main__":
    # config = init_hardware('1') # 测试配置读取
    user,admin  = read_id_list() # 测试user/admin名单
    # test_entrance() # 测试门禁线程
    test_user() # 测试用户线程
    
