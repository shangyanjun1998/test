"""
主界面调试类： 完成程序主体逻辑
"""

import sys
from panel import Ui_MainWindow
from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from PyQt5.QtCore import Qt
from PyQt5.Qt import QLCDNumber
from PyQt5.QtWidgets import QApplication


import serial
import modbus_tk
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu
import time

import os
import yaml

from device import adc, motor, switch
# from job import entranceThread, workThread
from job import init_hardware, read_id_list
import job

class entranceThread(job.entranceThread): # 重载
    def run(self):
        self.run_flag = True
        while self.run_flag:
            time.sleep(0.1) # CPU占用过高
            try:
                if self.ser.in_waiting:
                    read_str=self.ser.read(self.ser.in_waiting)
                    # read_str=self.ser.read(self.ser.in_waiting ).hex()
                    if not self.working: # 防止二次刷卡
                        self.working = True
                        input_id = str(read_str,'utf-8').split("'")[0]
                        self.log.emit(str("[Read] {}".format(input_id))) #
                        if input_id in self.user:
                            self.start_user.emit(bool(True)) # 
                            self.log.emit(str("[Door] Valid user {}".format(input_id))) #
                        elif input_id in self.admin:
                            self.start_admin.emit(bool(True)) # 
                            self.log.emit(str("[Door] Valid admin {}".format(input_id))) # 
                        else:
                            self.working = False # 
                            self.log.emit(str("[Door] Invalid user {}".format(input_id))) #
                    else:
                        self.log.emit(str("[Door] Don`t scan twice {}".format(input_id))) # 
            except Exception as e:
                print(str(e))

class userThread(job.userThread): # 重载
    timer_cnt = pyqtSignal(int)
    weight_cnt = pyqtSignal(float)
    for i in range (1,9):
        exec("sig_{0} = pyqtSignal(bool)".format(i))
    def test(self):
        cnt = 1
        time_cnt = 0
        weight_cnt = 15
        while cnt<9:
            exec("self.sig_{0}.emit(True)".format(cnt))
            if cnt ==2:
                print("Start 2")
                time_cnt = 0
                while time_cnt<=10:
                    time_cnt+=1
                    weight_cnt+=50
                    self.timer_cnt.emit(time_cnt)
                    self.weight_cnt.emit(weight_cnt)
                    time.sleep(1.0)
            if cnt == 5:
                print("Start 5")
                time_cnt = 0
                while time_cnt<=10:
                    time_cnt+=1
                    self.timer_cnt.emit(time_cnt)
                    time.sleep(1.0)
            if cnt == 7:
                print("Start 7")
                time_cnt = 0
                while time_cnt<=10:
                    time_cnt+=1
                    self.timer_cnt.emit(time_cnt)
                    time.sleep(1.0)
            cnt+=1
            time.sleep(1.0)
        self.end.emit(True)
    def temp(self):
        self.sig_7.emit(True)
        time.sleep(10.0)
        self.end.emit(True)

    def run(self):
        # self.test()
        # self.temp()
        self.process_1()
        self.end.emit(True)

    def process_1(self):
        self.sig_1.emit(True) # 1.jpg
        thresh = 1900 # 加压阈值
        if self.switch_1.check_on() and self.switch_2.check_on(): # 如果开关TD01和TD02开启
            time_start = time.time()
            weight_start = self.adc.get_value() 
            weight = 0 # 手动初始化
            self.motor_3.forward()
            self.output_switch_10.set_state(1)
            cnt = 0
            while cnt<=5:
                time.sleep(1)
                cnt+=1
                if self.switch_8.check_on()==1: # 如果触发，D03停止
                    break
            if self.switch_8.check_on() == 0: # 默认计时循环如果通过check_on = 1退出则离开后保持为1，暂不考虑防抖
                self.motor_3.stop()
                self.sig_3.emit(True)
                time.sleep(5.0) # 流程图中没有说明
                return # 报警无法开门3.jpg
            else: # 不需要显式说明这个else
                self.motor_3.stop() # 界面显示开始服务, 2.jpg
                if self.switch_10.check_on() == 1: 
                    weight = self.adc.get_value() - weight_start # D03称重, 开始倒计时120s并显示投递重量
                    self.weight_cnt.emit(weight)
                # 没有给出switch_10状态为0的分支，则读数为0
                tick = 0
                delay = 120
                self.timer_cnt.emit(delay) # 从0开始显示的bug
                self.sig_2.emit(True) # 成功开门
                while time.time() - time_start <=delay: # 所以这个应该是120? 流程图中给的是60
                    tick+=1
                    time.sleep(0.1)
                    if tick%10 ==0:
                        self.timer_cnt.emit(delay - tick/10)
                    # 如果计时过程中出现人离开就停止计时
                    if self.switch_1.check_on() == 0 and self.switch_2.check_on() == 0:
                        break
                self.sig_4.emit(True) # 即将关门 4.jpg
                time.sleep(5.0) # 流程图中没有给出
                self.motor_3.reverse() # d03反转
                self.output_switch_10.set_state(0) # d10关
                # TODO：上传投递信息，发出信号，由主线程进行
                cnt = 0
                while cnt <=5:
                    time.sleep(1.0)
                    cnt+=1
                    if self.switch_9.check_on() == 1:
                        break
                if self.switch_9.check_on() == 0: # 暂不考虑防抖
                    self.motor_3.stop()
                    self.sig_5.emit(True) # 关门失败，清理障碍物
                    tick = 0
                    delay = 30
                    while tick<=delay: # 流程图中没有给出
                        tick+=1
                        time.sleep(1.0)
                        self.timer_cnt.emit(delay - tick)
                        if self.switch_9.check_on() == 0:
                            break
                if self.switch_9.check_on() == 0: # 如果仍然有垃圾
                    return # 报警门口有垃圾无法关门，这一步无需要循环等待能否正确关门吗？ return.5.jpg
                self.motor_3.stop()
                if self.switch_5.check_on() == 0 and \
                    self.switch_6.check_on() == 0 and self.switch_7.check_on() == 0:
                    print("Successful Loop")
                    return # 本次投递成功，等待下一个投递
                # 不需要显式写出这个分支
                elif self.switch_5.check_on() == 1 or \
                    self.switch_6.check_on() == 1 or self.switch_7.check_on() == 1:
                    self.motor_2.forward()
                    cnt = 0
                    while cnt<20:
                        time.sleep(1.0)
                        cnt+=1
                        if self.switch_11.check_on() == 1: # 防抖？
                            break
                    if self.switch_11.check_on() == 0:
                        self.motor_2.stop() # 需求中没有给出d02停止的逻辑
                        self.sig_8.emit(True)
                        time.sleep(5.0) # 流程图中未给出
                        return # 暂停服务，报警，上传压缩故障信息,8.jpg
                    self.motor_2.stop()
                    self.motor_1.forward()
                    delay = 120
                    tick = 0
                    self.timer_cnt.emit(delay - tick/10) # 119开始显示的bug
                    self.sig_7.emit(True)
                    while self.adc.get_value() - (weight_start + weight) < thresh: # 垃圾压缩显示倒计时120s,7.jpg
                        tick +=1
                        time.sleep(0.1)
                        if tick%10 == 0:
                            self.timer_cnt.emit(delay - tick/10)
                        if self.switch_3.check_on() == 1:
                            break
                    cnt = 0
                    self.motor_1.stop() # d01停止5秒
                    while cnt<=5:
                        time.sleep(1.0) # 这部分时间包括在120s倒计时内？
                        tick+=10 # 
                        self.timer_cnt.emit(delay - tick/10) # 
                        cnt+=1
                    self.motor_1.reverse()
                    cnt = 0
                    print("D01 reverse 20s")
                    while cnt<=20:
                        time.sleep(1.0) # 这部分时间包括在120s倒计时内？
                        cnt+=1
                        tick+=10 # 
                        self.timer_cnt.emit(delay - tick/10) # 
                        if self.switch_4.check_on() == 1:
                            self.motor_1.stop()
                            break
                    if self.switch_4.check_on() == 0:
                        self.motor_1.stop() # 逻辑图中没有给出d01停止的条件
                        self.sig_8.emit(True)
                        time.sleep(5.0) # 流程图中没有给出
                        return # 暂停服务，报警，上传压缩故障信息,8.jpg
                    print("D02 reverse 20s")
                    self.motor_2.reverse()
                    cnt = 0
                    while cnt<=20:
                        time.sleep(1.0)
                        cnt+=1
                        tick+=10 # 
                        self.timer_cnt.emit(delay - tick/10) # 
                        if self.switch_12.check_on() == 1:
                            self.motor_2.stop()
                            break
                    if self.switch_12.check_on() == 0:
                        self.motor_2.stop() # 逻辑中没有给出d01停止的条件
                        self.sig_8.emit(True)
                        time.sleep(5.0) # 流程图中没有给出
                        return # 暂停服务，报警，上传压缩故障信息,8.jpg
                    if self.switch_5.check_on() == 0 and \
                        self.switch_6.check_on() == 0 and self.switch_7.check_on() == 0:
                        print("Successful Loop")
                        return # 本次投递成功，等待下一个投递
                    # 不需要显式写出这个分支
                    elif self.switch_5.check_on() == 1 or \
                        self.switch_6.check_on() == 1 or self.switch_7.check_on() == 1:
                        self.sig_6.emit(True)
                        time.sleep(2.0)
                        return # 暂停服务，上传满载信息，等待垃圾收运,6.jpg
        return 

class MyWindow(QtWidgets.QMainWindow,Ui_MainWindow):
    def __init__(self):
        # set UI
        super(MyWindow,self).__init__() # 菱形继承
        self.setupUi(self)
        # self.gui_tab.setWindowFlags (Qt.Window|Qt.FramelessWindowHint)
        # self.gui_tab.showFullScreen()

        self.serial_flag = False
        self.user,self.admin  = read_id_list()

        for i in range (1,21):
            exec('self.serial_port.addItem("/dev/ttyS{0}")'.format(i))
        for i in range (1,21):
            exec('self.modbus_port.addItem("/dev/ttyS{0}")'.format(i))

        self.lcdNumber = QtWidgets.QLCDNumber(self.frame)
        self.lcdNumber.setObjectName("lcdNumber")
        self.lcdNumber.setFrameShape(0)
        self.lcdNumber.setSegmentStyle(QLCDNumber.Flat)
        self.lcdNumber.hide()

        self.weightNumber = QtWidgets.QLCDNumber(self.frame)
        self.weightNumber.setObjectName("weightNumber")
        self.weightNumber.setFrameShape(0)
        self.weightNumber.setSegmentStyle(QLCDNumber.Flat)
        self.weightNumber.hide()

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
                    self.entranceThread.start_user.connect(self._admin_thread)
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

    def _release_enter(self, flag):
        self.entranceThread.working = False
        self.lcdNumber.hide()
        self.weightNumber.hide()
        self.frame.setStyleSheet("QFrame#frame{border-image: url(:/layer/source/1.jpg);}") # 修改背景
        # QFrame#myframe{border-image:url(:/new/prefix1/timg .jpg);}

    def _show_1(self,flag):
        self.serial_message.append("[GUI] showing 1")
        self.frame.setStyleSheet("QFrame#frame{border-image: url(:/layer/source/1.jpg);}") # 修改背景
        self.weightNumber.hide()
        self.lcdNumber.hide()
    
    def _show_2(self,flag): # 显示时间和重量
        self.serial_message.append("[GUI] showing 2")
        self.frame.setStyleSheet("QFrame#frame{border-image: url(:/layer/source/2.jpg);}") # 修改背景
        width = self.frame.geometry().width()
        height = self.frame.geometry().height()
        w = width/12
        h = height/12
        self.lcdNumber.setGeometry(QtCore.QRect(0.89 * width-w*0.8, height*0.119-h/2, w, h))
        self.weightNumber.setGeometry(QtCore.QRect(0.2* width-w*0.8, height*0.119-h/2, w, h))
        self.weightNumber.show()
        self.lcdNumber.show()
        # self.lcdNumber.display(999)

    def _show_3(self,flag):
        self.serial_message.append("[GUI] showing 3")
        self.frame.setStyleSheet("QFrame#frame{border-image: url(:/layer/source/3.jpg);}") # 修改背景
        self.weightNumber.hide()
        self.lcdNumber.hide()

    def _show_4(self,flag):
        self.serial_message.append("[GUI] showing 4")
        self.frame.setStyleSheet("QFrame#frame{border-image: url(:/layer/source/4.jpg);}") # 修改背景
        self.weightNumber.hide()
        self.lcdNumber.hide()

    def _show_5(self,flag): # 只显示时间
        self.serial_message.append("[GUI] showing 5")
        self.frame.setStyleSheet("QFrame#frame{border-image: url(:/layer/source/5.jpg);}") # 修改背景
        width = self.frame.geometry().width()
        height = self.frame.geometry().height()
        w = width/12
        h = height/12
        self.lcdNumber.setGeometry(QtCore.QRect(0.485*width-w*0.8, 0.665*height-h/2, w, h))
        self.weightNumber.hide()
        self.lcdNumber.show()
        # self.lcdNumber.display(888)

    def _show_6(self,flag):
        self.serial_message.append("[GUI] showing 6")
        self.frame.setStyleSheet("QFrame#frame{border-image: url(:/layer/source/6.jpg);}") # 修改背景
        self.weightNumber.hide()
        self.lcdNumber.hide()

    def _show_7(self,flag): # 只显示时间
        self.serial_message.append("[GUI] showing 7")
        self.frame.setStyleSheet("QFrame#frame{border-image: url(:/layer/source/7.jpg);}") # 修改背景
        width = self.frame.geometry().width()
        height = self.frame.geometry().height()
        w = width/12
        h = height/12
        self.lcdNumber.setGeometry(QtCore.QRect(0.575*width-w*0.8, 0.62*height-h/2, w, h))
        self.weightNumber.hide()
        self.lcdNumber.show()
        # self.lcdNumber.display(777.7)

    def _show_8(self,flag):
        self.serial_message.append("[GUI] showing 8")
        self.frame.setStyleSheet("QFrame#frame{border-image: url(:/layer/source/8.jpg);}") # 修改背景
        self.weightNumber.hide()
        self.lcdNumber.hide()

    def _show_timer(self, time):
        self.serial_message.append("[TIMER] counting {0}".format(time))
        self.lcdNumber.display(time)
        pass
    def _show_weight(self, weight):
        self.weightNumber.display(weight)
        self.serial_message.append("[WEIGHT] counting {0}".format(time))
        pass

if __name__ == "__main__":
    QtWidgets.QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app=QtWidgets.QApplication(sys.argv)
    myshow=MyWindow()
    myshow.show()
    # myshow.setWindowFlags(Qt.FramelessWindowHint)
    # myshow.showMaximized()
    # myshow.showFullScreen()
    sys.exit(app.exec())