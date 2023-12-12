<p align="center">
  <img src="doc/img/log.png" style="width:500px;"/>
</p>



<p align="center">
  <a href="./README_EN.md">English README</a> | <a href="./README.md">中文 README</a>
</p>

<p align="center">
  <a href="#项目描述">🔍 项目描述</a> •
  <a href="#功能预览">🍭 功能预览</a> •
  <a href="#部署">🔧 部署安装</a> •
  <a href="#待办清单">📌 待办清单</a>
  <a href="#联系我们">🚗 联系我们 </a>
</p>

# 项目描述 📚

> 一个利用大模型帮助我们在 Gitlab 上进行 Code Review 提升研发效能的项目 💪🏻 (( 包括但不限于 GPT 🎁))


**这个项目有什么特点? ✨** 

🐶 针对于 <span style="background-image: linear-gradient(to right, #ff9900, #ff66cc);-webkit-background-clip: text;color: transparent;font-weight: bold;">Gitlab 定制</span>

🐱 结合了<span style="background-image: linear-gradient(to right, #ff9900, #ff66cc);-webkit-background-clip: text;color: transparent;font-weight: bold;">GPT</span>的能力  🚀

🦊 正在尝试接入私有化 LLM  <span style="background-image: linear-gradient(to right, #ff9900, #ff66cc);-webkit-background-clip: text;color: transparent;font-weight: bold;">代码安全问题</span> 

🦁 我们将一直关注效能研发 <span style="background-image: linear-gradient(to right, #ff9900, #ff66cc);-webkit-background-clip: text;color: transparent;font-weight: bold;">最新的Coder Review动态</span> 融入这个项目


# [项目架构 🚗](https://vze9i86ezn.feishu.cn/docx/BuFidAogAoH1ecxQstscBUdhnfb?openbrd=1&doc_app_id=501&blockId=YneudO6sRoXPFIxkohtcgbwenye&blockType=whiteboard&blockToken=Yd3CwIPdphgGmFbWcRfcx9aNnrf#YneudO6sRoXPFIxkohtcgbwenye)

<p align="center">
  <img src="doc/img/project_framework.png" style="width:500px;"/>
</p>


# 功能预览 🌈

### 1. Gitlab Merge Request 触发评论
<p align="center">
  <img src="doc/img/gpt_code_review_gitlab.png" style="width:500px;"/>
</p>

### 2. 钉钉消息通知
<p align="center">
  <img src="doc/img/img.png" style="width:500px;"/>
</p>


# 部署 📖

#### 源代码运行 💻
1.**克隆仓库**
```bash
git clone git@github.com:mimo-x/Code-Review-GPT-Gitlab.git
```
2.**安装依赖**
```bash
pip install -r requirements.txt
```
3.**修改配置文件**
```bash
vim config/config.py
```
4.**运行**
```bash
python3 app.py
```
5.**配置Gitlab webhook**
<p align="center">
  <img src="doc/img/webhookconfig.png" style="width:300px;"/>
</p>

6.**尝试发起一个 Merge Request 吧🎉**



   
#### Docker

```bash
todo dockerfile
```


# 待办清单 📌

- ✅ 使用 GPT 进行Code Review
- [ ] 尝试接入私有化大模型解决代码安全问题
- [ ] 可以配置更多的触发方式
  - ✅ Merge Request
  - [ ] commit
  - [ ] tag
- [ ] 兼容飞书的消息通知
- [ ] 兼容钉钉的消息通知
- [ ] 结合静态代码分析来提供修改代码的风险等级

# 交流 👨‍👨‍👦‍👦
👏🏻 很高兴你能向我们提出一些问题和修改建议（issue，pr）, 欢迎 star 项目 ⭐️ 

📮 Email：mixuxin@163.com 

📱 wx: isxuxin

👨‍👨‍👦‍👦 如果有任何使用问题，欢迎来这里交流 👋🏻
<img src="doc/img/wechat.jpg" style="width:400px">

# 参考文献 📚
- [(字节)基于大模型 + 知识库的 Code Review 实践](https://mp.weixin.qq.com/s?__biz=Mzg2ODQ1OTExOA==&mid=2247504479&idx=1&sn=1ec09afbb5b5b9b2aaf151994be5fd27&chksm=cea9655ef9deec48b17cbab05ddd1ab04c86736d8b469eaac6f5a707ca110ce4186e8985ff41&mpshare=1&scene=1&srcid=1011C8l5RmCM2EL4Rpl3wdRy&sharer_shareinfo=96d0a83631aaa25db87709baa250085d&sharer_shareinfo_first=96d0a83631aaa25db87709baa250085d#rd)
- [(美团)代码变更风险可视化系统建设与实践](https://tech.meituan.com/2023/09/22/construction-and-practice-of-code-change-risk-visualization-system.html)


# License 📑
![github license](https://img.shields.io/github/license/mimo-x/Code-Review-GPT-Gitlab)
**This project is licensed under the [MIT License](https://chat.openai.com/c/9be6b422-f10c-4379-b152-e756230d54f8#:~:text=%E7%9A%84%E5%AE%8C%E6%95%B4%E6%96%87%E6%9C%AC%EF%BC%9A-,MIT%20License,-%E4%BD%A0%E5%8F%AF%E4%BB%A5%E8%AE%BF%E9%97%AE).**



