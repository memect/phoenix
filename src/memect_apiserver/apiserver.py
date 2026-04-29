'''
Author       : zhoutingji zhoutingji@memect.co
Date         : 2024-01-08 13:26:12
LastEditTime : 2024-01-25 15:11:40
FilePath     : /rag/app/utils/apiserver.py
Description  : apiserver交互操作
'''

import io
import os
import tarfile
import time
import zipfile

import requests

import logging

logger = logging.getLogger('apiserver')


class Api:
    '''
    description: apiserver操作类
    '''
    def __init__(self,base='http://127.0.0.1:6111/api',use_session=False,poll_interval=1):
        '''
        description: init
        '''
        super().__init__()
        self.base = base
        self.session = None
        if use_session:
            self.session = requests.Session()

        self.poll_interval=poll_interval

    def invoke(self,name,data,*,params=None,output_filename=None,output_format='json',async_=False):
        """
        nmae: pdf2json or pdf2table or pdf2doc
        input_filename: pdf的文件路径
        params:{} 其他的参数
        output_filename: 如果output_format=zip，必须设置一个目录，如果output_format=json，可以设置json的存储路径，或者为None，返回json
        output_format: json or zip
        async_: True表示使用轮训的方式获得结果，False表示同步等待结果
        """
        def get_content_text(res):
            try:
                return res.text
            except Exception as e:
                return ''
        url=f'{self.base}/{name}'
        query={}
        if params:
            query.update(params)

        query['async']='true' if async_ else 'false'
        query['output-format']=output_format

        headers={}

        if self.session:
            post = self.session.post
        else:
            post = requests.post
        res = post(url, data=data, params=query, headers=headers)
        if res.status_code == 200:
            #{task:{id:''},server:{name:''}}
            return self.get_result(name,res,output_filename=output_filename,output_format=output_format,async_=async_)
        elif res.status_code == 400:
            #返回错误,{error:{code:'',message:''}}
            error = res.json()['error']
            raise Exception(f'调用api失败，返回:error={error}, content_text={get_content_text(res)}')
        else:
            # 其它的错误，如：500，系统错误
            raise Exception(f'调用api失败，返回status_code={res.status_code}, content_text={get_content_text(res)}')

    def save_result(self,res,output_filename,output_format):
        '''
        description: 存储结果
        '''
        if output_filename:
            os.makedirs(os.path.dirname(output_filename),exist_ok=True)
        if output_format=='json':
            #如果没有指定文件名，就返回json对象
            if not output_filename:
                return res.json()
            #否则就是保存到指定的文件中
            with open(output_filename,'wb') as fp:
                fp.write(res.content)
        elif output_format=='zip':
            with io.BytesIO(res.content) as fp:
                with zipfile.ZipFile(fp) as zf:
                    zf.extractall(output_filename)
        elif output_format=='bz2':
            with io.BytesIO(res.content) as fp:
                with tarfile.open(fileobj=fp) as tf:
                    tf.extractall(output_filename)
        else:
            raise ValueError(f'不支持的output_format={output_format}')

    def get_result(self,name,res,*,output_filename=None,output_format='json',async_=False):
        '''
        description: 获取结果
        '''
        if not async_:
            #如果不是异步的，直接获得结果了
            return self.save_result(res,output_filename,output_format)

        #data={task:{},server:''}
        data = res.json()
        task = data['task']
        url=f'{self.base}/{name}'
        query={
            'task_id':task['id']
        }
        if self.session:
            get = self.session.get
        else:
            get = requests.get
        while True:
            #必须使用GET方法
            res = get(url,params=query)
            logger.info(f'status={res.status_code}')
            if res.status_code==200:
                return self.save_result(res,output_filename,output_format)
            elif res.status_code==400:
                #获得错误信息:{error:{code:'',message:''}}
                result = res.json()
                error = result.get('error')
                code = error['code']
                if code=='error':
                    #表示已经执行完毕，但是执行失败，不需要再轮训
                    raise Exception(f'调用api失败，error={error}')
                elif code in ('running','waiting'):
                    #running or waiting
                    #等待1秒再次轮训
                    time.sleep(self.poll_interval)
                else:
                    #其他的错误码？暂时没有，一样不需要继续了
                    raise Exception(f'调用api失败，error={error}')
            else:
                #其他的错误，如：500，系统错误，如果有前置，可能是前置错误等，不需要再轮训
                #理论上这个可以尝试几次，但是现在就不尝试了
                raise Exception(f'调用api失败，status_code={res.status_code}')
