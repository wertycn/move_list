# 配置工具类
import json


class Config:
    def __init__(self,path):
        """
        读取配置文件，解析配置
        """
        self._config = self._read_config(path)

        pass
    def get(self,name):
        '''
        获取配置信息
        :param name:
        :return:
        '''
        # 如果配置不存在 则返回空
        if name in self._config:
            return self._config[name]
        else:
            return None

    def _read_config(self,path):
        with open(path) as f:
            file_info = f.read()
        return json.loads(file_info)