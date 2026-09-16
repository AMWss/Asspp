# Asspp：iPadOS 16 专版与 iPhone OTA

目标仓库：<https://github.com/AMWss/Asspp>。

| 设备 | 构建来源 | 安装方式 |
|---|---|---|
| iPad / iPadOS **16.0** | 最新上游＋iOS 16 兼容补丁 | TrollStore（巨魔）安装 IPA |
| iPhone 13 Pro / iOS **18** | 正常上游，不应用 iPad 补丁 | 配置分发签名后的 Safari OTA |

## 当前交付状态

源码和工作流已提交到此 fork，11 项本地测试已通过。
[首个构建](https://github.com/AMWss/Asspp/actions/runs/34949862462)已通过 Xcode 26.6 编译、
包内二进制最低系统检查及 IPA 检查，生成 `wiki.qaq.Asspp`、最低 iOS 16.0 的 iPad 包。
**尚未进行 iPadOS 16.0 实机登录、App Store 下载验证，不能据此宣称这两项已解决。**
iPad 自动跟随上游已开启。iPhone 的 Pages 已配置为 Actions 部署，但签名 Secrets 尚未配置，OTA 尚未上线。

## iPad：通过巨魔安装兼容 IPA

iPad 已安装 TrollStore（巨魔），可以用它安装兼容 IPA，无需为这台设备配置付费开发者签名。

1. 将兼容改动提交到你的 fork，打开 [Actions](https://github.com/AMWss/Asspp/actions)。
2. 启用 fork 的 Actions，运行 **iPadOS 16 - Compatibility Check**。
3. 默认分支构建通过后，在 [Releases](https://github.com/AMWss/Asspp/releases) 中选择标题为 **Asspp iPadOS 16** 的版本，下载 `Asspp-iPad16-unsigned.ipa`。
   也可从对应运行的 Artifacts 下载 `Asspp-iPad16-unsigned-…`，解压得到 IPA。
4. 将 IPA 交给 iPad 上的 TrollStore 安装，之后同样用新 IPA 覆盖更新。
5. 完成下文 iPadOS 16.0 的实机验收。

发布标题为 **Asspp iPadOS 16**，桌面应用名仍为 **Asspp**（上游项目目标的名称设置优先）。
最低版本 16.0，只面向 iPad；默认搜索 iPad 应用。
默认 Bundle ID 仍为 `wiki.qaq.Asspp`，因此可能覆盖原版。若安装工具改变 Bundle ID 或签名团队，
原版的钥匙串账号未必可访问，届时重新登录。账号数据不写入 GitHub。

## 安装流程说明

### A. 在 Asspp 内下载安装 App Store 应用

这使用上游已有的 ApplePackage 登录/下载和本机 HTTPS 安装服务，
不需要为了**这个功能本身**申请付费开发者会员。Asspp 本身仍需先正确签名安装。

1. 登录 Apple ID，根据提示完成两步验证。
2. 在 Asspp 设置页安装其本地 HTTPS 根证书；在系统设置中安装下载的描述文件。
3. 按系统要求在“通用 → 关于本机 → 证书信任设置”启用该证书的完全信任，并允许本地网络访问。
4. 搜索与你账号地区匹配的应用，获取你账号有权下载的应用版本，完成下载后点“安装”。

保留了上游 HTTPS 服务、manifest、签名注入和 IPA 下载代码。
最低系统版本取决于**所下载的应用本身**；Asspp 能运行在 16.0，不会使要求 iOS 17 的应用也能运行。
如最新版不支持 16.0，可尝试账号有权下载、且本身支持 16.0 的历史版本。

### B. iPhone：用 Safari 网页安装/更新 Asspp 本身

你发来的 `FORK_AUTOBUILD_GUIDE.md` 讲的是这个流程。
它要求适用于分发的有效 `.p12` 证书及 `.mobileprovision`，Ad Hoc 描述文件需包含 **iPhone 13 Pro 的 UDID**，无需为巨魔 iPad 准备该签名。
普通个人账号自签不能直接作为这份 Ad Hoc 网页发布流程的替代。

准备好签名材料后，在 GitHub 仓库 Settings → Secrets and variables → Actions 中配置：

| 类型 | 名称 | 内容 |
|---|---|---|
| Secret | `IOS_CERT_P12_BASE64` | 分发证书 p12 的 Base64 |
| Secret | `IOS_CERT_PASSWORD` | p12 密码 |
| Secret | `IOS_PROVISIONING_PROFILE_BASE64` | 包含 iPhone 的分发描述文件 Base64 |
| Variable | `IOS_BUNDLE_ID` | 描述文件对应的 Bundle ID |
| Variable | `IOS_EXPORT_METHOD` | `release-testing`（现代 Xcode 的 Ad Hoc 导出名称） |
| Variable | `IOS_OTA_BASE_URL` | 可选 HTTPS 自定义 Pages 根地址 |

证书和密码只通过 GitHub Secrets 设置，不提交到仓库、不贴在聊天中。
已有 macOS 签名材料可使用上游 `Resources/Scripts/generate.github.action.inputs.sh` 辅助配置。

仓库必须公开；Settings → Pages → Source 选择 **GitHub Actions**。
手动运行 **iPhone - Upstream Signed OTA**。发布成功后安装地址为：

<https://amwss.github.io/Asspp/ios/latest/install.html>

**以上是部署成功后的预期地址，现在不代表已上线。** 安装用 **iPhone Safari** 打开。
页面发布前校验 IPA 的最低系统不高于 18.0、支持 iPhone、Bundle ID、签名描述文件类型和有效期；
Xcode 归档还检查签名及包内 Mach-O 二进制的最低系统版本。

## 自动跟随上游

把兼容工作流及补丁放在 fork 的**默认分支**，设置仓库 Variable：

- `IOS16_AUTO_BUILD=true`：每 30 分钟检查上游，生成有新变化的未签名 IPA。
- `IPHONE_AUTO_BUILD=true`：已配置签名材料时，每 30 分钟检查上游并签名发布 iPhone OTA。

不配置 iPhone 分发签名时，保持 `IPHONE_AUTO_BUILD` 未设置即可。两个开关互不影响。
GitHub 定时任务可能排队或延迟；这属于定时同步，不能保证上游一提交就即时完成构建。
长期没有活动的公开仓库可能需要重新启用定时工作流。

每次构建固定一个上游提交。iPad 工作流应用 `Resources/Patches/ios16.patch`，iPhone 工作流直接构建上游：

```text
Lakr233/Asspp main（固定提交）
        ├─ iPad：iOS 16 补丁 → Xcode / 包校验 → IPA → 巨魔安装
        └─ iPhone：正常上游 → Xcode / 分发签名 → Release + Safari OTA
```

上游的 App Store 协议、下载逻辑及 `Package.resolved` 依赖锁随源码进入构建。
不自动拉取尚未被 Asspp 上游采用的 ApplePackage 版本。
补丁冲突、编译失败或包检查失败会停止发布，需要维护兼容补丁。
iPhone 成功部署后的回执用于去重，Pages 部署失败的运行会在后续检查中重试。
Releases 保留旧 IPA；Pages 每次只保留当前版本页面及 latest 入口，不承诺保留历史版本网页。

## 源码研究结论

- 3.0.25 的应用目标最低 iOS 为 15.0；当前上游设为 17.0。
- 提交 `4a327fe` 将共享模型迁移为 `@Observable`，新界面还用到 iOS 17 的空状态、动画和 onChange 重载。
  因此仅修改 IPA 的版本声明或 deployment target 不够。
- 旧版内置的认证入口固定为 `buy.itunes.apple.com`；后续 `f5f8831` 加入 bag 获取认证入口和 pod 分区路由。
- 当前锁定 ApplePackage 1.2.7，其包声明支持 iOS 15 起。这为保留最新协议并下移界面兼容层提供了基础。
  旧版登录失败是否全部由入口/路由引起，需要结合实际错误日志确认。
- 兼容版以 `ObservableObject` / `@Published` / `@ObservedObject` / `@StateObject` 维护账号、下载、安装、历史版本页面状态；
  对持久化计算属性显式发送变更通知，保留原存储格式。
- 本地下载行单独观察下载状态，安装页单独观察安装器状态，避免“能打开但进度不刷新”。

参考：[上游自动构建指南](https://github.com/Lakr233/Asspp/blob/main/Resources/Document/FORK_AUTOBUILD_GUIDE.md)、
[ApplePackage 1.2.7](https://github.com/Lakr233/ApplePackage/blob/1.2.7/Package.swift)、
[Apple 开发者账号说明](https://developer.apple.com/help/account/basics/about-your-developer-account)。

## 实机验收与排错

### iPadOS 16.0

1. 在 iPadOS **16.0** 安装后冷启动，确认账号、搜索、下载、设置页面均可打开。
2. 新增账号并完成 2FA；退出重进，确认账号持久化。
3. 搜索账号所属地区的免费 iPad 应用，确认信息、历史版本列表、下载入口可用。
4. 下载一个兼容 iOS 16 的应用，确认进度刷新，暂停/恢复/完成及 IPA 文件均正常。
5. 安装并信任本地 HTTPS 证书，允许本地网络，尝试在 Asspp 内安装该应用。
6. 若失败，提供**错误信息、发生在哪一步、系统版本、构建编号**。分享日志前删除 Apple ID、cookie、令牌等账号信息。

### iPhone 13 Pro / iOS 18

1. 准备包含 iPhone UDID 的分发描述文件，运行 **iPhone - Upstream Signed OTA**。
2. 成功后，用 iPhone Safari 打开上述安装页，确认能够安装并启动。
3. 上游更新后再次运行，确认通过同一链接能覆盖更新且账号数据可用。
4. 如安装失败，先核对证书有效期、描述文件是否包含 iPhone、IPA 和 manifest 是否能公开访问。

本地测试命令（Python 3.10+、Git）：

```sh
python3 -m unittest discover -s Resources/Scripts/ios16/tests -v
```

维护补丁时修改应用源码；若升级基线，同步更新 `Resources/Patches/ios16-base.txt`，然后：

```sh
python3 Resources/Scripts/ios16/refresh_patch.py
python3 -m unittest discover -s Resources/Scripts/ios16/tests -v
```

补丁仅包含 `Asspp`、`Configuration`、`Asspp.xcodeproj` 下的运行时代码。
不要使用带 `git reset --hard` / `git clean` 的上游打包脚本处理已应用补丁但未提交的临时源码，
它会清掉兼容改动；两个专版工作流直接调用 `xcodebuild`。
