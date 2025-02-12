<p align="center">
  <img src="doc/img/log.png" style="width:500px;"/>
</p>



<p align="center">
  <a href="./README_EN.md">English README</a> | <a href="./README.md">中文 README</a>
</p>

<p align="center">
  <a href="https://tqz0rsrhsvf.feishu.cn/docx/FlgzdMrj0oYOg2xXY7EcrsZZnjb?from=from_copylink">📚 官方文档</a>
</p>
<p align="center">
  <a href="#项目描述-">🔍 项目描述</a> •
  <a href="#功能预览-">🍭 功能预览</a> •
  <a href="#部署-">🔧 部署安装</a> •
  <a href="#待办清单-">📌 待办清单</a>
  <a href="#交流-">🚗 联系我们 </a>
</p>

# 项目描述 📚

> 一个利用大模型帮助我们在 Gitlab 上进行 Code Review 提升研发效能的项目 💪🏻 (( 包括但不限于 GPT 🎁))

**这个项目有什么特点? ✨** 

🐶 针对于 <span style="background-image: linear-gradient(to right, #ff9900, #ff66cc);-webkit-background-clip: text;color: transparent;font-weight: bold;">Gitlab 定制</span>

🐱 结合了<span style="background-image: linear-gradient(to right, #ff9900, #ff66cc);-webkit-background-clip: text;color: transparent;font-weight: bold;">GPT</span>的能力  🚀

🦊 能够接入私有化 LLM  <span style="background-image: linear-gradient(to right, #ff9900, #ff66cc);-webkit-background-clip: text;color: transparent;font-weight: bold;">代码安全问题</span> 

🦁 我们将一直关注效能研发 <span style="background-image: linear-gradient(to right, #ff9900, #ff66cc);-webkit-background-clip: text;color: transparent;font-weight: bold;">最新的Coder Review动态</span> 融入这个项目


# [项目架构 🚗](https://vze9i86ezn.feishu.cn/docx/BuFidAogAoH1ecxQstscBUdhnfb?openbrd=1&doc_app_id=501&blockId=YneudO6sRoXPFIxkohtcgbwenye&blockType=whiteboard&blockToken=Yd3CwIPdphgGmFbWcRfcx9aNnrf#YneudO6sRoXPFIxkohtcgbwenye)

### 🚀 **全新架构升级：更强大、更灵活、更高效！** 🌈

<p align="center">
  <img src="doc/img/project_framework.png" style="width:500px;"/>
</p>

🌟  **丰富的模型接入**  支持轻松接入<span style="background-image: linear-gradient(to right, #ff9900, #ff66cc);-webkit-background-clip: text;color: transparent;font-weight: bold;">更多的模型</span> ，无论是经典模型还是最新的AI模型，都能轻松集成！

🔧  **高度定制化**     开发者可以<span style="background-image: linear-gradient(to right, #ff9900, #ff66cc);-webkit-background-clip: text;color: transparent;font-weight: bold;">便捷地自定义处理逻辑和回复机制</span>，打造专属于你的解决方案！

🔗  **扩展性强**       模块化设计使得功能扩展更加方便，未来可以<span style="background-image: linear-gradient(to right, #ff9900, #ff66cc);-webkit-background-clip: text;color: transparent;font-weight: bold;">轻松添加新功能</span>，满足不断变化的需求！

🛠️  **高可维护性**     代码结构清晰，注释详细，便于维护和二次开发，减少开发者的负担！

**快来体验我们的新架构吧，享受前所未有的强大功能和极致体验！**✨






# 功能预览 🌈

### 1. Gitlab Merge Request 触发评论
<p align="center">
  <img src="doc/img/gpt_code_review_gitlab.png" style="width:500px;"/>
</p>

### 2. 钉钉消息通知
<p align="center">
  <img src="doc/img/img.png" style="width:500px;"/>
</p>

### 3. 更多种大模型接入
1. 可通过实现项目接口快速接入自定义模型，具体配置方式参见[config.md](doc/config.md)。
2. 项目通过[UnionLLM](https://github.com/EvalsOne/UnionLLM/)进行多模型支持，
兼容[LiteLLM](https://docs.litellm.ai/docs)，默认支持模型如下表所示。

<table style="width:100%; text-align:center; border-collapse:collapse;">
  <tr>
    <td>OpenAI</td>
    <td>Azure</td>
    <td>AWS - SageMaker</td>
    <td>AWS - Bedrock</td>
  </tr>
  <tr>
    <td>Google - Vertex_AI</td>
    <td>Google - Palm</td>
    <td>Google AI Studio - Gemini</td>
    <td>Mistral AI API</td>
  </tr>
  <tr>
    <td>Cloudflare AI Workers</td>
    <td>Cohere</td>
    <td>Anthropic</td>
    <td>Empower</td>
  </tr>
  <tr>
    <td>Huggingface</td>
    <td>Replicate</td>
    <td>Together_AI</td>
    <td>OpenRouter</td>
  </tr>
  <tr>
    <td>AI21</td>
    <td>Baseten</td>
    <td>Vllm</td>
    <td>NLP_Cloud</td>
  </tr>
  <tr>
    <td>Aleph Alpha</td>
    <td>Petals</td>
    <td>Ollama</td>
    <td>Deepinfra</td>
  </tr>
  <tr>
    <td>Perplexity-AI</td>
    <td>Groq AI</td>
    <td>DeepSeek</td>
    <td>Anyscale</td>
  </tr>
  <tr>
    <td>IBM - Watsonx.ai</td>
    <td>Voyage AI</td>
    <td>Xinference [Xorbits Inference]</td>
    <td>FriendliAI</td>
  </tr>
  <tr>
    <td>Galadriel</td>
    <td>智谱AI</td>
    <td>月之暗面 Moonshot</td>
    <td>百度文心一言</td>
  </tr>
  <tr>
    <td>阿里巴巴通义千问</td>
    <td>MiniMax</td>
    <td>讯飞星火</td>
    <td>百川智能</td>
  </tr>
  <tr>
    <td>昆仑天工</td>
    <td>零一万物</td>
    <td>阶跃星辰</td>
    <td>字节豆包</td>
  </tr>
  <tr>
    <td>深度求索 DeepSeek</td>
    <td>More</td>
    <td></td>
    <td></td>
  </tr>
</table>
### 4. 自定义更多的通知方式和处理手段

1. 可通过实现自定义``Reply``类添加如邮箱，私有机器人等多种通知方式，具体教程参见[reply.md](doc/reply.md)
2. 可通过自定义更多的``Review Handle``引入自定义的代码审查逻辑，具体教程参见[review.md](doc/review.md)




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
> 填写```Webhook URL```时，请在域名后添加路径```/git/webhook```，例如：```http://example.com/git/webhook```
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
- ✅ 实现多模型支持
- [ ] 可以配置更多的触发方式
  - ✅ Merge Request
  - [ ] commit
  - [ ] tag
- [ ] 兼容飞书的消息通知
- [ ] 兼容钉钉的消息通知
- [ ] 结合静态代码分析来提供修改代码的风险等级
- [ ] 通过pydantic实现大模型输出内容的格式化

# 交流 👨‍👨‍👦‍👦
👏🏻 很高兴你能向我们提出一些问题和修改建议（issue，pr）, 欢迎 star 项目 ⭐️ 

📮 Email：mixuxin@163.com 

📱 wx: isxuxin

👨‍👨‍👦‍👦 如果有任何使用问题，欢迎来这里交流 👋🏻
<p float="left">
  <img src="doc/img/wechat.jpg" width="400" />
  <img src="doc/img/xuxin.png" width="400" /> 
</p>



# 参考文献 📚
- [(字节)基于大模型 + 知识库的 Code Review 实践](https://mp.weixin.qq.com/s?__biz=Mzg2ODQ1OTExOA==&mid=2247504479&idx=1&sn=1ec09afbb5b5b9b2aaf151994be5fd27&chksm=cea9655ef9deec48b17cbab05ddd1ab04c86736d8b469eaac6f5a707ca110ce4186e8985ff41&mpshare=1&scene=1&srcid=1011C8l5RmCM2EL4Rpl3wdRy&sharer_shareinfo=96d0a83631aaa25db87709baa250085d&sharer_shareinfo_first=96d0a83631aaa25db87709baa250085d#rd)
- [(美团)代码变更风险可视化系统建设与实践](https://tech.meituan.com/2023/09/22/construction-and-practice-of-code-change-risk-visualization-system.html)


# License 📑
![github license](https://img.shields.io/github/license/mimo-x/Code-Review-GPT-Gitlab)
**This project is licensed under the [MIT License](https://chat.openai.com/c/9be6b422-f10c-4379-b152-e756230d54f8#:~:text=%E7%9A%84%E5%AE%8C%E6%95%B4%E6%96%87%E6%9C%AC%EF%BC%9A-,MIT%20License,-%E4%BD%A0%E5%8F%AF%E4%BB%A5%E8%AE%BF%E9%97%AE).**


## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=mimo-x/Code-Review-GPT-Gitlab&type=Date)](https://star-history.com/#mimo-x/Code-Review-GPT-Gitlab&Date)
