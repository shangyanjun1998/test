"""
设备类：
    switch：开关类型设备，通过check_on读取状态
    motor：电机类型设备，通过forward，stop，reverse设置继电器输出
    adc：模拟量读取设备，通过get_value读取模拟量输入通道数值
    mqtt_device：mqtt客户端
    timer：定时器类，定时更新倒计时用
"""

import modbus_tk.defines as cst
import paho.mqtt.client as mqtt
from apscheduler.schedulers.background import BackgroundScheduler

class timer:
    def __init__(self, max_cnt, timer_cnt, num): # 传入定时最长时间，信号量以及lcd的序号
        self.cnt = 0
        self.isActive = True
        self.max_cnt = max_cnt
        self.timer_cnt = timer_cnt
        self.num = num
        self.timer = BackgroundScheduler() # 定时器对象
        self.timer.add_job(self.timer_operation, 'interval', seconds=1.0)
        self.timer.start(paused=True)
    
    def pause(self):
        self.timer.pause()

    def start(self):
        self.cnt = 0
        self.isActive = True
        self.timer_cnt.emit(self.max_cnt - self.cnt, self.num)
        self.timer.resume()

    def reset(self):
        self.cnt = 0
        self.timer_cnt.emit(self.max_cnt - self.cnt, self.num)
        self.timer.pause()

    def timer_operation(self):
        if self.cnt > self.max_cnt:
            # self.timer.shutdown(wait=False)
            self.timer.pause()
            self.isActive = False
            return 
        self.timer_cnt.emit(self.max_cnt - self.cnt, self.num)
        # print("counting {0} at {1}".format(self.num, self.cnt))
        self.cnt+=1
        
class mqtt_device:
    def __init__(self, host, port, user, pwd):
        self.client_id = "dustbin"
        self.client = mqtt.Client(self.client_id)
        self.client.username_pw_set(user, pwd)
        self.client_topic = '/iot/dbin'
        try:
            print("Successfully connect to mqtt broker {0}".format(self.client.connect(host, port, keepalive=5)))
        except Exception as e:
            print("Server refused to connect")
    # 小区名， 垃圾桶序号， 用户， 垃圾桶类型， 本次投递重量， 
    def send_info(self, community, bin_id, user, bin_type, weight, total_weight):
        info_dict = {
                    'community':community, \
                    'bin_id':bin_id, \
                    'user':user, \
                    'bin_type':bin_type,\
                    'weight':str(weight),\
                    'total_weight':str(total_weight)
                    }
        info_string = json.dumps(info_dict)
        self.client.reconnect()
        self.client.publish(self.client_topic, payload=info_string, qos=0)

class output_switch:
    def __init__(self, addr, port, master): # 站号， 地址， 主线程中modbus设备的实例
        self.addr = addr
        self.port = port
        self.master = master
        self.state = -1
        print("Init switch at {0} {1}".format(addr,port))
    def check_on(self):
        self.state = self.master.execute(self.addr, cst.READ_COILS, self.port-1, 1)[0]
        return self.state
    def set_state(self, output_value):
        self.state = self.master.execute(self.addr, cst.WRITE_SINGLE_COIL, self.port-1, output_value=output_value)
        return self.state

class switch:
    def __init__(self, addr, port, master): # 站号， 地址， 主线程中modbus设备的实例
        self.addr = addr
        self.port = port
        self.master = master
        self.state = -1
        print("Init switch at {0} {1}".format(addr,port))
    def check_on(self):
        self.state = self.master.execute(self.addr, cst.READ_DISCRETE_INPUTS, self.port-1, 1)[0]
        return self.state

class motor:
    def __init__(self, addr, bridge, master): # 站号， 四个继电器的地址
        self.addr = addr
        self.bridge = bridge
        self.master = master
        (self.h1,self.h2,self.l1,self.l2) = bridge
        print("Init motor at {0} {1}".format(addr, bridge))

    def stop(self):
        res1 = self.master.execute(self.addr, cst.WRITE_SINGLE_COIL, self.h1-1, output_value=0)
        res2 = self.master.execute(self.addr, cst.WRITE_SINGLE_COIL, self.h2-1, output_value=0)
        res3 = self.master.execute(self.addr, cst.WRITE_SINGLE_COIL, self.l1-1, output_value=0)
        res4 = self.master.execute(self.addr, cst.WRITE_SINGLE_COIL, self.l2-1, output_value=0)
        print(res1,res2,res3,res4)

    def forward(self):
        res1 = self.master.execute(self.addr, cst.WRITE_SINGLE_COIL, self.h1-1, output_value=1)
        res2 = self.master.execute(self.addr, cst.WRITE_SINGLE_COIL, self.h2-1, output_value=0)
        res3 = self.master.execute(self.addr, cst.WRITE_SINGLE_COIL, self.l1-1, output_value=0)
        res4 = self.master.execute(self.addr, cst.WRITE_SINGLE_COIL, self.l2-1, output_value=1)
        print(res1,res2,res3,res4)

    def reverse(self):
        res1 = self.master.execute(self.addr, cst.WRITE_SINGLE_COIL, self.h1-1, output_value=0)
        res2 = self.master.execute(self.addr, cst.WRITE_SINGLE_COIL, self.h2-1, output_value=1)
        res3 = self.master.execute(self.addr, cst.WRITE_SINGLE_COIL, self.l1-1, output_value=1)
        res4 = self.master.execute(self.addr, cst.WRITE_SINGLE_COIL, self.l2-1, output_value=0)
        print(res1,res2,res3,res4)

class adc:
    def __init__(self, addr, port, master): # 站号， 地址， 主线程中modbus设备的实例
        self.addr = addr
        self.port = port
        self.master = master
        print("Init adc at {0} {1}".format(addr, port))
    
    def get_value(self):
        res = self.master.execute(self.addr, cst.READ_INPUT_REGISTERS, self.port-1, 1)
        return res[0]

if __name__ == "__main__":
    import serial
    import modbus_tk
    import modbus_tk.defines as cst
    from modbus_tk import modbus_rtu
    import time
    # try:
    ser=serial.Serial(port="/dev/ttyS1",baudrate=9600,bytesize=8,parity='N',stopbits=1)
    master = modbus_rtu.RtuMaster(ser)
    master.set_timeout(5.0) # 需要设置，否则可能没有返回值,timeout表示若超过5秒没有连接上slave就会自动断开
    # s1 = switch(1, 1, master)
    # print(s1.check_on())
    # m1 = motor(1, (1,2,3,4), master)
    # m1.forward()
    # time.sleep(2)
    # m1.stop()
    # time.sleep(2)
    # m1.reverse()
    # time.sleep(2)
    # a1 = adc(1, 1, master)
    # print(a1.get_value())
    s2 = output_switch(1, 3, master)
    print("call set state {}".format(s2.set_state(0)))
    time.sleep(2)
    print("set state  {}".format(s2.check_on()))
    time.sleep(2)
    print("call set state {}".format(s2.set_state(1)))
    time.sleep(2)
    print("set state  {}".format(s2.check_on()))
    time.sleep(2)
    # except Exception as e:
    #     print("Test failed, check modbus device and serial comm")