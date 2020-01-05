import time

import pymongo
import requests
from pymongo.collection import Collection
from pyquery import PyQuery

from Config.config import Config


class Query:
    table: None

    def __init__(self):
        '''
        构造方法
        '''
        # 加载配置
        # 请求头
        self.config = Config('./config.json')
        self.mongo = pymongo.MongoClient(self.config.get('mongo_host'))
        self.headers = {
            "Host": "www.1905.com",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36 MicroMessenger/6.5.2.501 NetType/WIFI WindowsWechat QBCore/3.43.1021.400 QQBrowser/9.0.2524.400",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        self.sleep_time = self.config.get('sleep_time')
        self.table = None

    # 请求指定地址，自动携带请求头
    def query(self, url):
        '''
        请求指定地址
        :param url:
        :return:
        '''
        req = requests.get(url, headers=self.headers)
        if req.status_code == 200:
            return True, req
        print('请求失败：%s' % url)
        return False, req

    # 获取电影列表页信息
    def get_move_list_info(self, url):
        '''
        获取电影列表页信息
        :return:
        '''
        # 请求电影列表页
        status, res = self.query(url)
        if status == False:
            return False, []
        # 使用PyQuery解析网页
        doc = PyQuery(res.text)
        # 获取电影列表页的类.inqList下的li元素列表
        li = doc('.inqList li').items()
        # 保存电影列表信息的列表变量
        info_list = []
        # 循环遍历li元素列表，解析提取每个元素的有效信息
        for item in li:
            # 保存电影信息的字典变量
            info = {
                # 电影名称
                'title': item('div p a').attr.title,
                # 电影详情页uri
                'moveUrl': item('a').attr.href,
                # 缩略图地址
                'imgUrl': item('a img').attr.src,
                # 相关属性
                'attr': []
            }
            #  循环取出电影的相关属性
            for p in item('div p').items():
                info['attr'].append(p.text())
            # 将本次循环中获取到的电影信息添加到保存电影列表信息的列表变量
            info_list.append(info)
        return True, info_list

    # 保存电影列表页信息到mongo
    def save_info(self, info):
        table = self.get_database_table()
        # 保存电影信息表

        table.insert_many(info, ordered=False)

    # 遍历中国2019年电影列表页 并将信息保存到数据库
    def loop_move_list_page_of_cn2019(self):
        base_url = 'https://www.1905.com/mdb/film/list/country-China/year-2019/o0d0p'
        info_list = []
        # 一共44页
        for i in range(2, 45):
            time.sleep(self.sleep_time)
            url = '%s%d.html' % (base_url, i)
            print('正在访问：', url)
            status, res = self.get_move_list_info(url)
            if status:
                info_list = info_list + res
        self.save_info(info_list)

    # 获取电影的海报地址列表
    def get_move_image_url(self, move_uri):
        '''
        电影详情页中点击图片可以发现，图片版块url如下:
        https://www.1905.com{/mdb/film/2245264/}still/?fr=mdbypsy_dh_tp
        其中 {/mdb/film/2245264/} 部分为 电影列表页中获取到的moveUrl
        1. 判断是否有图片
        浏览多个页面可以发现  部分电影的图片tab是不能点击的
        右键查看元素可以发现 可以点击的tab class为active  不能点击的tab class为gray-style
        因此，可以通过class的判断当前电影是否有图片，没有的可以跳过
        2. 判断是否有海报
        图片判断通过后，需要继续判断图片tab中是否有海报模块
        多浏览几个页面观察可以发现 部分电影同时存在 “剧照” 和 “海报” 模块
        部分电影只有 "剧照" ，部分电影只有 "海报"
        如何判断有海报呢？
        先分析 “剧照” 和 “海报” 的html
        以 https://www.1905.com/mdb/film/2245264/still/?fr=mdbypsy_dh_tp 为例
        可以发现 两个元素都在父级div的class均为 secPag-pics, 其中海报 的 h3元素的class 比剧照的class 多了一个 paddng-top-none
        因此，可以通过判断是否存在 class为paddng-top-none的元素来判断是否有海报模块
        3. 获取海报页地址
        因为部分电影海报较多，点击海报可以发现还有专门的海报页面，会显示所有海报，因此先获取到海报页地址，在去海报页获取所有海报地址
        4. 获取所有海报地址
        :return:
        '''
        # 获取图片tab页地址  注意中间的 %s 为字符串替换
        image_tab_url = 'https://www.1905.com%sstill/?fr=mdbypsy_dh_tp' % move_uri
        # 请求地址
        status, res = self.query(image_tab_url)
        if not status:
            print('请求%s异常，状态码：%d' % (image_tab_url, res.status_code))
            return False, ''

        doc = PyQuery(res.text)
        # 判断图片tab class是否为active
        li = doc('.layout-menu ul li').eq(2).attr('class')
        if li != 'active':
            print("当前页面图片tab不可点击")
            return True, ''

        # 判断是否有海报
        sec = doc('.secPag-pics .paddng-top-none')
        if not sec:
            print('没有海报模块')
            return True, ''

        # 获取海报详情页地址 .secPag-pics:last 代表 class为secPag-pics 的最后一个元素 li:first 代表前置条件元素内的第一个li元素
        image_page_url = doc('.secPag-pics:last ul li:first a').attr('href')
        return True, image_page_url

    # 请求电影详情
    def get_image_list(self, image_page_url):
        # 参数校验，如果地址为空
        if image_page_url == '':
            return False, []
        status, res = self.query(image_page_url)
        if not status:
            return False, []
        images_doc = PyQuery(res.text)
        # 创建一个保存海报的列表变量
        image_list = []
        # 获取 class 为 pic_img_gallery 的元素 下的 所有li元素，items()方法获得一个可遍历的对象
        li = images_doc('.pic_img_gallery li').items()
        for elem in li:
            # 取出一张图片的地址
            image_url = elem('div a').attr('href')
            # 将这个地址添加到列表中
            image_list.append(image_url)
        print('成功获得%d张海报' % (len(image_list)))
        return True, image_list

    # 保存海报列表信息
    def save_image_list(self, key, image_list):
        table = self.get_database_table()
        # 组装需要保存到数据的数据
        update_dict = {'image_list': image_list, 'image_list_status': True}
        # 更新mongodb 数据表中的一条数据 条件为_id = key ,$set 表示直更新局部，即表中的image_list字段
        table.update_one({'_id': key}, {'$set': update_dict})

    # 读取电影列表
    def read_move_list(self,number = 10):
        table = self.get_database_table()
        # 取出image_list_status 不等于 true的记录 , limit 指定取出条数
        info_list = table.find({'image_list_status': {'$ne': True}}).limit(number)
        for info in info_list:
            # 取出信息后，获取海报列表，并写入数据中，
            print("当前请求的是《%s》" % info['title'])
            status, image_page_url = self.get_move_image_url(info['moveUrl'])
            # 如果返回接口正常且获取到url
            if status and image_page_url != '':
                get_image_list_status,image_list = self.get_image_list(image_page_url)
                if get_image_list_status:
                    print("获取到海报列表")
                    self.save_image_list(info['_id'],image_list)
            # 如果返回接口正常且没有获取到url
            elif status and image_page_url == '':
                print("没有海报")
                self.save_image_list(info['_id'],[])
            else:
                print("请求异常")

    # 获取mongo数据库表对象
    def get_database_table(self):
        if self.table is None:
            database = self.mongo[self.config.get('database')]
            self.table = database['move_info']
        return self.table


def main():
    print("欢迎使用电影海报下载小工具")
    url = 'https://www.1905.com/mdb/film/list/country-China/year-2019/o0d0p1.html'
    # 实例化Query对象
    query = Query()
    # text = input("请选择你要执行的功能：")
    text = "3"
    if text == '1':
        status, image_page_url = query.get_move_image_url('/mdb/film/2250704/')
        if status and image_page_url != '':
            res = query.get_image_list(image_page_url)
            print(res)
    elif text == '2':
        query.loop_move_list_page_of_cn2019()
    elif text == '3':
        query.read_move_list()
    else:
        # 执行query对象的get_move_list_info方法
        status, res = query.get_move_list_info(url)
        if status == False:
            print('请求失败')
        else:
            print('请求成功：', res)


# 如果是直接执行当前文件，则执行main方法
if __name__ == '__main__':
    main()
    pass
