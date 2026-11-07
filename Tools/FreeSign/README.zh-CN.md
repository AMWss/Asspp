# Apple ID 免费自签 Asspp

[打开工作流](https://github.com/AMWss/Asspp/actions/workflows/free-sign.yml)

## 首次配置

打开 [Repository Secrets](https://github.com/AMWss/Asspp/settings/secrets/actions)，点击 **New repository secret**，填写以下四项。

| 名称 | 内容 |
|---|---|
| `APPLE_ID` | 用来免费自签的 Apple ID |
| `APPLE_PASSWORD` | 该账号的登录密码 |
| `IPHONE_UDID` | 目标 iPhone 的完整 UDID，例如 `00008110-…` |
| `SIGNING_STATE_PASSWORD` | 自己生成的至少 20 位随机密码，用于加密签名状态。后续继续使用同一个值 |

`IPHONE_UDID` 可在连接电脑后的爱思助手设备信息中复制。
签名材料只通过 Secrets 和加密的状态文件保存。请把状态密码保存在自己的密码管理器中。

## 第一次签名

1. 打开工作流，点击 **Run workflow**，分支选择 **main**。
2. Operation 选择 **Sign IPA**，点击运行。
3. 工具完成编译后会下载官方最新 `Asspp.ipa`，登录 Apple 并开始自签。
4. 如果日志显示 **Waiting for 2FA**，在 Secrets 新增或更新 `APPLE_2FA_CODE`，填入 Apple 刚发来的六位验证码。
5. 回到同一个工作流，再点击 **Run workflow**，Operation 改成 **Send verification code**。Target run ID 通常留空。
6. 原来的签名任务会在十分钟内等待验证码，并在收到后继续。若验证码被拒绝，可更新 Secret 并再次发送。
7. 成功后，在原签名任务的 **Artifacts** 下载 `Asspp-signed`，解压得到 `Asspp-signed.ipa`。

验证码通过等待任务的一次性公钥加密传递。不要把验证码填进普通 workflow inputs。
如果同时有多个等待任务，在 Target run ID 填原任务地址中 `/runs/` 后面的数字。

## 后续运行

继续运行 **Sign IPA**。任务会尝试恢复上次的 Apple 会话、Anisette 状态和签名私钥，并向 Apple 获取描述文件。会话失效时可能再次要求 2FA。免费账号的描述文件通常有效七天。

状态使用 Scrypt 和 AES-256-GCM 加密后存入 Actions Artifacts，保留 90 天。不要手动删除最新的 `free-sign-state-…`。超过保存期后仍可重新认证，但已有证书的私钥若已丢失，可能需要你自行管理账号里的证书。

这个工作流遇到证书额度用尽会失败。它不会自动吊销账号已有证书。

签好的 IPA 内嵌设备描述文件，可能显示 UDID。在这个公开仓库中，有仓库读取权限的 GitHub 用户可能下载 Actions 的产物。签名状态和验证码产物均已加密。

## 可选设置

账号关联多个 Team 时，在 Repository Variables 添加 `APPLE_TEAM_ID`。需要替换 Anisette 服务时添加 `ANISETTE_URL`。默认使用 isideload 的公开 Anisette 服务 `https://ani.iloader.app`，其可用性及 Apple 的接受情况需要实际认证验证。

## 验证边界

离线检查涵盖工具编译、加密状态完整性、验证码传递、防重放和工作流语法。完整的 Apple 登录、证书签发、描述文件续期和 IPA 实机运行需要填好 Secrets 后验证。

运行签名任务不依赖 iPhone 连在云端。工具通过 UDID 登记设备，只输出签名 IPA。
签名后使用安装工具在目标设备上安装，网页分发不属于本实验。

源码固定到 [isideload 326e562](https://github.com/nab138/isideload/tree/326e56229d0727cb6e7b34c8cf03e37e2cd3e17d)。
