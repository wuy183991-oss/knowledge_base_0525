import json

from pymongo import MongoClient


mongo_client = MongoClient("mongodb://192.168.1.245:27017")

db = mongo_client["test"]

#创建集合
# db.create_collection("classes")

#插入数据
# db["classes"].insert_one({"name":"wuke","age":18})


#查询
find_result = db["classes"].find()  #列表
for doc in find_result:
    print(doc) 
    print(doc["name"])