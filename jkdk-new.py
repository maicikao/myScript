# -*- encoding:utf-8 -*-
"""
cron: 0 8 * * *
new Env('我在校园健康打卡');
"""

import datetime
import os
import requests
from urllib.parse import urlencode
import time
import json
import hashlib

class pre:
    # 获取answers
    def get_answers(self,i):
        global get_answers
        get_answers = os.getenv("wzxy_jkdk_config" + str(i) + "answers", "null")
        if get_answers == "null":
            get_answers = '["0"]'
            print("未获取到用户的"+str(i+1)+"answers,使用默认answers："+str(get_answers))
        else:
            get_answers = os.getenv("wzxy_jkdk_config" + str(i) + "answers")
            #get_answers = get_answers.strip('[')
            #get_answers = get_answers.strip(']')
            #get_answers = get_answers.split(',')
            print("获取到用户的"+str(i+1)+"anwsers："+str(get_answers))
        return get_answers

# 读写 json 文件
class processJson:
    def __init__(self, path):
        self.path = path

    def read(self):
        with open(self.path, 'rb') as file:
            data = json.load(file)
        file.close()
        return data

    def write(self, data):
        with open(self.path, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        file.close()


class WoZaiXiaoYuanPuncher:
    def __init__(self, item, answers):
        # 我在校园账号数据
        self.data = item['wozaixiaoyuan_data']
        # pushPlus 账号数据
        self.pushPlus_data = item['pushPlus_data']
        # mark 打卡用户昵称
        self.mark = item['mark']
        # answers
        self.answers = answers
        # 初始化  jwsession
        self.jwsession = ""
        # 学校打卡时段
        self.seqs = []
        # 打卡结果
        self.status_code = 0
        # 请求头
        self.header = {
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36 MicroMessenger/7.0.9.501 NetType/WIFI MiniProgramEnv/Windows WindowsWechat",
            "content-type": "application/json;charset=UTF-8",
            "Content-Length": "2",
            "Host": "gw.wozaixiaoyuan.com",
            "Accept-Language": "en-us,en",
            "Accept": "application/json, text/plain, */*"
        }
        # signdata  要保存的信息
        self.sign_data = ""
        # 请求体（必须有）
        self.body = "{}"

    # 地理/逆地理编码请求
    def geoCode(self, url, params):
        url = "https://apis.map.qq.com/ws/geocoder/v1/"
        _params = {
            **params,
            "key": "A3YBZ-NC5RU-MFYVV-BOHND-RO3OT-ABFCR",
        }
        response = requests.get(url=url, params=_params)
        res = json.loads((response.text))
        return res
    # 设置JWSESSION
    def setJwsession(self):
    # 如果找不到cache,新建cache储存目录与文件
        if not os.path.exists('.cache'):
            print("正在创建cache储存目录与文件...")
            os.mkdir('.cache')
            data = {"jwsession": self.jwsession}
        elif not os.path.exists('.cache/'+str(self.data["username"])+".json"):
            print("正在创建cache文件...")
            data = {"jwsession": self.jwsession}
        # 如果找到cache,读取cache并更新jwsession
        else:
            print("找到cache文件，正在更新cache中的jwsession...")
            data = processJson('.cache/'+str(self.data["username"])+".json").read()
            data['jwsession'] = self.jwsession
        processJson('.cache/'+str(self.data["username"])+".json").write(data)
        self.jwsession = data['jwsession']

    # 获取JWSESSION
    def getJwsession(self):
        if not self.jwsession:  # 读取cache中的配置文件
            data = processJson('.cache/'+str(self.data["username"])+".json").read()
            self.jwsession = data['jwsession']
        return self.jwsession
    # 请求地址信息
    def requestAddress(self, location):
        # 根据经纬度求具体地址
        url2 = 'https://apis.map.qq.com/ws/geocoder/v1/'
        location = location.split(',')
        res = self.geoCode(url2, {
             "location": location[1] + "," + location[0]
        })
        _res = res['result']

        country = _res['address_component']['nation']
        province = _res['address_component']['province']
        city = _res['address_component']['city']
        district = _res['address_component']['district']
        township = _res['address_reference']['town']['title']
        street = _res['address_component']['street']
        nationcode = _res['ad_info']['nation_code']
        areacode = _res['ad_info']['adcode']
        citycode = _res['ad_info']['city_code']
        towncode = _res['address_reference']['town']['id']
        
        address=country+"/"+province+"/"+city+"/"+district+"/"+township+"/"+street
        addresscode=nationcode+"/"+areacode+"/"+citycode+"/"+towncode

        if city == '无锡市':
            lk="在无锡"
        else:
            lk="不在无锡"

        sign_data = {
            "location": address+"/"+addresscode,
            "t1": "否",
            "t2": lk,
            "t3": "否",
            "type": 0,
            "locationType": 0
        }
        return sign_data
    # 登录

    def login(self):
        # 登录接口
        loginUrl = "https://gw.wozaixiaoyuan.com/basicinfo/mobile/login/username"
        username, password = str(self.data['username']), str(self.data['password'])
        url = f'{loginUrl}?username={username}&password={password}'
        self.session = requests.session()
        # 登录
        response = self.session.post(url=url, data=self.body, headers=self.header)
        res = json.loads(response.text)
        if res["code"] == 0:
            self.jwsession = response.headers['JWSESSION']
            self.setJwsession()
            return True
        else:
            print("登录失败，请检查账号信息" + str(res))
            self.status_code = 5
            return False

    # 获取打卡列表，判断当前打卡时间段与打卡情况，符合条件则自动进行打卡
    def PunchIn(self):
        url = "https://student.wozaixiaoyuan.com/health/getHealthLatest.json"
        self.header['Host'] = "student.wozaixiaoyuan.com"
        self.header['content-type'] = "application/x-www-form-urlencoded"
        self.header['Content-Length'] = "0"
        self.header['JWSESSION'] = self.getJwsession()
        self.session = requests.session()
        response = self.session.post(url=url, data=self.body, headers=self.header)
        res = json.loads(response.text)
        # 如果 jwsession 无效，则重新 登录 + 打卡
        if res['code'] == -10:
            print('jwsession 无效，尝试账号密码打卡')
            self.status_code = 4
            loginStatus = self.login()
            if loginStatus:
                print("登录成功")
                self.PunchIn()
            else:
                print("登录失败")
        elif res['code'] == 0:
            self.doPunchIn()

    # 打卡
    def doPunchIn(self):
        print('开始打卡，打卡信息：')
        url = "https://gw.wozaixiaoyuan.com/health/mobile/health/save?batch=8600001"
        headers = {
            "Host": "gw.wozaixiaoyuan.com",
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; V2055A Build/RP1A.200720.012; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/86.0.4240.99 XWEB/4277 MMWEBSDK/20220706 Mobile Safari/537.36 MMWEBID/815 MicroMessenger/8.0.25.2200(0x2800193B) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 miniProgram/wxce6d08f781975d91",
            "Referer": "https://gw.wozaixiaoyuan.com/h5/mobile/health/index/health/detail?id=8600001",
            "Content-Length": "360",
        }
        headers["JWSESSION"] = self.getJwsession()
        sign_data = self.requestAddress(self.data['location'])
        self.sign_data = sign_data
        print(sign_data)
        data = json.dumps(sign_data)
        response = self.session.post(url, data=data, headers=headers).json()
        ##response = json.loads(response.text)
        # 打卡情况
        if response["code"] == 0:
            self.status_code = 1
            print("打卡成功")
        else:
            self.status_code = 3
            print(response)
            print("打卡失败")

    # 获取打卡结果
    def getResult(self):
        res = self.status_code
        if res == 1:
            return "✅ 打卡成功"
        elif res == 2:
            return "✅ 你已经打过卡了，无需重复打卡"
        elif res == 3:
            return "❌ 打卡失败，当前不在打卡时间段内"
        elif res == 4:
            return "❌ 打卡失败，jwsession 无效"
        elif res == 5:
            return "❌ 打卡失败，登录错误，请检查账号信息"
        else:
            return "❌ 打卡失败，发生未知错误"

    # 推送打卡结果
    def sendNotification(self):
        notifyResult = self.getResult()
        # pushplus 推送
        url = 'http://www.pushplus.plus/send'
        notifyToken = self.pushPlus_data['notifyToken']
        content = json.dumps({
            "打卡用户": self.mark,
            "打卡项目": "健康打卡",
            "打卡情况": notifyResult,
            "打卡信息": self.sign_data,
            "打卡时间": time.strftime("%Y-%m-%d %H:%M:%S", (time.localtime())),
        }, ensure_ascii=False)
        msg = {
            "token": notifyToken,
            "title": "⏰ 我在校园打卡结果通知",
            "content": content,
            "template": "json"
        }
        body = json.dumps(msg).encode(encoding='utf-8')
        headers = {'Content-Type': 'application/json'}
        r = requests.post(url, data=body, headers=headers).json()
        if r["code"] == 200:
            print("消息经 pushplus 推送成功")
        else:
            print("pushplus: " + r)
            print("消息经 pushplus 推送失败，请检查错误信息")


if __name__ == '__main__':
   # 读取环境变量，若变量不存在则返回 默认值 'null'
    for i in range(200):
        try:
            client_priv_key = os.getenv('wzxy_jkdk_config'+str(i), 'null')
            if client_priv_key == 'null':
                print('打卡完毕，共'+str(i)+"个账号。")
                break
            configs = os.environ['wzxy_jkdk_config'+str(i)]
            configs = json.loads(configs)
            answers = pre().get_answers(i)
            print("开始打卡用户："+configs["mark"])
            wzxy = WoZaiXiaoYuanPuncher(configs, answers)
            # 如果没有 jwsession，则 登录 + 打卡
            if os.path.exists('.cache/'+str(configs["wozaixiaoyuan_data"]["username"])+".json") is False:
                print("找不到cache文件，正在使用账号信息登录...")
                loginStatus = wzxy.login()
                if loginStatus:
                    print("登录成功,开始打卡")
                    wzxy.PunchIn()
                else:
                    print("登录失败")
            else:
                print("找到cache文件，正在使用jwsession打卡")
                wzxy.PunchIn()
            wzxy.sendNotification()
        except Exception as e:
            print("账号"+str(i+1)+"信息异常"+e)