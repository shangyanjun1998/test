import paho.mqtt.client as mqtt
import time
import json

host = "127.0.0.1"
port = 1883
user = "test_user"
pwd = "test_passwd"

# def on_connect(client, userdata, flags, rc):
#     print("Connected with result code: " + str(rc))

# def on_message(client, userdata, msg):
#     print(msg.topic + " " + str(msg.payload))

# client = mqtt.Client()
# client.username_pw_set(user, pwd)
# client.on_connect = on_connect
# client.on_message = on_message
# client.connect(host, port)
# while True:
#     client.publish('fifa', payload='amazing', qos=0)
#     time.sleep(2.0)

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

if __name__ == "__main__":
    mqtt_client = mqtt_device(host, port, user, pwd)
    time.sleep(10.0)
    mqtt_client.send_info('tj', str(1), 'user_name', 'residual',1.0, 22.9) # 干垃圾:residual

