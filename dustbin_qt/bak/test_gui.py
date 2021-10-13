"""
主界面调试类： 完成程序主体逻辑
"""

import sys
from panel_2 import Ui_MainWindow
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

    def read_param(self):
        self.serial_port = self.serial_port.currentText()
        self.modbus_port = self.modbus_port.currentText()
        self.baud_rate = self.baud_rate.currentText()
        self.data_bit = int(self.data_bit.currentText())
        self.parity = self.parity.currentText()
        self.stop_bit = int(self.stop_bit.currentText())

    def serial_connect(self):
        self.stackedWidget.setCurrentIndex(5)
        pass

    def serial_disconnect(self):
        pass

    def _user_thread(self, flag):
        # self.frame.setStyleSheet("border-image: url(:/layer/source/2.jpg);") # 修改背景
        self.userThread.start()

    def _admin_thread(self, flag):
        pass
    
    def _log_append(self, text):
        pass

    def _release_enter(self, flag):
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