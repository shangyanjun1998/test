
"""
主界面调试类： 完成程序主体逻辑
"""

import os
import sys
import time

import modbus_tk
import modbus_tk.defines as cst
import serial
import yaml
from modbus_tk import modbus_rtu
from PyQt5 import QtCore, QtWidgets
from PyQt5.Qt import QLCDNumber
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication

import job
from device import adc, motor, switch
# from job import entranceThread, workThread
from job import init_hardware, read_id_list              ###使用时直接用job.read_id_list是不是易于理解？
from panel import Ui_MainWindow


class entranceThread(job.entranceThread): # 重载
    def run(self):      ###将job里面的run()方法重写
        self.run_flag = True
        while self.run_flag:
            time.sleep(0.1) # 已解决CPU占用过高
            try:
                if self.ser.in_waiting:     #判断当前是否接收数据
                    read_str=self.ser.read(self.ser.in_waiting)
                    # read_str=self.ser.read(self.ser.in_waiting ).hex()
                    input_id = str(read_str,'utf-8').split("'")[0]
                    print("Working state = {0}".format(self.working_state))
                    if self.working_state == -1: # 如果工作线程没有在工作
                        if input_id in self.user:
                            self.log.emit(str("[Door] Valid user {}".format(input_id))) #
                            self.start_user.emit(bool(True)) # 
                            self.working_state = 0
                        elif input_id in self.admin:
                            self.log.emit(str("[Door] Valid admin {}".format(input_id))) # 
                            self.start_admin.emit(bool(True)) # 
                            self.working_state = 0
                        else :
                            self.log.emit(str("[Door] Invalid user {}".format(input_id))) #
                    elif self.working_state == 0: # 如果工作线程正在工作
                        self.log.emit(str("[Door] Don`t scan twice {}".format(input_id))) # 
                    elif self.working_state == 1 or self.working_state == 2:  # 如果系统处在故障状态正在工作
                        if input_id in self.admin:
                            self.log.emit(str("[Door]Working state = 1/2, Valid admin {}".format(input_id))) # 
                            self.start_admin.emit(bool(True)) # 
                            self.working_state = 0
                        else :
                            self.log.emit(str("[Door]Working state = 1, Invalid admin {}".format(input_id))) #
                    elif self.working_state == 3:
                        if input_id in self.user or input_id in self.admin:
                            self.log.emit(str("[Door] Stop user thread with Valid user {}".format(input_id))) #
                            self.stop_user.emit(bool(True)) # 
                            time.sleep(1.0)
                            self.start_user.emit(bool(True)) # 
                            self.working_state = 0
                    else :
                        self.log.emit(str("[Door] Thread working state error {}".format(input_id))) #
            except Exception as e:
                print(str(e))

class userThread(job.userThread): # 重载
    timer_cnt = pyqtSignal((int,int))
    weight_cnt = pyqtSignal(float)

    for i in range (1,9):
        exec("sig_{0} = pyqtSignal(bool)".format(i))

    def run(self):
        self.reset_timer()
        ret = self.process_1()
        # self.testTimer()
        if ret == 0:
            self.end.emit(0) # 1.jpg 正常界面
            print("Return - 0")
        elif ret == 1:
            self.end.emit(1) # 8.jpg 暂停使用
            print("Return - 1")
        elif ret == 2:
            self.end.emit(2) # 6.jpg 箱体已满
            print("Return - 2")
        elif ret == 3: 
            print("Return - 3")
            self.end.emit(3) # 3.jpg 持续120s，结束后回到初始界面，或通过刷卡重新开始
            cnt = 0
            while cnt < 120:
                if self.run_flag == False:
                    self.run_flag = True
                    break
                cnt+=1
                time.sleep(1.0)
            self.end.emit(0) # 120s倒计时结束则和正常结束一样处理
        else:
            while True:
                print("Job ending Error")
                time.sleep(1.0)
        self.reset_timer()

    def process_1(self):
        self.sig_1.emit(True)
        thresh = 1900 # 加压阈值， 0kg --- 4mA --- 800; 20kg --- 20mA --- 4000
        if self.switch_1.check_on() and self.switch_2.check_on():
            weight_start = self.adc.get_value() # 垃圾桶起始总重
            weight = 0 # 本次重量读数
            self.timer_2.start() # 构造一个120s的显示定时器
            self.sig_2.emit(True)
            self.motor_3.forward() # 显示 "箱门已开启，请规范投递， 2.jpg"
            self.output_switch_10.set_state(1) # 开灯
            print("motor3 forward / output switch 10 set (1)")
            cnt = 0
            while cnt<=5: # 5
                if self.switch_8.check_on()==1:
                    break
                time.sleep(1)
                cnt+=1
            if self.switch_8.check_on() == 0:
                self.motor_3.stop()
                self.sig_3.emit(True) # 显示 "开门失败， 清理障碍物， 再刷卡开门， 3.jpg"
                return 3 # 120s结束后回到初始界面，或通过刷卡重新开始
            else:
                self.motor_3.stop()
                while self.timer_2.isActive:
                    if self.switch_10.check_on() == 1: # 触发则读本次投递垃圾重量
                        weight = self.adc.get_value() - weight_start
                        self.weight_cnt.emit(weight)
                    if self.switch_1.check_on() == 0 and self.switch_2.check_on() == 0:
                        break
                    time.sleep(1)
                self.sig_4.emit(True) # 倒完垃圾后， 显示 "箱门即将关闭，请勿将手放在门口, 4.jpg"
                self.timer_2.pause() # 更换界面后 计时器可以停止工作
                # TODO：上传投递信息，发出信号，由主线程进行

                while self.switch_9.check_on() == 0: # 如果td09始终没有触发
                    self.motor_3.reverse()
                    self.output_switch_10.set_state(0)
                    cnt = 0
                    while cnt <=5: # 5 
                        if self.switch_9.check_on() == 1: # 
                            break
                        time.sleep(1.0)
                        cnt+=1
                    self.motor_3.stop()
                    self.sig_5.emit(True)
                    self.timer_5.start() # 显示 "关门失败，请先清理障碍物" 5.jpg
                    while self.timer_5.isActive:
                        if self.switch_9.check_on() == 1: # 需要添加防抖
                            break
                        time.sleep(1.0)
                    if self.switch_9.check_on() == 1:
                        break
                self.motor_3.stop()

                if self.switch_5.check_on() == 0 and \
                    self.switch_6.check_on() == 0 and self.switch_7.check_on() == 0:
                    print("Successful Loop")
                    return 0 
                elif self.switch_5.check_on() == 1 or \
                    self.switch_6.check_on() == 1 or self.switch_7.check_on() == 1:
                    # self.motor_2.forward()
                    # self.sig_7.emit(True)
                    # self.timer_7.start() # 显示 "仓内正在压缩，请稍等片刻" 7.jpg
                    # self.timer_5.pause() # 更换界面后 计时器可以停止工作
                    # cnt = 0
                    # while cnt<20:
                    #     if self.switch_11.check_on() == 1: # 防抖
                    #         break
                    #     time.sleep(1.0)
                    #     cnt+=1

                    # if self.switch_11.check_on() == 0:
                    #     self.motor_2.stop()
                    #     self.sig_8.emit(True) # 20秒内td1未触发，显示"暂停使用" 暂停服务，TODO:上传压缩故障信息
                    #     return 1 # 持续显示暂停使用，不再释放

                    # self.motor_2.stop()
                    time.sleep(30)
                    self.motor_1.forward()
                    
                    while self.adc.get_value() - (weight_start + weight) < thresh: # 判断压力
                        if self.switch_3.check_on() == 1:
                            break
                        time.sleep(1)
                    
                    self.motor_1.stop() # D01停止5秒
                    cnt = 0
                    while cnt<=5: # 5
                        time.sleep(1.0) #
                        cnt+=1

                    self.motor_1.reverse() # D01反转
                    print("D01 reverse 20s")
                    cnt = 0
                    while cnt<=20:
                        if self.switch_4.check_on() == 1:
                            self.motor_1.stop()
                            break
                        time.sleep(1.0)
                        cnt+=1

                    if self.switch_4.check_on() == 0:
                        self.motor_1.stop()
                        self.sig_8.emit(True) # 20秒内td04未触发，显示"暂停使用" 暂停服务，TODO:上传压缩故障信息
                        self.timer_7.pause() # 更换界面后 计时器可以停止工作
                        return 1 # 持续显示暂停使用，不再释放

                    print("D02 reverse 20s")
                    self.motor_2.reverse()
                    cnt = 0
                    while cnt<=20:
                        if self.switch_12.check_on() == 1:
                            self.motor_2.stop()
                            break
                        time.sleep(1.0)
                        cnt+=1

                    if self.switch_12.check_on() == 0:
                        self.motor_2.stop()
                        self.sig_8.emit(True) # 20秒内td12未触发，显示"暂停使用" 暂停服务，TODO:上传压缩故障信息
                        return 1 # 持续显示暂停使用，不再释放

                    if self.switch_5.check_on() == 0 and \
                        self.switch_6.check_on() == 0 and self.switch_7.check_on() == 0:
                        print("Successful Loop")
                        return 0 
                    elif self.switch_5.check_on() == 1 or \
                        self.switch_6.check_on() == 1 or self.switch_7.check_on() == 1:
                        self.sig_6.emit(True) # 显示"箱体已满" 暂停服务，TODO:上传垃圾箱满信息
                        return 2 # 持续显示箱体已满，不再释放
        return 0

class MyWindow(QtWidgets.QMainWindow,Ui_MainWindow):
    def __init__(self):
        # set UI
        super(MyWindow,self).__init__() # 菱形继承（多父类如果继承了同一个方法，只会被调用一次）
        self.setupUi(self)                                                  ### 直接继承界面类，调用类的setupUi方法
        self.stackedWidget.setCurrentIndex(0)                               ### 栈窗口的序号，初始为0
        # self.gui_tab.setWindowFlags (Qt.Window|Qt.FramelessWindowHint)
        # self.gui_tab.showFullScreen()

        self.serial_flag = False
        self.user,self.admin  = read_id_list()                              ### 前面已经导入了job.read_id_list方法

        for i in range (1,21):
            exec('self.serial_port.addItem("/dev/ttyS{0}")'.format(i))
        for i in range (1,21):
            exec('self.modbus_port.addItem("/dev/ttyS{0}")'.format(i))


    def read_param(self):
        self.serial_port = self.serial_port.currentText()
        self.modbus_port = self.modbus_port.currentText()
        self.baud_rate = self.baud_rate.currentText()
        self.data_bit = int(self.data_bit.currentText())
        self.parity = self.parity.currentText()
        self.stop_bit = int(self.stop_bit.currentText())

    def serial_connect(self):
        # self.frame.setStyleSheet("border-image: url(:/layer/source/2.jpg);")
        if not self.serial_flag:
            self.read_param()
            try:
                # modbus串口
                self.mod=serial.Serial(port=self.modbus_port,baudrate=self.baud_rate,bytesize=self.data_bit,parity=self.parity,stopbits=self.stop_bit)
                self.master = modbus_rtu.RtuMaster(self.mod)
                self.master.set_timeout(0.5)
                self.userThread = userThread(self.master, 1)
                self.userThread.log.connect(self._log_append)
                self.userThread.end.connect(self._release_enter)
                self.userThread.timer_cnt.connect(self._show_timer)
                self.userThread.weight_cnt.connect(self._show_weight)
                for i in range (1,9):
                    exec("self.userThread.sig_{0}.connect(self._show_{0})".format(i))
                # 门禁串口
                self.ser=serial.Serial(port=self.serial_port,baudrate=self.baud_rate,bytesize=self.data_bit,parity=self.parity,stopbits=self.stop_bit)
                if self.ser.isOpen():
                    self.serial_message.append("[State] Seral connected")
                    self.serial_flag = True
                    self.entranceThread = entranceThread(self.ser, self.user, self.admin)
                    self.entranceThread.log.connect(self._log_append)
                    self.entranceThread.start_user.connect(self._user_thread)
                    self.entranceThread.start_admin.connect(self._admin_thread)
                    self.entranceThread.stop_user.connect(self._stop_user_thread)
                    self.entranceThread.start()
            except Exception as e:
                self.serial_message.append("Open device failed, make sure you open the device")
        else:
            self.serial_message.append("[State] Serial already connected")

    def serial_disconnect(self):
        pass

    def _user_thread(self, flag):
        # self.frame.setStyleSheet("border-image: url(:/layer/source/2.jpg);") # 修改背景
        self.userThread.start()

    def _admin_thread(self, flag):
        pass
    
    def _log_append(self, text):
        self.serial_message.append(text)

    def _stop_user_thread(self, flag):
        self.userThread.run_flag = False

    def _release_enter(self, mode):
        if mode == 0 :
            self.stackedWidget.setCurrentIndex(0) # 正常界面
            self.entranceThread.working_state = -1
        elif mode == 1 :
            self.stackedWidget.setCurrentIndex(7) # 8.jpg 压缩故障，暂停使用
            self.entranceThread.working_state = 1
        elif mode == 2 :
            self.stackedWidget.setCurrentIndex(5) # 箱体已满
            self.entranceThread.working_state = 2
        elif mode == 3 :
            self.stackedWidget.setCurrentIndex(2) # 倒计时服务界面
            self.entranceThread.working_state = 3

    # 批量构造8页界面 stackedWidget 的设定方法，2显示倒计时和重量，5，7显示倒计时
    for i in range(1, 9):
        exec("def _show_{0}(self,flag): self.stackedWidget.setCurrentIndex({1})".format(i, i-1))
        
    def _show_timer(self, time, index):
        exec("self.lcdNumber_{0}.display(time)".format(index))
        self.serial_message.append("[TIMER] counting {0}".format(time))

    def _show_weight(self, weight):
        self.lcdNumber_1.display(weight)
        self.serial_message.append("[WEIGHT] counting {0}".format(time))

if __name__ == "__main__":
    QtWidgets.QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app=QtWidgets.QApplication(sys.argv)    ### pyqt窗口必须在QApplication方法中使用
    myshow=MyWindow()                       ### 生成mywindow类的实例 myshow
    myshow.show()                           ### myshow调用show方法
    # myshow.setWindowFlags(Qt.FramelessWindowHint)
    # myshow.showMaximized()
    # myshow.showFullScreen()
    sys.exit(app.exec())                  ###消息结束的时候，结束进程，并返回0，接着调用sys.exit(0)退出程序
