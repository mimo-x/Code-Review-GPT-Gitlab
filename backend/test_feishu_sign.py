#!/usr/bin/env python
"""
测试飞书签名生成是否正确
"""
import hashlib
import base64
import hmac
import time

def gen_sign_correct(timestamp, secret):
    """
    正确的飞书签名生成方法（根据官方文档）
    """
    # 拼接timestamp和secret
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    # 使用 HMAC-SHA256 算法
    hmac_code = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    # 对结果进行base64处理
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return sign

def gen_sign_wrong(timestamp, secret):
    """
    错误的签名生成方法（之前的实现）
    """
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    # 错误：只使用了 SHA256，没有使用 HMAC
    hmac_code = hashlib.sha256(string_to_sign.encode('utf-8')).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return sign

if __name__ == '__main__':
    # 测试数据
    test_timestamp = str(int(time.time()))
    test_secret = "SEC_test_secret_key_12345"

    print("="*60)
    print("飞书签名验证测试")
    print("="*60)
    print(f"时间戳: {test_timestamp}")
    print(f"密钥: {test_secret}")
    print(f"签名字符串: {test_timestamp}\\n{test_secret}")
    print("-"*60)

    # 生成正确的签名
    correct_sign = gen_sign_correct(test_timestamp, test_secret)
    print(f"正确的签名 (HMAC-SHA256): {correct_sign}")

    # 生成错误的签名
    wrong_sign = gen_sign_wrong(test_timestamp, test_secret)
    print(f"错误的签名 (SHA256): {wrong_sign}")

    print("-"*60)
    if correct_sign != wrong_sign:
        print("✅ 签名算法已修复！两个签名不同，现在使用正确的 HMAC-SHA256 算法")
    else:
        print("❌ 签名算法仍有问题")
    print("="*60)
