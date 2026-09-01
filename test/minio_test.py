from utils.minio_utils import get_minio_client

# 获取客户端
client = get_minio_client()
print(f"客户端类型: {type(client)}")
print(f"是否为空: {client is None}")

if client:
    # 测试连接
    buckets = client.list_buckets()
    print(f"可用的存储桶: {[b.name for b in buckets]}")
else:
    print("❌ MinIO 客户端为空，请检查配置！")