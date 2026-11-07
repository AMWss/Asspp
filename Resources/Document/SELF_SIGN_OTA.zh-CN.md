# Asspp 免费自签与网页安装研究

## 分支

- [main](https://github.com/AMWss/Asspp/tree/main) 跟随 Lakr233/Asspp 的 main。应用源码与上游一致，保留三个 fork 专用工作流文件。可在 [Actions](https://github.com/AMWss/Asspp/actions/workflows/sync-upstream.yml) 手动运行同步，定时检查每 6 小时一次。
- [ios16](https://github.com/AMWss/Asspp/tree/ios16) 保存 iPadOS 16 兼容源码、补丁、验证脚本和本说明。默认分支的 [iPad 构建入口](https://github.com/AMWss/Asspp/actions/workflows/ios16-check.yml) 调用该分支的工作流。它固定兼容代码和上游提交后应用补丁，补丁冲突会阻止发布。成功的 iPad IPA 用 TrollStore 安装。
- GitHub 会在公开仓库长期无活动时停用定时工作流。若上游更新了工作流文件且 GitHub 拒绝同步推送，可使用只授权本仓库、具有 Contents 和 Workflows 写权限的凭据，存入 `UPSTREAM_SYNC_TOKEN`。应用代码的常规同步使用内置 GitHub token。

## 签名与安装是两个步骤

HTTPS 的 IPA 直链会下载文件。网页安装由 `itms-services://?action=download-manifest&url=…` 触发，HTTPS manifest 再指向 IPA。设备还会验证 Apple 签发的描述文件、证书、设备登记、Bundle ID、entitlements 和有效期。

免费 Personal Team 可以自签设备测试包，描述文件有效期为 7 天。SideStore 和 iloader 能用个人 Apple ID 签装，首登或会话失效时可能需要 2FA。现成工具的安装路径使用设备配对及安装服务。Apple 的免费账号文档描述的是个人设备测试，公开网页分发文档针对受支持的分发签名。普通免费开发签名能否在目标 iOS 版本通过 Safari OTA 仍需要实机验证。

## 实验顺序

1. 用 Actions 生成未签名的 Asspp IPA，固定上游 SHA。
2. 在你控制的设备上登录 Apple ID，完成 2FA 并为目标 iPhone 获得开发证书、签名私钥和描述文件。优先在 Windows 上用 Sideloadly 或 iloader 验证免费自签安装。云端构建不需要 Apple ID。
3. 拿到可导出的开发签名材料后，先在受控环境中用同一个 Bundle ID、同一个证书及未过期的描述文件签一份 IPA，验证能通过正常侧载安装和启动。
4. 同一份签名 IPA 放到受控 HTTPS 地址，以单独的 manifest 测试 Safari OTA。在新装及覆盖更新场景分别记录系统版本、安装提示、是否能启动以及签名有效期。若侧载成功但 Safari 安装失败，就保留 Actions 打包加 SideStore 签装的流程。
5. 只有 Safari 安装实验通过，才值得把签名和 manifest 发布接进 Actions。可优先使用预生成的签名材料，或在用户控制的自托管 runner 上使用本地开发者会话。后者还需验证会话过期后如何处理 2FA。

现有 [iPhone OTA 工作流](https://github.com/AMWss/Asspp/actions/workflows/upstream-signed-ios.yml) 仍用 Apple 分发证书及 Ad Hoc 描述文件。免费签名实验与这条发布流程分开。账号密码、验证码、会话和设备配对文件留在用户控制的设备。公开的已签名 IPA 可能暴露其描述文件内的设备 UDID。

## 参考

- [Apple 免费开发账号与 Personal Team](https://developer.apple.com/help/account/basics/about-your-developer-account/)
- [Apple 关于 OTA manifest 的说明](https://support.apple.com/guide/deployment/distribute-proprietary-in-house-apps-depce7cefc4d/web)
- [Apple 签名描述文件技术说明](https://developer.apple.com/documentation/technotes/tn3125-inside-code-signing-provisioning-profiles)
- [SideStore FAQ](https://docs.sidestore.io/docs/faq)
- [iloader 的签名与安装实现说明](https://iloader.app/)
